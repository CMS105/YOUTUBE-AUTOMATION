"""
Pydantic schemas for Global Livestream Discovery, Creator Authorization,
OBS Studio integration, and Recording Sessions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 1. LIVE DISCOVERY SCHEMAS
# ---------------------------------------------------------------------------
class LiveDiscoveryBase(BaseModel):
    video_id: str = Field(..., max_length=100)
    channel_id: str = Field(..., max_length=100)
    channel_title: str = Field(..., max_length=200)
    title: str = Field(..., max_length=500)
    thumbnail_url: Optional[str] = None
    stream_url: str
    live_status: str = Field(default="live")
    authorization_status: str = Field(default="AWAITING_AUTHORIZATION")
    recording_status: str = Field(default="IDLE")
    viewer_count: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None


class LiveDiscoveryResponse(LiveDiscoveryBase):
    id: int
    detected_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveDiscoveryListResponse(BaseModel):
    items: List[LiveDiscoveryResponse]
    total: int
    live_count: int
    authorized_count: int
    recording_count: int
    quota_status: Optional[Dict[str, Any]] = None


class PollDiscoveryRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Optional custom search query; defaults to random or configured keywords")
    max_results: int = Field(default=15, ge=1, le=50)


# ---------------------------------------------------------------------------
# 2. CREATOR AUTHORIZATION SCHEMAS
# ---------------------------------------------------------------------------
class CreatorAuthorizationCreate(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=100)
    creator_name: str = Field(..., min_length=1, max_length=200)
    authorized_source: Optional[str] = Field(default=None, max_length=500, description="RTMP URL, SRT URL, or OBS window/game capture scene name")
    allowed_scope: Literal["clip_creation", "full_access"] = "clip_creation"
    notes: Optional[str] = None
    status: Literal["ACTIVE", "PENDING", "REVOKED", "EXPIRED"] = "ACTIVE"
    expires_at: Optional[datetime] = None


class CreatorAuthorizationUpdate(BaseModel):
    creator_name: Optional[str] = Field(None, max_length=200)
    authorized_source: Optional[str] = Field(None, max_length=500)
    allowed_scope: Optional[Literal["clip_creation", "full_access"]] = None
    status: Optional[Literal["ACTIVE", "PENDING", "REVOKED", "EXPIRED"]] = None
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class CreatorAuthorizationRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class CreatorAuthorizationResponse(BaseModel):
    id: int
    channel_id: str
    creator_name: str
    status: str
    authorized_source: Optional[str] = None
    allowed_scope: str
    authorized_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    notes: Optional[str] = None
    streamer_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreatorAuthorizationListResponse(BaseModel):
    items: List[CreatorAuthorizationResponse]
    total: int
    active_count: int


# ---------------------------------------------------------------------------
# 3. OBS STUDIO SCHEMAS
# ---------------------------------------------------------------------------
class OBSStatusResponse(BaseModel):
    connected: bool
    host: str
    port: int
    version: Optional[str] = None
    is_recording: bool = False
    recording_time_seconds: float = 0.0
    output_path: Optional[str] = None
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    disk_sufficient: bool = True
    error: Optional[str] = None


class OBSConnectRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None


class OBSRecordStartRequest(BaseModel):
    channel_id: str
    video_id: Optional[str] = None
    discovery_id: Optional[int] = None
    custom_source: Optional[str] = None


class OBSRecordStopResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    output_path: Optional[str] = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    message: str


# ---------------------------------------------------------------------------
# 4. RECORDING SESSION SCHEMAS
# ---------------------------------------------------------------------------
class RecordingSessionResponse(BaseModel):
    id: int
    session_id: str
    discovery_id: Optional[int] = None
    authorization_id: Optional[int] = None
    channel_id: str
    video_id: Optional[str] = None
    source_input: str
    status: str
    obs_output_path: Optional[str] = None
    recording_id: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float
    file_size_bytes: int
    error_message: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecordingSessionListResponse(BaseModel):
    items: List[RecordingSessionResponse]
    total: int
    active_sessions: int
