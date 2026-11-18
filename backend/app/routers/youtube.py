"""
YouTube Monitoring API Router.

Provides endpoints for YouTube API status, key verification,
streamer live status polling, and channel metadata inspection.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LiveDiscovery
from app.services.youtube_monitor_service import youtube_monitor_service
from app.domain.schemas.discovery import (
    LiveDiscoveryResponse,
    LiveDiscoveryListResponse,
    PollDiscoveryRequest,
)
from app.core.config import settings

router = APIRouter(prefix="/youtube", tags=["YouTube Monitoring"])


class VerifyKeyRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Optional custom key to test; defaults to configured key")


@router.get("/status")
def get_youtube_status():
    """Returns current YouTube API connection status, masked key, and quota consumption."""
    return {
        "configured": settings.has_youtube_api,
        "key_hint": settings.mask_key(settings.YOUTUBE_API_KEY),
        "poll_interval_seconds": settings.YOUTUBE_POLL_INTERVAL_SECONDS,
        "quota": youtube_monitor_service.quota_tracker.get_status(),
        "policy_notice": "Strictly official YouTube Data API v3. Zero video scraping or extraction.",
    }


@router.post("/verify-key")
def verify_api_key(req: Optional[VerifyKeyRequest] = None):
    """
    Live verification of YouTube Data API v3 key using a lightweight 1-quota request.
    """
    test_key = req.api_key if req else None
    result = youtube_monitor_service.verify_api_key(test_key)
    return result


@router.post("/poll")
def poll_streamers_live_status(db: Session = Depends(get_db)):
    """
    Manually triggers a live status check across all active registered streamers.
    """
    if not settings.has_youtube_api:
        return {
            "status": "skipped",
            "message": "YouTube API key not configured. Offline mode active.",
            "streamers_checked": 0,
            "live_streams_detected": 0,
            "quota_status": youtube_monitor_service.quota_tracker.get_status(),
        }

    res = youtube_monitor_service.poll_streamers(db)
    return {
        "status": "completed",
        **res,
    }


@router.get("/channel/{channel_id}")
def get_channel_details(channel_id: str):
    """
    Retrieves official YouTube channel info (avatar, title, stats) via API.
    """
    info = youtube_monitor_service.fetch_channel_info(channel_id)
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Channel info not found or YouTube API unavailable for '{channel_id}'",
        )
    return info


# ---------------------------------------------------------------------------
# GLOBAL GTA 6 LIVESTREAM DISCOVERIES
# ---------------------------------------------------------------------------
@router.get("/discoveries", response_model=LiveDiscoveryListResponse)
def list_discoveries(
    live_status: Optional[str] = Query(None, description="Filter by live status: 'live', 'ended', 'unavailable'"),
    authorization_status: Optional[str] = Query(None, description="Filter: 'AUTHORIZED', 'AWAITING_AUTHORIZATION', 'REVOKED'"),
    recording_status: Optional[str] = Query(None, description="Filter: 'IDLE', 'RECORDING', 'RECORDED', 'PROCESSING', 'CLIPPED', 'FAILED'"),
    search: Optional[str] = Query(None, description="Search channel title or stream title"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns discovered public GTA 6 livestreams with filtering, search, and recording states.
    """
    query = db.query(LiveDiscovery)

    if live_status:
        query = query.filter(LiveDiscovery.live_status == live_status.lower())
    if authorization_status:
        query = query.filter(LiveDiscovery.authorization_status == authorization_status.upper())
    if recording_status:
        query = query.filter(LiveDiscovery.recording_status == recording_status.upper())
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (LiveDiscovery.title.ilike(search_filter))
            | (LiveDiscovery.channel_title.ilike(search_filter))
            | (LiveDiscovery.channel_id.ilike(search_filter))
        )

    total = query.count()
    items = query.order_by(LiveDiscovery.detected_at.desc()).offset(skip).limit(limit).all()

    live_count = db.query(LiveDiscovery).filter(LiveDiscovery.live_status == "live").count()
    authorized_count = db.query(LiveDiscovery).filter(LiveDiscovery.authorization_status == "AUTHORIZED").count()
    recording_count = db.query(LiveDiscovery).filter(LiveDiscovery.recording_status == "RECORDING").count()

    return {
        "items": items,
        "total": total,
        "live_count": live_count,
        "authorized_count": authorized_count,
        "recording_count": recording_count,
        "quota_status": youtube_monitor_service.quota_tracker.get_status(),
    }


@router.post("/discoveries/poll")
def poll_global_discoveries(
    req: Optional[PollDiscoveryRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Triggers an official YouTube Data API v3 search for active GTA 6 livestreams.
    """
    query = req.query if req else None
    max_results = req.max_results if req else 15

    result = youtube_monitor_service.discover_gta6_livestreams(
        db=db,
        query=query,
        max_results=max_results,
    )
    return result


@router.get("/discoveries/{discovery_id}", response_model=LiveDiscoveryResponse)
def get_discovery_detail(discovery_id: int, db: Session = Depends(get_db)):
    """
    Returns full details for a single discovered livestream.
    """
    disc = db.query(LiveDiscovery).filter(LiveDiscovery.id == discovery_id).first()
    if not disc:
        raise HTTPException(status_code=404, detail=f"Discovery #{discovery_id} not found.")
    return disc

