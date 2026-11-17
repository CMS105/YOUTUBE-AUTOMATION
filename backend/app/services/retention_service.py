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


retention_service = RetentionService()
