"""
Processing Job Worker:
Executes multi-stage feature extraction pipelines (Audio ➔ Visual ➔ Facecam ➔ Candidate Generation).
Tracks job progress, updates database state, and manages memory garbage collection between passes.
"""

import gc
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import torch
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import Recording, ProcessingJob, DetectedEvent, AuditLog
from app.services.audio_analysis_service import audio_analysis_service
from app.services.visual_analysis_service import visual_analysis_service
from app.services.facecam_service import facecam_service
from app.services.stt_service import stt_service


class JobWorker:
    @classmethod
    def execute_feature_extraction(cls, db: Session, job_id: int) -> ProcessingJob:
        """
        Runs complete Stage 1-3 feature extraction on a recorded video asset.
        """
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job or not job.recording_id:
            raise ValueError(f"Valid job with recording_id required (job_id={job_id}).")

        rec = db.query(Recording).filter(Recording.id == job.recording_id).first()
        if not rec:
            job.status = "failed"
            job.error_message = f"Recording #{job.recording_id} not found."
            db.commit()
            return job

        video_path = Path(rec.file_path)
        if not video_path.exists():
            job.status = "failed"
            job.error_message = f"Video file not found at {rec.file_path}."
            db.commit()
            return job

        try:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.progress_percent = 5.0
            job.current_stage = "Stage 1: Decoding & Audio Excitement Analysis"
            db.commit()

            # -------------------------------------------------------------
            # STAGE 1: Audio Feature Extraction & Vocal Spikes (5% -> 35%)
            # -------------------------------------------------------------
            logger.info(f"[Job #{job.id}] Stage 1: Audio Analysis on {video_path.name}")
            audio_samples, sample_rate = audio_analysis_service.extract_audio_samples(video_path)
            timestamps_audio, rms_curve = audio_analysis_service.compute_rms_energy_curve(
                audio_samples, sample_rate, window_ms=500
            )
            audio_events = audio_analysis_service.detect_excitement_events(
                timestamps_audio, rms_curve, threshold_sigma=2.0
            )

            # Persist detected audio events
            for ae in audio_events:
                db.add(
                    DetectedEvent(
                        recording_id=rec.id,
                        event_type=ae.event_type,
                        category="audio_reaction",
                        start_time=ae.start_time,
                        end_time=ae.end_time,
                        confidence=min(1.0, ae.intensity / 100.0),
                        intensity=ae.intensity,
                        description=f"Vocal excitement burst peaking at {ae.peak_time}s",
                    )
                )

            job.progress_percent = 35.0
            job.current_stage = "Stage 2: Visual Cut & Motion Action Analysis"
            db.commit()

            # Memory Hygiene: Free audio samples before visual processing
            del audio_samples
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            # -------------------------------------------------------------
            # STAGE 2: Visual Scene Cuts & Gameplay Action (35% -> 70%)
            # -------------------------------------------------------------
            logger.info(f"[Job #{job.id}] Stage 2: Visual Analysis on {video_path.name}")
            scene_cuts, times_vis, motion_curve, visual_events = (
                visual_analysis_service.analyze_video_motion_and_cuts(video_path, sample_fps=2.0)
            )

            # Persist detected visual events
            for ve in visual_events:
                db.add(
                    DetectedEvent(
                        recording_id=rec.id,
                        event_type=ve.event_type,
                        category="action",
                        start_time=ve.start_time,
                        end_time=ve.end_time,
                        confidence=min(1.0, ve.intensity / 100.0),
                        intensity=ve.intensity,
                        description=f"High motion gameplay action peaking at {ve.peak_time}s",
                    )
                )

            job.progress_percent = 70.0
            job.current_stage = "Stage 3: Facecam Detection & Spatial Locking"
            db.commit()

            # -------------------------------------------------------------
            # STAGE 3: Facecam Inspection & Metadata Summary (70% -> 100%)
            # -------------------------------------------------------------
            logger.info(f"[Job #{job.id}] Stage 3: Facecam Tracking on {video_path.name}")
            has_cam, cam_loc, cam_box = facecam_service.analyze_stream_facecam(video_path)

            job.result_summary = {
                "audio_events_count": len(audio_events),
                "visual_events_count": len(visual_events),
                "scene_cuts_count": len(scene_cuts),
                "has_facecam": has_cam,
                "facecam_location": cam_loc,
                "facecam_box": cam_box,
            }
            job.progress_percent = 100.0
            job.status = "completed"
            job.current_stage = "Feature extraction complete"
            job.completed_at = datetime.now(timezone.utc)

            rec_meta = dict(rec.metadata_json or {})
            rec_meta["facecam"] = {
                "has_facecam": has_cam,
                "location": cam_loc,
                "box": cam_box,
            }
            rec.metadata_json = rec_meta
            rec.status = "features_extracted"
            db.commit()
            db.refresh(job)

            logger.info(
                f"[Job #{job.id}] Feature extraction completed successfully: "
                f"{len(audio_events)} audio events, {len(visual_events)} action events, "
                f"Facecam={has_cam} ({cam_loc})."
            )
            return job

        except Exception as e:
            logger.error(f"[Job #{job.id}] Feature extraction failed: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return job


job_worker = JobWorker()
