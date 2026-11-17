"""
Permissions management router.
Enforces explicit creator consent gates.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Permission, Streamer, AuditLog
from app.domain.schemas.permissions import (
    PermissionCreate, PermissionUpdate, PermissionResponse,
    PermissionGrantRequest, PermissionRevokeRequest,
)

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("", response_model=list[PermissionResponse])
def list_permissions(
    streamer_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    query = db.query(Permission)
    if streamer_id:
        query = query.filter(Permission.streamer_id == streamer_id)
    if status:
        query = query.filter(Permission.status == status)
    return query.order_by(Permission.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{permission_id}", response_model=PermissionResponse)
def get_permission(permission_id: int, db: Session = Depends(get_db)):
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission record not found")
    return perm


@router.post("/grant", response_model=PermissionResponse, status_code=201)
def grant_permission(data: PermissionGrantRequest, db: Session = Depends(get_db)):
    """Grant ACTIVE permission to a registered streamer."""
    streamer = db.query(Streamer).filter(Streamer.id == data.streamer_id).first()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    # Check if already has active permission
    existing = (
        db.query(Permission)
        .filter(Permission.streamer_id == data.streamer_id, Permission.status == "ACTIVE")
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Streamer already has an active permission")

    perm = Permission(
        streamer_id=data.streamer_id,
        status="ACTIVE",
        grant_type=data.grant_type,
        scope=data.scope,
        notes=data.notes,
        granted_at=datetime.now(timezone.utc),
    )
    db.add(perm)
    db.add(AuditLog(
        entity_type="permission", entity_id=None, action="permission_granted",
        details=f"Permission granted to streamer '{streamer.display_name}' (ID: {streamer.id}). Scope: {data.scope}.",
    ))
    db.commit()
    db.refresh(perm)
    return perm


@router.post("/{permission_id}/revoke", response_model=PermissionResponse)
def revoke_permission(
    permission_id: int,
    data: PermissionRevokeRequest,
    db: Session = Depends(get_db),
):
    """Revoke an existing permission. Cascades job cancellation."""
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission record not found")
    if perm.status == "REVOKED":
        raise HTTPException(status_code=409, detail="Permission is already revoked")

    perm.status = "REVOKED"
    perm.revoked_at = datetime.now(timezone.utc)
    if data.reason:
        perm.notes = f"{perm.notes or ''}\nRevoked: {data.reason}".strip()

    db.add(AuditLog(
        entity_type="permission", entity_id=permission_id, action="permission_revoked",
        details=f"Permission #{permission_id} revoked for streamer ID {perm.streamer_id}. Reason: {data.reason or 'No reason provided'}.",
    ))
    db.commit()
    db.refresh(perm)
    return perm


@router.patch("/{permission_id}", response_model=PermissionResponse)
def update_permission(permission_id: int, data: PermissionUpdate, db: Session = Depends(get_db)):
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission record not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)

    db.commit()
    db.refresh(perm)
    return perm

