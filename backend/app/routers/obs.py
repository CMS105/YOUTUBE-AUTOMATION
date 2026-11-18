"""
OBS Studio Integration Router.

Provides endpoints to monitor OBS connection health, verify recording status,
and trigger recording start/stop via OBS WebSocket protocol v5.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.obs_service import obs_client
from app.services.recording_manager_service import recording_manager_service
from app.domain.schemas.discovery import (
    OBSStatusResponse,
    OBSConnectRequest,
    OBSRecordStartRequest,
    OBSRecordStopResponse,
    RecordingSessionResponse,
)

router = APIRouter(prefix="/obs", tags=["OBS Studio Recording"])


@router.get("/status", response_model=OBSStatusResponse)
def get_obs_status():
    """
    Returns real-time connection status with OBS Studio, active recording metrics,
    and storage disk space availability.
    """
    status = obs_client.get_full_status()
    return status


@router.post("/connect", response_model=OBSStatusResponse)
def connect_obs(req: Optional[OBSConnectRequest] = None):
    """
    Attempts to establish an authenticated WebSocket v5 connection with OBS Studio.
    """
    if req and req.host:
        obs_client.host = req.host
    if req and req.port:
        obs_client.port = req.port
    if req and req.password is not None:
        obs_client.password = req.password

    connected, err = obs_client.connect()
    status = obs_client.get_full_status()
    if not connected:
        status["error"] = err
    return status


@router.post("/recording/start", response_model=RecordingSessionResponse)
def start_recording(
    req: OBSRecordStartRequest,
    db: Session = Depends(get_db),
):
    """
    Initiates OBS recording for an authorized creator's input feed.
    Rejects immediately if:
    - Creator authorization is not ACTIVE
    - No approved input feed is configured
    - OBS is unreachable or disk space is insufficient (< 5GB free)
    """
    try:
        session = recording_manager_service.start_session(
            db=db,
            channel_id=req.channel_id,
            video_id=req.video_id,
            discovery_id=req.discovery_id,
            custom_source=req.custom_source,
        )
        return session
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recording/stop", response_model=OBSRecordStopResponse)
def stop_recording(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Stops the active OBS recording session, saves the output path,
    ingests the recording into PostgreSQL, and auto-launches the AI clipping pipeline.
    """
    try:
        session, rec_id = recording_manager_service.stop_session(
            db=db,
            session_id=session_id,
            reason="api_request",
        )
        return {
            "success": True,
            "session_id": session.session_id,
            "output_path": session.obs_output_path,
            "duration_seconds": session.duration_seconds,
            "file_size_bytes": session.file_size_bytes,
            "message": f"Recording stopped successfully. Ingested as Recording #{rec_id} (AI Pipeline queued)." if rec_id else "Recording stopped.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
