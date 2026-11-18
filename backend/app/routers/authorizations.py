"""
Creator Authorizations API Router.

Provides endpoints to manage explicit streamer authorization records,
configure approved video input feeds, and revoke permissions.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.creator_authorization_service import creator_authorization_service
from app.domain.schemas.discovery import (
    CreatorAuthorizationCreate,
    CreatorAuthorizationUpdate,
    CreatorAuthorizationResponse,
    CreatorAuthorizationListResponse,
    CreatorAuthorizationRevokeRequest,
)

router = APIRouter(prefix="/authorizations", tags=["Creator Authorizations"])


@router.get("", response_model=CreatorAuthorizationListResponse)
def list_authorizations(
    status: Optional[str] = Query(None, description="Filter: 'ACTIVE', 'PENDING', 'REVOKED', 'EXPIRED'"),
    search: Optional[str] = Query(None, description="Search creator name or channel ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns all creator authorization records with status counts and filtering.
    """
    items, total, active_count = creator_authorization_service.list_authorizations(
        db=db,
        status=status,
        search=search,
        skip=skip,
        limit=limit,
    )
    return {
        "items": items,
        "total": total,
        "active_count": active_count,
    }


@router.post("", response_model=CreatorAuthorizationResponse, status_code=201)
def authorize_creator(
    data: CreatorAuthorizationCreate,
    db: Session = Depends(get_db),
):
    """
    Grants or updates creator authorization for recording and clipping.
    Requires specifying an approved input source (RTMP, SRT, or OBS scene).
    """
    try:
        record = creator_authorization_service.authorize_creator(db=db, data=data)
        return record
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{auth_id}", response_model=CreatorAuthorizationResponse)
def get_authorization(auth_id: int, db: Session = Depends(get_db)):
    """
    Returns single authorization record by ID.
    """
    record = creator_authorization_service.get_by_id(db, auth_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Authorization #{auth_id} not found.")
    return record


@router.get("/channel/{channel_id}", response_model=CreatorAuthorizationResponse)
def get_authorization_by_channel(channel_id: str, db: Session = Depends(get_db)):
    """
    Returns authorization record for a specific channel ID.
    """
    record = creator_authorization_service.get_by_channel_id(db, channel_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No authorization record found for channel '{channel_id}'.")
    return record


@router.post("/{auth_id}/revoke", response_model=CreatorAuthorizationResponse)
def revoke_authorization(
    auth_id: int,
    req: CreatorAuthorizationRevokeRequest,
    db: Session = Depends(get_db),
):
    """
    Revokes creator authorization. Immediately aborts any active recording sessions.
    """
    try:
        record = creator_authorization_service.revoke_authorization(
            db=db,
            auth_id=auth_id,
            reason=req.reason,
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
