"""
Ingestion API Router.
Handles video uploads, local file registration, and retention sweeps.
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Recording
from app.domain.schemas.clips import RecordingResponse
from app.services.ingestion_service import ingestion_service
from app.services.retention_service import retention_service
from app.services.permission_service import permission_service
from app.core.config import settings

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


class LocalIngestRequest(BaseModel):
    streamer_id: int
    source_path: str = Field(..., description="Absolute or relative path to local video file")
    stream_id: Optional[int] = None
    copy_to_storage: bool = Field(default=False, description="Whether to copy file into ./data/recordings/")


class RetentionRunRequest(BaseModel):
    max_days: Optional[int] = Field(None, ge=1, le=365)


@router.post("/local", response_model=RecordingResponse, status_code=201)
def ingest_local_file(data: LocalIngestRequest, db: Session = Depends(get_db)):
    """
    Ingest an authorized local gameplay recording.
    Permission check is enforced automatically: rejects unpermitted creators with 403.
    """
    recording = ingestion_service.ingest_local_file(
        db=db,
        streamer_id=data.streamer_id,
        source_path=data.source_path,
        stream_id=data.stream_id,
        copy_to_storage=data.copy_to_storage,
    )
    return recording


@router.post("/upload", response_model=RecordingResponse, status_code=201)
def upload_recording(
    streamer_id: int = Form(...),
    stream_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Direct multipart upload of an authorized gameplay recording file.
    """
    # 1. Enforce permission verification
    permission_service.verify_streamer_authorized(db, streamer_id)

    # 2. Save uploaded stream to temporary file first
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    clean_name = Path(file.filename or "recording.mp4").name
    temp_file = temp_dir / clean_name

    try:
        with open(temp_file, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
    finally:
        file.file.close()

    # 3. Ingest saved file and copy to managed storage
    recording = ingestion_service.ingest_local_file(
        db=db,
        streamer_id=streamer_id,
        source_path=str(temp_file),
        stream_id=stream_id,
        copy_to_storage=True,
    )

    # Clean up temp upload
    try:
        if temp_file.exists():
            temp_file.unlink()
    except Exception:
        pass

    return recording


@router.post("/retention/run")
def trigger_retention_sweep(data: Optional[RetentionRunRequest] = None, db: Session = Depends(get_db)):
    """Run automated retention cleanup: purges old raw video recordings and temporary files."""
    retention_service.cleanup_temp_directory()
    result = retention_service.apply_retention_policy(db, max_days=data.max_days if data else None)
    return {
        "status": "success",
        "message": f"Retention sweep completed. Purged {result['purged_count']} recordings, freed {result['megabytes_freed']} MB.",
        "details": result,
    }


@router.get("/probe")
def probe_file_metadata(file_path: str):
    """Diagnose container format, duration, codecs, and resolution of a media file."""
    p = Path(file_path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return ingestion_service.probe_video_metadata(p)


@router.get("/storage/status")
def get_storage_status(db: Session = Depends(get_db)):
    """Returns current disk usage, recording counts, quota, and cleanup metrics."""
    return retention_service.get_storage_usage(db)
