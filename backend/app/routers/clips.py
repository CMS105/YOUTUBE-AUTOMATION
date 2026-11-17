"""
Clips, Candidates, Recordings and Processing Jobs router.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from pathlib import Path

from app.database import get_db
from app.models import (
    Clip, ClipCandidate, Recording, ProcessingJob, Thumbnail,
    Streamer, Permission, AuditLog,
)
from app.domain.schemas.clips import (
    ClipResponse, ClipListResponse, ClipUpdateRequest,
    ClipCandidateResponse, RecordingResponse,
    ProcessingJobResponse, ProcessingJobListResponse, ProcessingJobCreate,
    DashboardStats,
)
from app.core.config import settings

router = APIRouter(tags=["Clips & Processing"])


# --- RECORDINGS ---
@router.get("/recordings", response_model=list[RecordingResponse], tags=["Recordings"])
def list_recordings(
    streamer_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    query = db.query(Recording)
    if streamer_id:
        query = query.filter(Recording.streamer_id == streamer_id)
    if status:
        query = query.filter(Recording.status == status)
    return query.order_by(Recording.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/recordings/{recording_id}", response_model=RecordingResponse, tags=["Recordings"])
def get_recording(recording_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    return rec


# --- CLIP CANDIDATES ---
@router.get("/candidates", response_model=list[ClipCandidateResponse], tags=["Candidates"])
def list_candidates(
    recording_id: Optional[int] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    query = db.query(ClipCandidate)
    if recording_id:
        query = query.filter(ClipCandidate.recording_id == recording_id)
    if status:
        query = query.filter(ClipCandidate.status == status)
    if min_score is not None:
        query = query.filter(ClipCandidate.score_composite >= min_score)
    return query.order_by(ClipCandidate.score_composite.desc()).offset(skip).limit(limit).all()


# --- CLIPS ---
@router.get("/clips", response_model=ClipListResponse, tags=["Clips"])
def list_clips(
    search: Optional[str] = None,
    preset: Optional[str] = None,
    category: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    min_score: Optional[float] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    query = db.query(Clip)
    if search:
        query = query.filter(Clip.title.ilike(f"%{search}%"))
    if preset:
        query = query.filter(Clip.preset == preset)
    if category:
        query = query.filter(Clip.event_category.ilike(f"%{category}%"))
    if is_favorite is not None:
        query = query.filter(Clip.is_favorite == is_favorite)
    if min_score is not None:
        query = query.filter(Clip.score >= min_score)

    total = query.count()

    sort_col = getattr(Clip, sort_by, Clip.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    clips = query.offset(skip).limit(limit).all()

    items = []
    for clip in clips:
        resp = ClipResponse.model_validate(clip)
        # Enrich with streamer name via candidate -> recording -> streamer
        try:
            cand = db.query(ClipCandidate).filter(ClipCandidate.id == clip.candidate_id).first()
            if cand:
                rec = db.query(Recording).filter(Recording.id == cand.recording_id).first()
                if rec:
                    streamer = db.query(Streamer).filter(Streamer.id == rec.streamer_id).first()
                    if streamer:
                        resp.streamer_name = streamer.display_name
        except Exception:
            pass
        # Thumbnail URL
        thumb = db.query(Thumbnail).filter(Thumbnail.clip_id == clip.id, Thumbnail.is_primary == True).first()
        if thumb:
            resp.thumbnail_url = f"/api/v1/clips/{clip.id}/thumbnail"
        resp.download_url = f"/api/v1/clips/{clip.id}/download"
        items.append(resp)

    return ClipListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/clips/{clip_id}", response_model=ClipResponse, tags=["Clips"])
def get_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return ClipResponse.model_validate(clip)


@router.patch("/clips/{clip_id}", response_model=ClipResponse, tags=["Clips"])
def update_clip(clip_id: int, data: ClipUpdateRequest, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(clip, field, value)
    db.commit()
    db.refresh(clip)
    return ClipResponse.model_validate(clip)


@router.get("/clips/{clip_id}/download", tags=["Clips"])
def download_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    file_path = Path(clip.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found on disk")
    clip.download_count += 1
    db.commit()
    return FileResponse(
        path=str(file_path),
        filename=clip.file_name,
        media_type="video/mp4",
    )


@router.get("/clips/{clip_id}/thumbnail", tags=["Clips"])
def get_clip_thumbnail(clip_id: int, db: Session = Depends(get_db)):
    thumb = db.query(Thumbnail).filter(Thumbnail.clip_id == clip_id, Thumbnail.is_primary == True).first()
    if not thumb:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    file_path = Path(thumb.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found on disk")
    return FileResponse(path=str(file_path), media_type="image/jpeg")


@router.delete("/clips/{clip_id}", tags=["Clips"])
def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    # Attempt filesystem cleanup
    try:
        file_path = Path(clip.file_path)
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass
    db.delete(clip)
    db.commit()
    return {"status": "deleted", "message": f"Clip '{clip.title}' removed."}


# --- PROCESSING JOBS ---
@router.get("/jobs", response_model=ProcessingJobListResponse, tags=["Jobs"])
def list_jobs(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    skip = int(getattr(skip, "default", skip)) if not isinstance(skip, int) else skip
    limit = int(getattr(limit, "default", limit)) if not isinstance(limit, int) else limit
    query = db.query(ProcessingJob)
    if status:
        query = query.filter(ProcessingJob.status == status)
    total = query.count()
    items = query.order_by(ProcessingJob.created_at.desc()).offset(skip).limit(limit).all()
    return ProcessingJobListResponse(items=items, total=total)


@router.post("/jobs", response_model=ProcessingJobResponse, status_code=201, tags=["Jobs"])
def create_job(data: ProcessingJobCreate, db: Session = Depends(get_db)):
    rec = db.query(Recording).filter(Recording.id == data.recording_id).first()
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
            detail="Cannot process: streamer does not have an ACTIVE permission. Grant permission first.",
        )

    job = ProcessingJob(
        recording_id=data.recording_id,
        job_type=data.job_type,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/cancel", response_model=ProcessingJobResponse, tags=["Jobs"])
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail=f"Job is already {job.status}")
    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return job


# --- DASHBOARD STATS ---
@router.get("/dashboard/stats", response_model=DashboardStats, tags=["Dashboard"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_streamers = db.query(Streamer).count()
    active_perms = db.query(Permission).filter(Permission.status == "ACTIVE").count()
    total_recs = db.query(Recording).count()
    total_clips = db.query(Clip).count()
    total_cands = db.query(ClipCandidate).count()
    active_jobs = db.query(ProcessingJob).filter(ProcessingJob.status.in_(["queued", "running"])).count()
    failed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "failed").count()

    # Calculate storage usage
    total_size = db.query(sa_func.coalesce(sa_func.sum(Clip.file_size_bytes), 0)).scalar() or 0
    rec_size = db.query(sa_func.coalesce(sa_func.sum(Recording.file_size_bytes), 0)).scalar() or 0
    total_mb = round((total_size + rec_size) / (1024 * 1024), 2)

    return DashboardStats(
        total_streamers=total_streamers,
        active_permissions=active_perms,
        total_recordings=total_recs,
        total_clips=total_clips,
        total_candidates=total_cands,
        active_jobs=active_jobs,
        failed_jobs=failed_jobs,
        total_storage_mb=total_mb,
        gpu_info=settings.gpu_info,
        integrations=settings.get_integration_status(),
    )

