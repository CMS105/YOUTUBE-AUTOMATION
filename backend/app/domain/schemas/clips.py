"""Pydantic schemas for Clip, ClipCandidate, Recording, and Processing Job entities."""

from datetime import datetime
from typing import Optional, Literal, List, Any, Dict, Union
from pydantic import BaseModel, ConfigDict, Field

ClipPreset = Literal["Viral Gaming", "Clean Gameplay", "Reaction Focus"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


# --- Recording Schemas ---
class RecordingResponse(BaseModel):
    id: int
    uuid: str
    streamer_id: int
    stream_id: Optional[int]
    file_name: str
    file_size_bytes: Optional[int]
    duration_seconds: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    codec_video: Optional[str]
    codec_audio: Optional[str]
    status: str
    ingested_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Clip Candidate Schemas ---
class ClipCandidateResponse(BaseModel):
    id: int
    uuid: str
    recording_id: int
    start_time: float
    end_time: float
    duration: float
    score_audio: float
    score_visual: float
    score_context: float
    score_composite: float
    rank: Optional[int]
    event_category: str
    status: str
    has_facecam: bool
    facecam_region: Optional[dict] = None
    transcript_text: Optional[str] = None
    suggested_titles: Optional[Any] = None
    metadata_json: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateListResponse(BaseModel):
    items: List[ClipCandidateResponse]
    total: int
    skip: int
    limit: int


class CandidateApproveRequest(BaseModel):
    preset: ClipPreset = "Viral Gaming"
    custom_title: Optional[str] = Field(None, max_length=300)


# --- Clip Schemas ---
class ClipResponse(BaseModel):
    id: int
    uuid: str
    candidate_id: int
    title: str
    file_name: str
    file_size_bytes: Optional[int]
    duration_seconds: float
    width: int
    height: int
    preset: str
    score: float
    event_category: str
    has_subtitles: bool
    is_favorite: bool
    download_count: int
    rendered_at: datetime
    created_at: datetime

    # Derived fields populated by router
    streamer_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    download_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ClipListResponse(BaseModel):
    items: List[ClipResponse]
    total: int
    skip: int
    limit: int


class ClipUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    is_favorite: Optional[bool] = None


# --- Processing Job Schemas ---
class ProcessingJobCreate(BaseModel):
    recording_id: int
    job_type: str = "full_pipeline"


class ProcessingJobResponse(BaseModel):
    id: int
    uuid: str
    recording_id: Optional[int]
    job_type: str
    status: str
    current_stage: Optional[str]
    progress_percent: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result_summary: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcessingJobListResponse(BaseModel):
    items: List[ProcessingJobResponse]
    total: int


# --- Dashboard Stats ---
class DashboardStats(BaseModel):
    total_streamers: int
    active_permissions: int
    total_recordings: int
    total_clips: int
    total_candidates: int
    active_jobs: int
    failed_jobs: int
    total_storage_mb: float
    gpu_info: dict
    integrations: dict

