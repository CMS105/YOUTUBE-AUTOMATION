"""
Creator Authorization Service.

Manages explicit creator permissions for video recording and short-form clipping.
Ensures zero unauthorized streams are recorded by enforcing:
1. Active status check
2. Expiry check
3. Explicit authorized video input source configuration
4. Audit logging of all grants, updates, and revocations.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import (
    CreatorAuthorization, LiveDiscovery, Streamer,
    Permission, AuditLog, RecordingSession
)
from app.domain.schemas.discovery import (
    CreatorAuthorizationCreate,
    CreatorAuthorizationUpdate,
)


class CreatorAuthorizationService:
    """
    Handles creator permission records, input source validation, and audit tracking.
    """

    def list_authorizations(
        self,
        db: Session,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[CreatorAuthorization], int, int]:
        """Lists authorizations with optional filtering by status and creator name."""
        query = db.query(CreatorAuthorization)
        if status:
            query = query.filter(CreatorAuthorization.status == status.upper())
        if search:
            query = query.filter(
                (CreatorAuthorization.creator_name.ilike(f"%{search}%"))
                | (CreatorAuthorization.channel_id.ilike(f"%{search}%"))
            )

        total = query.count()
        active_count = db.query(CreatorAuthorization).filter(CreatorAuthorization.status == "ACTIVE").count()
        items = query.order_by(CreatorAuthorization.updated_at.desc()).offset(skip).limit(limit).all()
        return items, total, active_count

    def get_by_id(self, db: Session, auth_id: int) -> Optional[CreatorAuthorization]:
        return db.query(CreatorAuthorization).filter(CreatorAuthorization.id == auth_id).first()

    def get_by_channel_id(self, db: Session, channel_id: str) -> Optional[CreatorAuthorization]:
        return db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id == channel_id).first()

    def authorize_creator(
        self,
        db: Session,
        data: CreatorAuthorizationCreate,
    ) -> CreatorAuthorization:
        """
        Creates or updates a creator authorization record.
        Automatically syncs status to any matching LiveDiscovery records.
        """
        existing = self.get_by_channel_id(db, data.channel_id)

        # Check or auto-create matching Streamer record
        matching_streamer = db.query(Streamer).filter(Streamer.channel_id == data.channel_id).first()
        if not matching_streamer:
            matching_streamer = Streamer(
                channel_id=data.channel_id,
                display_name=data.creator_name,
                platform="youtube",
                is_active=(data.status == "ACTIVE"),
            )
            db.add(matching_streamer)
            db.flush()

        streamer_id = matching_streamer.id
        now = datetime.now(timezone.utc)

        if existing:
            existing.creator_name = data.creator_name
            existing.authorized_source = data.authorized_source
            existing.allowed_scope = data.allowed_scope
            existing.notes = data.notes
            existing.status = data.status
            existing.authorized_at = now if data.status == "ACTIVE" else existing.authorized_at
            existing.expires_at = data.expires_at
            existing.revoked_at = None
            existing.revocation_reason = None
            existing.streamer_id = streamer_id
            record = existing
            action = "creator_authorization_updated"
        else:
            record = CreatorAuthorization(
                channel_id=data.channel_id,
                creator_name=data.creator_name,
                status=data.status,
                authorized_source=data.authorized_source,
                allowed_scope=data.allowed_scope,
                authorized_at=now if data.status == "ACTIVE" else None,
                expires_at=data.expires_at,
                notes=data.notes,
                streamer_id=streamer_id,
            )
            db.add(record)
            action = "creator_authorization_created"

        db.flush()

        # Sync Permission record for the Streamer
        perm = db.query(Permission).filter(Permission.streamer_id == streamer_id).first()
        if not perm:
            perm = Permission(
                streamer_id=streamer_id,
                status=data.status,
                grant_type="manual",
                granted_at=now if data.status == "ACTIVE" else None,
                expires_at=data.expires_at,
                scope=data.allowed_scope or "clip_creation",
                notes=f"Synced from CreatorAuthorization #{record.id}",
            )
            db.add(perm)
        else:
            perm.status = data.status
            if data.status == "ACTIVE":
                perm.granted_at = now
                perm.revoked_at = None
            elif data.status == "REVOKED":
                perm.revoked_at = now
            perm.expires_at = data.expires_at

        # Sync matching LiveDiscovery entries
        target_status = "AUTHORIZED" if data.status == "ACTIVE" else "AWAITING_AUTHORIZATION"
        db.query(LiveDiscovery).filter(LiveDiscovery.channel_id == data.channel_id).update(
            {"authorization_status": target_status, "updated_at": now}
        )

        # Audit log
        db.add(
            AuditLog(
                entity_type="creator_authorization",
                entity_id=record.id,
                action=action,
                details=f"Creator '{data.creator_name}' ({data.channel_id}) authorization status set to {data.status}. Approved input: '{data.authorized_source}'.",
            )
        )
        db.commit()
        db.refresh(record)
        logger.info(f"[CreatorAuth] Successfully saved authorization #{record.id} for '{record.creator_name}' (Status: {record.status}).")
        return record

    def revoke_authorization(
        self,
        db: Session,
        auth_id: int,
        reason: str,
    ) -> CreatorAuthorization:
        """
        Revokes an authorization, immediately halting any active recording sessions.
        """
        record = self.get_by_id(db, auth_id)
        if not record:
            raise ValueError(f"Authorization #{auth_id} not found.")

        now = datetime.now(timezone.utc)
        record.status = "REVOKED"
        record.revoked_at = now
        record.revocation_reason = reason

        # Update matching live discoveries to REVOKED
        db.query(LiveDiscovery).filter(LiveDiscovery.channel_id == record.channel_id).update(
            {"authorization_status": "REVOKED", "updated_at": now}
        )

        # Abort any active recording sessions for this channel
        active_sessions = (
            db.query(RecordingSession)
            .filter(RecordingSession.channel_id == record.channel_id, RecordingSession.status == "recording")
            .all()
        )
        for s in active_sessions:
            s.status = "aborted"
            s.ended_at = now
            s.error_message = f"Recording aborted: Creator authorization revoked ({reason})."

        # Also sync Permission table if linked to a Streamer
        if record.streamer_id:
            db.query(Permission).filter(Permission.streamer_id == record.streamer_id).update({
                "status": "REVOKED",
                "revoked_at": now,
            })

        db.add(
            AuditLog(
                entity_type="creator_authorization",
                entity_id=record.id,
                action="creator_authorization_revoked",
                details=f"Authorization revoked for '{record.creator_name}' ({record.channel_id}): {reason}.",
            )
        )
        db.commit()
        db.refresh(record)
        logger.warning(f"[CreatorAuth] Authorization #{record.id} REVOKED for '{record.creator_name}'. Reason: {reason}")
        return record

    def verify_recording_eligibility(
        self,
        db: Session,
        channel_id: str,
    ) -> Tuple[bool, str, Optional[CreatorAuthorization]]:
        """
        Strict permission gate: Checks if recording is authorized.
        Requires:
        1. Authorization record exists
        2. Status is ACTIVE
        3. Expiry date not passed
        4. Valid authorized_source configured
        """
        auth = self.get_by_channel_id(db, channel_id)

        # Fallback check on Streamer & Permission tables
        if not auth:
            streamer = db.query(Streamer).filter(Streamer.channel_id == channel_id).first()
            if streamer:
                perm = (
                    db.query(Permission)
                    .filter(Permission.streamer_id == streamer.id, Permission.status == "ACTIVE")
                    .first()
                )
                if perm:
                    # Synthesize CreatorAuthorization from Streamer permission
                    auth = self.authorize_creator(
                        db,
                        CreatorAuthorizationCreate(
                            channel_id=channel_id,
                            creator_name=streamer.display_name,
                            authorized_source=f"OBS:WindowCapture_{streamer.display_name}",
                            allowed_scope="clip_creation",
                            notes=f"Auto-bridged from Streamer #{streamer.id} Permission #{perm.id}",
                            status="ACTIVE",
                        ),
                    )

        if not auth:
            return False, f"Creator ({channel_id}) has no authorization record on file.", None

        if auth.status != "ACTIVE":
            return False, f"Creator authorization status is '{auth.status}' (must be ACTIVE).", auth

        if auth.expires_at:
            now = datetime.now(timezone.utc)
            if now > auth.expires_at.replace(tzinfo=timezone.utc if auth.expires_at.tzinfo is None else auth.expires_at.tzinfo):
                auth.status = "EXPIRED"
                db.commit()
                return False, "Creator authorization has expired.", auth

        if not auth.authorized_source or not auth.authorized_source.strip():
            return False, "Creator is authorized, but no approved video input source (RTMP/SRT/Capture) is configured.", auth

        return True, "Authorized and input source configured.", auth


creator_authorization_service = CreatorAuthorizationService()
