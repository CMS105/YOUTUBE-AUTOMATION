"""
Streamers CRUD router.
Adapted from API-TASKFLOW (demo123) router patterns.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.models import Streamer, Permission, AuditLog
from app.domain.schemas.streamers import (
    StreamerCreate, StreamerUpdate, StreamerResponse, StreamerListResponse,
)

router = APIRouter(prefix="/streamers", tags=["Streamers"])


def _enrich_response(streamer: Streamer, db: Session) -> StreamerResponse:
    """Builds StreamerResponse with latest permission status."""
    perm = (
        db.query(Permission)
        .filter(Permission.streamer_id == streamer.id)
        .order_by(Permission.created_at.desc())
        .first()
    )
    return StreamerResponse(
        id=streamer.id,
        uuid=streamer.uuid,
        display_name=streamer.display_name,
        platform=streamer.platform,
        channel_id=streamer.channel_id,
        channel_url=streamer.channel_url,
        avatar_url=streamer.avatar_url,
        description=streamer.description,
        is_active=streamer.is_active,
        permission_status=perm.status if perm else None,
        created_at=streamer.created_at,
        updated_at=streamer.updated_at,
    )


@router.get("", response_model=StreamerListResponse)
def list_streamers(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    query = db.query(Streamer)
    if is_active is not None:
        query = query.filter(Streamer.is_active == is_active)
    if search:
        query = query.filter(Streamer.display_name.ilike(f"%{search}%"))

    total = query.count()
    streamers = query.order_by(Streamer.created_at.desc()).offset(skip).limit(limit).all()

    return StreamerListResponse(
        items=[_enrich_response(s, db) for s in streamers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{streamer_id}", response_model=StreamerResponse)
def get_streamer(streamer_id: int, db: Session = Depends(get_db)):
    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    return _enrich_response(streamer, db)


@router.post("", response_model=StreamerResponse, status_code=201)
def create_streamer(data: StreamerCreate, db: Session = Depends(get_db)):
    streamer = Streamer(**data.model_dump())
    db.add(streamer)
    db.commit()
    db.refresh(streamer)

    # Audit log
    db.add(AuditLog(entity_type="streamer", entity_id=streamer.id, action="created",
                     details=f"Streamer '{streamer.display_name}' registered."))
    db.commit()

    return _enrich_response(streamer, db)


@router.patch("/{streamer_id}", response_model=StreamerResponse)
def update_streamer(streamer_id: int, data: StreamerUpdate, db: Session = Depends(get_db)):
    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(streamer, field, value)

    db.commit()
    db.refresh(streamer)
    return _enrich_response(streamer, db)


@router.delete("/{streamer_id}")
def delete_streamer(streamer_id: int, db: Session = Depends(get_db)):
    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    name = streamer.display_name
    db.delete(streamer)
    db.add(AuditLog(entity_type="streamer", entity_id=streamer_id, action="deleted",
                     details=f"Streamer '{name}' removed."))
    db.commit()
    return {"status": "deleted", "message": f"Streamer '{name}' and all associated data removed."}

