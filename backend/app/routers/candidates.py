"""
Dedicated Candidate API Router.

Provides endpoints to list, inspect, approve, reject, and generate
highlight clip candidates.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClipCandidate, Recording, ProcessingJob, Permission
from app.domain.schemas.clips import (
    ClipCandidateResponse,
    CandidateListResponse,
    CandidateApproveRequest,
    ProcessingJobResponse,
)
from app.services.candidate_service import candidate_service
from app.core.logging import logger

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.get("", response_model=CandidateListResponse)
def list_candidates(
    recording_id: Optional[int] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    min_score: Optional[float] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List ranked clip candidates with optional filtering and pagination."""
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit

    query = db.query(ClipCandidate)
    if recording_id:
        query = query.filter(ClipCandidate.recording_id == recording_id)
    if status:
        query = query.filter(ClipCandidate.status == status)
    if category:
        query = query.filter(ClipCandidate.event_category.ilike(f"%{category}%"))
    if min_score is not None:
        query = query.filter(ClipCandidate.score_composite >= min_score)

    total = query.count()
    items = (
        query.order_by(ClipCandidate.score_composite.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return CandidateListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{candidate_id}", response_model=ClipCandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Retrieve details for a single clip candidate."""
    cand = db.query(ClipCandidate).filter(ClipCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Clip candidate not found")
    return cand


@router.post("/generate/{recording_id}", response_model=list[ClipCandidateResponse], status_code=201)
def generate_candidates(
    recording_id: int,
    count: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Trigger candidate window synthesis, multimodal scoring, and Temporal NMS
    for an analyzed recording.
    """
    count = int(getattr(count, "default", count)) if not isinstance(count, int) else count

    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Verify streamer permission
    perm = (
        db.query(Permission)
        .filter(Permission.streamer_id == rec.streamer_id, Permission.status == "ACTIVE")
        .first()
    )
    if not perm:
        raise HTTPException(
            status_code=403,
            detail="Cannot generate candidates: Streamer does not have an ACTIVE permission grant.",
        )

    try:
        candidates = candidate_service.generate_candidates_for_recording(
            db=db,
            recording_id=recording_id,
            target_count=count,
        )
        return candidates
    except Exception as e:
        logger.error(f"[CandidateRouter] Failed to generate candidates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Candidate generation failed: {str(e)}",
        )


@router.post("/{candidate_id}/approve", response_model=ProcessingJobResponse)
def approve_candidate(
    candidate_id: int,
    req: CandidateApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Approve candidate highlight for rendering. Sets status to 'approved' and
    enqueues an FFmpeg vertical clipping job.
    """
    cand = db.query(ClipCandidate).filter(ClipCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Clip candidate not found")

    rec = db.query(Recording).filter(Recording.id == cand.recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Associated recording not found")

    # Verify permission gate
    perm = (
        db.query(Permission)
        .filter(Permission.streamer_id == rec.streamer_id, Permission.status == "ACTIVE")
        .first()
    )
    if not perm:
        raise HTTPException(
            status_code=403,
            detail="Cannot approve: Streamer does not have an ACTIVE permission grant.",
        )

    # Update candidate status
    cand.status = "approved"

    # Enqueue render processing job
    chosen_title = req.custom_title
    if not chosen_title and cand.suggested_titles:
        chosen_title = cand.suggested_titles[0]
    if not chosen_title:
        chosen_title = f"GTA 6 Highlight #{cand.id}"

    job = ProcessingJob(
        recording_id=rec.id,
        job_type="render_clip",
        status="queued",
        progress_percent=0.0,
        result_summary={
            "candidate_id": cand.id,
            "preset": req.preset,
            "title": chosen_title,
            "start_time": cand.start_time,
            "end_time": cand.end_time,
            "has_facecam": cand.has_facecam,
            "facecam_region": cand.facecam_region,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(cand)
    db.refresh(job)

    logger.info(f"[CandidateRouter] Candidate #{cand.id} approved for rendering with preset '{req.preset}'. Job #{job.id} enqueued.")
    return job


@router.post("/{candidate_id}/reject", response_model=ClipCandidateResponse)
def reject_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Reject a clip candidate. Sets status to 'rejected'."""
    cand = db.query(ClipCandidate).filter(ClipCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Clip candidate not found")

    cand.status = "rejected"
    db.commit()
    db.refresh(cand)
    logger.info(f"[CandidateRouter] Candidate #{cand.id} marked as rejected.")
    return cand
