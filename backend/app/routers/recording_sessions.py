"""
Recording Sessions & Automation API Router.

Provides endpoints to list recording sessions, retrieve session diagnostics,
and trigger manual automation cycles.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.recording_manager_service import recording_manager_service
from app.services.automation_service import automation_service
from app.domain.schemas.discovery import (
    RecordingSessionResponse,
    RecordingSessionListResponse,
)

router = APIRouter(prefix="/recording-sessions", tags=["Recording Sessions"])


@router.get("", response_model=RecordingSessionListResponse)
def list_recording_sessions(
    status: Optional[str] = Query(None, description="Filter: 'recording', 'completed', 'failed', 'aborted'"),
    channel_id: Optional[str] = Query(None, description="Filter by creator channel ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns recorded and active broadcast sessions with duration and file metrics.
    """
    items, total, active_count = recording_manager_service.list_sessions(
        db=db,
        status=status,
        channel_id=channel_id,
        skip=skip,
        limit=limit,
    )
    return {
        "items": items,
        "total": total,
        "active_sessions": active_count,
    }


@router.get("/{session_id}", response_model=RecordingSessionResponse)
def get_recording_session(session_id: str, db: Session = Depends(get_db)):
    """
    Returns single recording session details by ID or session UUID.
    """
    session = recording_manager_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Recording session '{session_id}' not found.")
    return session


@router.post("/{session_id}/stop", response_model=RecordingSessionResponse)
def stop_recording_session(session_id: str, db: Session = Depends(get_db)):
    """
    Stops a specific recording session by ID or UUID.
    """
    try:
        session, _ = recording_manager_service.stop_session(
            db=db,
            session_id=session_id,
            reason="manual_session_stop",
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/process")
def process_recording_session(session_id: str, db: Session = Depends(get_db)):
    """
    Triggers the end-to-end AI clipping pipeline on a completed recording session.
    """
    session = recording_manager_service.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Recording session '{session_id}' not found.")
    if not session.recording_id:
        raise HTTPException(status_code=400, detail="Session does not have an ingested recording file to process.")

    job_id = recording_manager_service.trigger_ai_pipeline(
        db=db,
        session_id=session.id,
        recording_id=session.recording_id,
    )
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to initiate AI processing pipeline.")

    return {
        "status": "processing_started",
        "session_id": session.session_id,
        "recording_id": session.recording_id,
        "job_id": job_id,
        "message": "AI feature extraction, candidate scoring, and vertical rendering initiated.",
    }


@router.post("/automation/run")
def trigger_automation_cycle(db: Session = Depends(get_db)):
    """
    Manually triggers one complete automation cycle:
    - Discovery poll
    - Stream status verification
    - Auto-recording start for authorized inputs
    - Auto-recording stop for ended streams
    """
    summary = automation_service.run_cycle(db)
    return {
        "status": "cycle_executed",
        **summary,
    }
