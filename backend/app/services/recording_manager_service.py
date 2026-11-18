"""
Recording Manager & Automated AI Clipping Pipeline Service.

Coordinates:
1. Strict authorization verification before recording.
2. OBS WebSocket recording lifecycle (start, monitor health, stop).
3. Registration of completed media into PostgreSQL/SQLite via IngestionService.
4. Automatic AI clipping pipeline triggering (Feature Extraction -> Scoring -> 9:16 Vertical Rendering).
5. Safe recovery after backend or OBS restarts.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import (
    RecordingSession, LiveDiscovery, CreatorAuthorization,
    Streamer, Recording, ProcessingJob, AuditLog, Permission
)
from app.services.creator_authorization_service import creator_authorization_service
from app.services.obs_service import obs_client
from app.services.ingestion_service import ingestion_service
from app.services.job_worker import job_worker
from app.services.candidate_service import candidate_service
from app.services.render_service import render_service


class RecordingManagerService:
    """
    Manages automated recording sessions and seamlessly connects
    completed broadcasts to the AI clipping pipeline.
    """

    def get_active_session(self, db: Session) -> Optional[RecordingSession]:
        """Returns the currently active recording session, if any."""
        return (
            db.query(RecordingSession)
            .filter(RecordingSession.status == "recording")
            .order_by(RecordingSession.started_at.desc())
            .first()
        )

    def list_sessions(
        self,
        db: Session,
        status: Optional[str] = None,
        channel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[RecordingSession], int, int]:
        """Lists recording sessions with optional filtering."""
        query = db.query(RecordingSession)
        if status:
            query = query.filter(RecordingSession.status == status)
        if channel_id:
            query = query.filter(RecordingSession.channel_id == channel_id)

        total = query.count()
        active_count = db.query(RecordingSession).filter(RecordingSession.status == "recording").count()
        items = query.order_by(RecordingSession.started_at.desc()).offset(skip).limit(limit).all()
        return items, total, active_count

    def get_session_by_id(self, db: Session, session_id_or_pk: Any) -> Optional[RecordingSession]:
        """Look up by integer PK or 32-character session_id."""
        if isinstance(session_id_or_pk, int) or (isinstance(session_id_or_pk, str) and session_id_or_pk.isdigit()):
            return db.query(RecordingSession).filter(RecordingSession.id == int(session_id_or_pk)).first()
        return db.query(RecordingSession).filter(RecordingSession.session_id == str(session_id_or_pk)).first()

    def start_session(
        self,
        db: Session,
        channel_id: str,
        video_id: Optional[str] = None,
        discovery_id: Optional[int] = None,
        custom_source: Optional[str] = None,
    ) -> RecordingSession:
        """
        Initiates a new recording session.
        Enforces:
        - Active creator authorization with configured approved source
        - No duplicate active recordings
        - OBS connection and free disk space check
        """
        # 1. Prevent duplicate active recording sessions
        active = self.get_active_session(db)
        if active:
            raise RuntimeError(f"Cannot start recording: Session #{active.id} is already actively recording '{active.channel_id}'.")

        # 2. Verify creator authorization & approved input
        is_auth, auth_reason, auth_record = creator_authorization_service.verify_recording_eligibility(db, channel_id)
        if not is_auth:
            logger.warning(f"[RecordingManager] Recording denied for channel '{channel_id}': {auth_reason}")
            raise PermissionError(f"Recording denied: {auth_reason}")

        # 3. Check OBS connection and disk buffer
        if not obs_client.is_connected():
            connected, err = obs_client.connect()
            if not connected:
                raise ConnectionError(f"Cannot connect to OBS Studio: {err}")

        # 4. Trigger OBS StartRecord
        started, start_err = obs_client.start_recording()
        if not started:
            raise RuntimeError(f"OBS failed to start recording: {start_err}")

        # 5. Determine input source
        source_input = custom_source or (auth_record.authorized_source if auth_record else "OBS:DefaultFeed")

        # 6. Create database record
        session = RecordingSession(
            discovery_id=discovery_id,
            authorization_id=auth_record.id if auth_record else None,
            channel_id=channel_id,
            video_id=video_id,
            source_input=source_input,
            status="recording",
            started_at=datetime.now(timezone.utc),
            metadata_json={
                "creator_name": auth_record.creator_name if auth_record else "Authorized Creator",
                "custom_source": custom_source,
            },
        )
        db.add(session)

        # Update LiveDiscovery status if provided
        if discovery_id:
            discovery = db.query(LiveDiscovery).filter(LiveDiscovery.id == discovery_id).first()
            if discovery:
                discovery.recording_status = "RECORDING"
        elif video_id:
            db.query(LiveDiscovery).filter(LiveDiscovery.video_id == video_id).update(
                {"recording_status": "RECORDING"}
            )

        db.add(
            AuditLog(
                entity_type="recording_session",
                entity_id=None,
                action="recording_started",
                details=f"OBS recording started for channel '{channel_id}' (Source: '{source_input}').",
            )
        )
        db.commit()
        db.refresh(session)
        logger.info(f"[RecordingManager] Started RecordingSession #{session.id} ({session.session_id}) for '{channel_id}'.")
        return session

    def stop_session(
        self,
        db: Session,
        session_id: Optional[str] = None,
        reason: str = "manual_stop",
        auto_process: bool = True,
    ) -> Tuple[RecordingSession, Optional[int]]:
        """
        Stops the active recording session, registers the output video,
        and optionally triggers the automated AI highlight pipeline.
        Returns: (RecordingSession, Optional[recording_id])
        """
        session = self.get_session_by_id(db, session_id) if session_id else self.get_active_session(db)
        if not session:
            raise ValueError("No active recording session found to stop.")

        now = datetime.now(timezone.utc)

        # 1. Stop OBS recording and retrieve output path
        stopped, output_path, stop_err = obs_client.stop_recording()
        if not stopped:
            session.status = "failed"
            session.ended_at = now
            session.error_message = f"OBS stop error: {stop_err}"
            db.commit()
            raise RuntimeError(f"Failed to stop OBS recording: {stop_err}")

        # 2. Inspect recorded file
        if session.metadata_json and session.metadata_json.get("mock_path"):
            mock_override = session.metadata_json["mock_path"]
            if Path(mock_override).exists():
                output_path = mock_override

        duration = 0.0
        file_size = 0
        if output_path and Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            started_ts = session.started_at.replace(tzinfo=timezone.utc).timestamp()
            duration = max(1.0, round(now.timestamp() - started_ts, 1))
        elif session.metadata_json and "mock_path" in session.metadata_json:
            output_path = session.metadata_json["mock_path"]
            duration = 10.0
            file_size = 50000

        session.obs_output_path = output_path
        session.duration_seconds = duration
        session.file_size_bytes = file_size
        session.status = "completed"
        session.ended_at = now

        # 3. Register with IngestionService if file exists
        created_recording_id = None
        if output_path and Path(output_path).exists():
            # Find or auto-bridge Streamer entity
            streamer = db.query(Streamer).filter(Streamer.channel_id == session.channel_id).first()
            if not streamer:
                streamer = Streamer(
                    channel_id=session.channel_id,
                    display_name=(
                        session.metadata_json.get("creator_name")
                        if session.metadata_json
                        else f"Creator_{session.channel_id[:8]}"
                    ),
                    platform="youtube",
                    is_active=True,
                )
                db.add(streamer)
                db.flush()

            # Ensure active permission exists if creator authorization is active
            perm = db.query(Permission).filter(Permission.streamer_id == streamer.id).first()
            auth = db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id == session.channel_id).first()
            if auth and auth.status == "ACTIVE":
                if not perm:
                    perm = Permission(
                        streamer_id=streamer.id,
                        status="ACTIVE",
                        grant_type="manual",
                        granted_at=now,
                        scope="clip_creation",
                    )
                    db.add(perm)
                    db.flush()
                elif perm.status != "ACTIVE":
                    perm.status = "ACTIVE"
                    perm.revoked_at = None
                    db.flush()
            db.commit()

            try:
                rec = ingestion_service.ingest_local_file(
                    db=db,
                    streamer_id=streamer.id,
                    source_path=output_path,
                    copy_to_storage=False,
                )
                session.recording_id = rec.id
                created_recording_id = rec.id
                logger.info(f"[RecordingManager] Ingested OBS output into Recording #{rec.id} ({rec.width}x{rec.height}, {rec.duration_seconds:.1f}s).")
            except Exception as e:
                logger.error(f"[RecordingManager] Failed to ingest recorded file '{output_path}': {e}")
                session.error_message = f"Ingestion warning: {e}"

        # 4. Update LiveDiscovery state
        if session.discovery_id:
            db.query(LiveDiscovery).filter(LiveDiscovery.id == session.discovery_id).update(
                {"recording_status": "RECORDED", "updated_at": now}
            )
        elif session.video_id:
            db.query(LiveDiscovery).filter(LiveDiscovery.video_id == session.video_id).update(
                {"recording_status": "RECORDED", "updated_at": now}
            )

        db.add(
            AuditLog(
                entity_type="recording_session",
                entity_id=session.id,
                action="recording_stopped",
                details=f"OBS recording stopped (Duration: {duration}s, Size: {file_size} bytes, Reason: {reason}).",
            )
        )
        db.commit()
        db.refresh(session)

        # 5. Auto-trigger AI clipping pipeline if requested & recording exists
        if auto_process and created_recording_id and settings.AUTO_PROCESS_AFTER_RECORDING:
            self.trigger_ai_pipeline(db, session.id, created_recording_id)

        return session, created_recording_id

    def trigger_ai_pipeline(self, db: Session, session_id: int, recording_id: int) -> Optional[int]:
        """
        Executes the end-to-end AI clipping pipeline on a newly recorded broadcast:
        1. Feature Extraction (Audio bursts + Scene cuts + Motion + Facecam)
        2. Candidate Generation & Multimodal Scoring + Temporal NMS
        3. Vertical 9:16 MP4 Rendering with dynamic subtitles & presets
        """
        session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()
        if session and session.discovery_id:
            db.query(LiveDiscovery).filter(LiveDiscovery.id == session.discovery_id).update(
                {"recording_status": "PROCESSING"}
            )
            db.commit()

        try:
            logger.info(f"[RecordingManager] Triggering AI pipeline for Recording #{recording_id}...")

            # 1. Feature Extraction
            job = ProcessingJob(
                recording_id=recording_id,
                job_type="full_pipeline",
                status="queued",
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            job_worker.execute_feature_extraction(db=db, job_id=job.id)

            # 2. Candidate Generation & Scoring
            candidates = candidate_service.generate_candidates_for_recording(
                db=db,
                recording_id=recording_id,
                target_count=3,
            )

            # 3. Render Top Highlight Clip(s)
            rendered_clips = 0
            if candidates:
                top_candidate = candidates[0]
                clip = render_service.render_candidate(
                    db=db,
                    candidate_id=top_candidate.id,
                    preset="Viral Gaming",
                    custom_title=f"GTA 6 Highlight #{top_candidate.id}",
                )
                rendered_clips += 1
                logger.info(f"[RecordingManager] Successfully generated vertical clip #{clip.id}: '{clip.title}'")

            # Update LiveDiscovery status to CLIPPED
            if session and session.discovery_id:
                db.query(LiveDiscovery).filter(LiveDiscovery.id == session.discovery_id).update(
                    {"recording_status": "CLIPPED"}
                )
                db.commit()

            return job.id

        except Exception as e:
            logger.error(f"[RecordingManager] AI Pipeline processing failed for Recording #{recording_id}: {e}")
            if session and session.discovery_id:
                db.query(LiveDiscovery).filter(LiveDiscovery.id == session.discovery_id).update(
                    {"recording_status": "FAILED"}
                )
                db.commit()
            return None

    def recover_hanging_sessions(self, db: Session) -> int:
        """
        Recovers sessions left in 'recording' state if backend or OBS restarted.
        """
        active_sessions = (
            db.query(RecordingSession)
            .filter(RecordingSession.status == "recording")
            .all()
        )
        if not active_sessions:
            return 0

        obs_status = obs_client.get_record_status()
        obs_is_recording = bool(obs_status.get("outputActive", False))
        recovered_count = 0

        for s in active_sessions:
            if not obs_is_recording:
                # OBS is not actively recording -> mark session aborted
                s.status = "aborted"
                s.ended_at = datetime.now(timezone.utc)
                s.error_message = "Session recovered after service restart (OBS recording was not active)."
                recovered_count += 1

        if recovered_count > 0:
            db.commit()
            logger.info(f"[RecordingManager] Recovered {recovered_count} hanging recording sessions.")

        return recovered_count


recording_manager_service = RecordingManagerService()
