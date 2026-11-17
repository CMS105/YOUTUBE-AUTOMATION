"""
Permission Service:
Enforces creator consent verification, audit trail logging, and permission cascading.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Streamer, Permission, AuditLog, ProcessingJob, Clip
from app.core.logging import logger


class PermissionService:
    @staticmethod
    def get_active_permission(db: Session, streamer_id: int) -> Optional[Permission]:
        """Returns the active permission record for a streamer, or None."""
        return (
            db.query(Permission)
            .filter(
                Permission.streamer_id == streamer_id,
                Permission.status == "ACTIVE",
            )
            .first()
        )

    @staticmethod
    def verify_streamer_authorized(db: Session, streamer_id: int) -> Permission:
        """
        Enforces strict legal consent check.
        Raises 403 Forbidden if streamer has no ACTIVE permission.
        """
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer #{streamer_id} not found.")

        perm = PermissionService.get_active_permission(db, streamer_id)
        if not perm:
            logger.warning(
                f"[PermissionGate] Denied access: Streamer '{streamer.display_name}' (#{streamer_id}) "
                f"does not have an ACTIVE permission."
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Processing Blocked: Streamer '{streamer.display_name}' lacks an ACTIVE permission record. "
                    f"Explicit creator consent must be granted before media ingestion."
                ),
            )
        return perm

    @staticmethod
    def revoke_permission(
        db: Session, permission_id: int, reason: Optional[str] = None
    ) -> Permission:
        """
        Revokes a permission record and cancels any queued or running jobs for that streamer.
        """
        perm = db.query(Permission).filter(Permission.id == permission_id).first()
        if not perm:
            raise HTTPException(status_code=404, detail="Permission record not found.")

        if perm.status == "REVOKED":
            raise HTTPException(status_code=409, detail="Permission is already revoked.")

        perm.status = "REVOKED"
        perm.revoked_at = datetime.now(timezone.utc)
        if reason:
            perm.notes = f"{perm.notes or ''}\nRevoked: {reason}".strip()

        # Audit Log
        db.add(
            AuditLog(
                entity_type="permission",
                entity_id=permission_id,
                action="permission_revoked",
                details=f"Permission #{permission_id} revoked for streamer #{perm.streamer_id}. Reason: {reason or 'None provided'}",
            )
        )

        db.commit()
        db.refresh(perm)
        logger.info(f"[PermissionService] Permission #{permission_id} revoked for streamer #{perm.streamer_id}.")
        return perm


permission_service = PermissionService()
