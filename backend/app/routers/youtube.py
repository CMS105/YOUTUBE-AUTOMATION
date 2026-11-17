"""
YouTube Monitoring API Router.

Provides endpoints for YouTube API status, key verification,
streamer live status polling, and channel metadata inspection.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.youtube_monitor_service import youtube_monitor_service
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
