"""
Automation Engine Service.

Coordinates periodic background tasks:
1. Livestream Discovery: periodically polls YouTube Data API for GTA 6 broadcasts.
2. Status Verification: checks if active discovered streams are still live.
3. Auto-Recording: automatically initiates OBS recording for discovered live streams
   with ACTIVE creator authorizations and configured inputs.
4. Auto-Stopping: detects when streams end or exceed MAX_RECORDING_DURATION_MINUTES,
   stops OBS, ingests video, and triggers AI highlight processing.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import LiveDiscovery, CreatorAuthorization, RecordingSession
from app.services.youtube_monitor_service import youtube_monitor_service
from app.services.creator_authorization_service import creator_authorization_service
from app.services.recording_manager_service import recording_manager_service
from app.services.obs_service import obs_client


class AutomationService:
    """
    Automated cycle executor for YouTube discovery, creator authorization verification,
    and hands-free OBS recording.
    """

    def __init__(self):
        self._last_discovery_time = 0.0
        self._last_status_check_time = 0.0

    def run_cycle(self, db: Session) -> Dict[str, Any]:
        """
        Executes one full automation cycle:
        - Discovery poll (if interval elapsed)
        - Live stream status refresh
        - Auto-start recording for authorized streams
        - Auto-stop recording if stream ended or max duration reached
        """
        now = time.time()
        results: Dict[str, Any] = {
            "timestamp": str(datetime.now(timezone.utc)),
            "discovery_performed": False,
            "status_check_performed": False,
            "recordings_started": 0,
            "recordings_stopped": 0,
        }

        # 1. Recover hanging sessions on first check
        recording_manager_service.recover_hanging_sessions(db)

        # 2. Discovery Poll (if enabled and interval elapsed)
        if settings.AUTO_DISCOVERY_ENABLED:
            if (now - self._last_discovery_time) >= settings.YOUTUBE_DISCOVERY_INTERVAL_SECONDS:
                disc_res = youtube_monitor_service.discover_gta6_livestreams(db)
                self._last_discovery_time = now
                results["discovery_performed"] = True
                results["discovery_summary"] = disc_res

        # 3. Stream Status Verification (every 60s)
        if (now - self._last_status_check_time) >= 60.0:
            status_res = youtube_monitor_service.verify_active_discoveries_status(db)
            self._last_status_check_time = now
            results["status_check_performed"] = True
            results["status_summary"] = status_res

        # 4. Check active recording session (Auto-Stop conditions)
        active_session = recording_manager_service.get_active_session(db)
        if active_session:
            should_stop = False
            stop_reason = ""

            # Check if duration exceeded MAX_RECORDING_DURATION_MINUTES
            started_ts = active_session.started_at.replace(tzinfo=timezone.utc).timestamp()
            elapsed_minutes = (now - started_ts) / 60.0
            if elapsed_minutes >= settings.MAX_RECORDING_DURATION_MINUTES:
                should_stop = True
                stop_reason = f"Max recording duration reached ({elapsed_minutes:.1f} mins >= {settings.MAX_RECORDING_DURATION_MINUTES} mins)."

            # Check if the stream has ended
            if not should_stop and active_session.discovery_id:
                disc = db.query(LiveDiscovery).filter(LiveDiscovery.id == active_session.discovery_id).first()
                if disc and disc.live_status in ["ended", "unavailable"]:
                    should_stop = True
                    stop_reason = f"Live stream ended ({disc.live_status})."

            if should_stop:
                try:
                    logger.info(f"[Automation] Auto-stopping session #{active_session.id}: {stop_reason}")
                    recording_manager_service.stop_session(
                        db=db,
                        session_id=active_session.session_id,
                        reason=stop_reason,
                        auto_process=settings.AUTO_PROCESS_AFTER_RECORDING,
                    )
                    results["recordings_stopped"] += 1
                except Exception as e:
                    logger.error(f"[Automation] Failed to auto-stop session #{active_session.id}: {e}")

        # 5. Auto-Start Recording for authorized streams (if enabled and no session currently active)
        if settings.AUTO_RECORD_AUTHORIZED and not active_session:
            # Find eligible live discoveries with AUTHORIZED status and IDLE recording status
            eligible_discoveries = (
                db.query(LiveDiscovery)
                .filter(
                    LiveDiscovery.live_status == "live",
                    LiveDiscovery.authorization_status == "AUTHORIZED",
                    LiveDiscovery.recording_status == "IDLE",
                )
                .all()
            )

            for discovery in eligible_discoveries:
                is_auth, reason, auth_rec = creator_authorization_service.verify_recording_eligibility(db, discovery.channel_id)
                if is_auth and auth_rec:
                    try:
                        logger.info(f"[Automation] Auto-starting OBS recording for authorized discovery #{discovery.id} ({discovery.channel_title}).")
                        recording_manager_service.start_session(
                            db=db,
                            channel_id=discovery.channel_id,
                            video_id=discovery.video_id,
                            discovery_id=discovery.id,
                            custom_source=auth_rec.authorized_source,
                        )
                        results["recordings_started"] += 1
                        break  # Record one stream at a time to prevent CPU/GPU overload
                    except Exception as e:
                        logger.warning(f"[Automation] Auto-recording initiation failed for '{discovery.channel_title}': {e}")

        return results


automation_service = AutomationService()
