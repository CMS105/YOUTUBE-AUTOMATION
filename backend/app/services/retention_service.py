"""
Retention and Storage Policy Service.
Manages disk quota enforcement, temporary cache cleanup, and raw video retention.
"""

import time
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models import Recording, Clip, AuditLog


class RetentionService:
    @staticmethod
    def cleanup_temp_directory(max_age_seconds: int = 3600) -> int:
        """Removes temporary files older than max_age_seconds."""
        temp_dir = Path(settings.TEMP_DIR)
        if not temp_dir.exists():
            return 0

        now = time.time()
        purged_count = 0
        for f in temp_dir.glob("*"):
            if f.is_file():
                try:
                    if now - f.stat().st_mtime > max_age_seconds:
                        f.unlink()
                        purged_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {f}: {e}")
        if purged_count > 0:
            logger.info(f"[RetentionService] Purged {purged_count} temporary scratch files.")
        return purged_count

    @staticmethod
    def apply_retention_policy(db: Session, max_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Deletes raw recordings older than max_days while keeping rendered clips intact.
        """
        days = max_days if max_days is not None else settings.MAX_RECORDING_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        old_recs = db.query(Recording).filter(Recording.ingested_at < cutoff).all()
        purged_count = 0
        bytes_freed = 0

        for rec in old_recs:
            file_path = Path(rec.file_path)
            if file_path.exists():
                try:
                    bytes_freed += file_path.stat().st_size
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"Could not remove old recording file {file_path}: {e}")
            rec.status = "archived_purged"
            purged_count += 1

        if purged_count > 0:
            db.add(
                AuditLog(
                    entity_type="retention",
                    entity_id=None,
                    action="purge_recordings",
                    details=f"Purged {purged_count} raw recordings older than {days} days ({round(bytes_freed / (1024*1024), 1)} MB freed).",
                )
            )
            db.commit()

        logger.info(
            f"[RetentionService] Retention check complete. Purged: {purged_count} files, "
            f"Freed: {round(bytes_freed / (1024*1024), 2)} MB."
        )
        return {
            "purged_count": purged_count,
            "megabytes_freed": round(bytes_freed / (1024 * 1024), 2),
            "retention_days_threshold": days,
        }

    @staticmethod
    def get_storage_usage(db: Session) -> Dict[str, Any]:
        """Calculates storage usage across recordings, clips, thumbnails, and temp."""
        total_recs = db.query(Recording).count()
        total_clips = db.query(Clip).count()

        def dir_size(path_str: str) -> int:
            p = Path(path_str)
            if not p.exists():
                return 0
            return sum(f.stat().st_size for f in p.glob("**/*") if f.is_file())

        recs_bytes = dir_size(settings.RECORDINGS_DIR)
        clips_bytes = dir_size(settings.CLIPS_DIR)
        thumbs_bytes = dir_size(settings.THUMBNAILS_DIR)
        temp_bytes = dir_size(settings.TEMP_DIR)
        total_bytes = recs_bytes + clips_bytes + thumbs_bytes + temp_bytes

        total_mb = round(total_bytes / (1024 * 1024), 2)
        total_gb = round(total_bytes / (1024 * 1024 * 1024), 3)

        return {
            "total_quota_gb": settings.MAX_STORAGE_QUOTA_GB,
            "used_storage_gb": total_gb,
            "used_storage_mb": total_mb,
            "used_percentage": round((total_gb / settings.MAX_STORAGE_QUOTA_GB) * 100, 2),
            "recordings_mb": round(recs_bytes / (1024 * 1024), 2),
            "clips_mb": round(clips_bytes / (1024 * 1024), 2),
            "thumbnails_mb": round(thumbs_bytes / (1024 * 1024), 2),
            "temp_mb": round(temp_bytes / (1024 * 1024), 2),
            "total_recordings": total_recs,
            "total_clips": total_clips,
            "recordings_dir": settings.RECORDINGS_DIR,
            "clips_dir": settings.CLIPS_DIR,
        }


retention_service = RetentionService()
