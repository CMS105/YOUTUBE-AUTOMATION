"""
SQLAlchemy ORM Models for GTA 6 AI Clip Factory.

Entities:
  Streamer, Permission, Stream, MediaSource, Recording,
  DetectedEvent, ClipCandidate, Clip, Thumbnail,
  ProcessingJob, UserSettings, AuditLog

Constraint patterns adapted from TETHR-Bluetooth-Payments models.py.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, Float,
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint,
    Index, Enum as SAEnum, JSON,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


# ---------------------------------------------------------------------------
# Helper: generate a UUID hex default
# ---------------------------------------------------------------------------
def _uuid_hex() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# 1. STREAMER
# ---------------------------------------------------------------------------
class Streamer(Base):
    __tablename__ = "streamers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default=_uuid_hex)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="youtube")
    channel_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    channel_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    permissions: Mapped[List["Permission"]] = relationship("Permission", back_populates="streamer", cascade="all, delete-orphan")
    streams: Mapped[List["Stream"]] = relationship("Stream", back_populates="streamer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Streamer(id={self.id}, name='{self.display_name}', channel='{self.channel_id}')>"


# ---------------------------------------------------------------------------
# 2. PERMISSION
# ---------------------------------------------------------------------------
class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int] = mapped_column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    grant_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")  # manual, oauth, api
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scope: Mapped[str] = mapped_column(String(200), nullable=False, default="clip_creation")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    streamer: Mapped["Streamer"] = relationship("Streamer", back_populates="permissions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'PENDING', 'REVOKED', 'EXPIRED')",
            name="ck_permissions_valid_status",
        ),
        CheckConstraint(
            "grant_type IN ('manual', 'oauth', 'api', 'email')",
            name="ck_permissions_valid_grant_type",
        ),
    )


# ---------------------------------------------------------------------------
# 3. STREAM
# ---------------------------------------------------------------------------
class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int] = mapped_column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    platform_video_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="detected")  # detected, live, ended, processed
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    viewer_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    streamer: Mapped["Streamer"] = relationship("Streamer", back_populates="streams")
    recordings: Mapped[List["Recording"]] = relationship("Recording", back_populates="stream", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 4. MEDIA SOURCE
# ---------------------------------------------------------------------------
class MediaSource(Base):
    __tablename__ = "media_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # local_file, capture_feed, rtmp
    source_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('local_file', 'capture_feed', 'rtmp', 'srt', 'authorized_url')",
            name="ck_media_sources_valid_type",
        ),
    )


# ---------------------------------------------------------------------------
# 5. RECORDING
# ---------------------------------------------------------------------------
class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default=_uuid_hex)
    stream_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("streams.id", ondelete="SET NULL"), nullable=True)
    streamer_id: Mapped[int] = mapped_column(Integer, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # SHA-256
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    codec_video: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    codec_audio: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ingested")  # ingested, analyzing, analyzed, failed
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    stream: Mapped[Optional["Stream"]] = relationship("Stream", back_populates="recordings")
    streamer: Mapped["Streamer"] = relationship("Streamer")
    detected_events: Mapped[List["DetectedEvent"]] = relationship("DetectedEvent", back_populates="recording", cascade="all, delete-orphan")
    clip_candidates: Mapped[List["ClipCandidate"]] = relationship("ClipCandidate", back_populates="recording", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("file_size_bytes > 0 OR file_size_bytes IS NULL", name="ck_recordings_positive_size"),
        CheckConstraint("duration_seconds >= 0 OR duration_seconds IS NULL", name="ck_recordings_non_negative_duration"),
    )


# ---------------------------------------------------------------------------
# 6. DETECTED EVENT
# ---------------------------------------------------------------------------
class DetectedEvent(Base):
    __tablename__ = "detected_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    intensity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    recording: Mapped["Recording"] = relationship("Recording", back_populates="detected_events")

    __table_args__ = (
        CheckConstraint("start_time >= 0", name="ck_events_positive_start"),
        CheckConstraint("end_time > start_time", name="ck_events_end_after_start"),
        CheckConstraint("confidence >= 0 AND confidence <= 1.0", name="ck_events_valid_confidence"),
        Index("ix_detected_events_recording_time", "recording_id", "start_time"),
    )


# ---------------------------------------------------------------------------
# 7. CLIP CANDIDATE
# ---------------------------------------------------------------------------
class ClipCandidate(Base):
    __tablename__ = "clip_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default=_uuid_hex)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    score_audio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_visual: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_context: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_composite: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending, approved, rejected, rendered
    has_facecam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    facecam_region: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {x, y, w, h}
    transcript_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_titles: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # list of title strings
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    recording: Mapped["Recording"] = relationship("Recording", back_populates="clip_candidates")
    clips: Mapped[List["Clip"]] = relationship("Clip", back_populates="candidate", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("start_time >= 0", name="ck_candidates_positive_start"),
        CheckConstraint("end_time > start_time", name="ck_candidates_end_after_start"),
        CheckConstraint("duration > 0", name="ck_candidates_positive_duration"),
        CheckConstraint("score_composite >= 0 AND score_composite <= 100", name="ck_candidates_valid_score"),
        UniqueConstraint("recording_id", "start_time", "end_time", name="uq_candidates_recording_window"),
        Index("ix_clip_candidates_score", "score_composite"),
    )


# ---------------------------------------------------------------------------
# 8. CLIP (Rendered Final Output)
# ---------------------------------------------------------------------------
class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default=_uuid_hex)
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("clip_candidates.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1080)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1920)
    preset: Mapped[str] = mapped_column(String(50), nullable=False, default="Viral Gaming")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    event_category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    has_subtitles: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    subtitle_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rendered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    candidate: Mapped["ClipCandidate"] = relationship("ClipCandidate", back_populates="clips")
    thumbnails: Mapped[List["Thumbnail"]] = relationship("Thumbnail", back_populates="clip", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="ck_clips_positive_duration"),
        CheckConstraint(
            "preset IN ('Viral Gaming', 'Clean Gameplay', 'Reaction Focus')",
            name="ck_clips_valid_preset",
        ),
    )


# ---------------------------------------------------------------------------
# 9. THUMBNAIL
# ---------------------------------------------------------------------------
class Thumbnail(Base):
    __tablename__ = "thumbnails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clip_id: Mapped[int] = mapped_column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1080)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1920)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    clip: Mapped["Clip"] = relationship("Clip", back_populates="thumbnails")


# ---------------------------------------------------------------------------
# 10. PROCESSING JOB
# ---------------------------------------------------------------------------
class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default=_uuid_hex)
    recording_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full_pipeline, audio_analysis, visual_analysis, rendering, etc.
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    # queued, running, completed, failed, cancelled
    current_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    recording: Mapped[Optional["Recording"]] = relationship("Recording")

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_valid_status",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_jobs_valid_progress",
        ),
        Index("ix_processing_jobs_status_created", "status", "created_at"),
    )


# ---------------------------------------------------------------------------
# 11. USER SETTINGS
# ---------------------------------------------------------------------------
class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")  # string, int, bool, json
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ---------------------------------------------------------------------------
# 12. AUDIT LOG
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # created, updated, deleted, permission_granted, permission_revoked
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created", "created_at"),
    )


# ---------------------------------------------------------------------------
# 13. LIVE DISCOVERY (Global YouTube Livestream Monitoring)
# ---------------------------------------------------------------------------
class LiveDiscovery(Base):
    __tablename__ = "live_discoveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel_title: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    live_status: Mapped[str] = mapped_column(String(30), nullable=False, default="live", index=True)
    authorization_status: Mapped[str] = mapped_column(String(30), nullable=False, default="AWAITING_AUTHORIZATION", index=True)
    recording_status: Mapped[str] = mapped_column(String(30), nullable=False, default="IDLE", index=True)
    viewer_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    recording_sessions: Mapped[List["RecordingSession"]] = relationship("RecordingSession", back_populates="discovery", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("live_status IN ('live', 'ended', 'unavailable')", name="ck_discoveries_valid_live_status"),
        CheckConstraint("authorization_status IN ('AUTHORIZED', 'AWAITING_AUTHORIZATION', 'REVOKED')", name="ck_discoveries_valid_auth_status"),
        CheckConstraint("recording_status IN ('IDLE', 'RECORDING', 'RECORDED', 'PROCESSING', 'CLIPPED', 'FAILED')", name="ck_discoveries_valid_recording_status"),
        Index("ix_discoveries_channel_live", "channel_id", "live_status"),
    )


# ---------------------------------------------------------------------------
# 14. CREATOR AUTHORIZATION (Explicit Permission & Ingest Input)
# ---------------------------------------------------------------------------
class CreatorAuthorization(Base):
    __tablename__ = "creator_authorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    creator_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    authorized_source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # RTMP, SRT, capture_feed, or OBS scene/window
    allowed_scope: Mapped[str] = mapped_column(String(100), nullable=False, default="clip_creation")
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    streamer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("streamers.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    streamer: Mapped[Optional["Streamer"]] = relationship("Streamer")
    recording_sessions: Mapped[List["RecordingSession"]] = relationship("RecordingSession", back_populates="authorization", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'PENDING', 'REVOKED', 'EXPIRED')", name="ck_creator_auth_valid_status"),
        CheckConstraint("allowed_scope IN ('clip_creation', 'full_access')", name="ck_creator_auth_valid_scope"),
    )


# ---------------------------------------------------------------------------
# 15. RECORDING SESSION (Automated OBS / Pipeline Recording)
# ---------------------------------------------------------------------------
class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default=_uuid_hex, index=True)
    discovery_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("live_discoveries.id", ondelete="SET NULL"), nullable=True)
    authorization_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("creator_authorizations.id", ondelete="SET NULL"), nullable=True)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    video_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source_input: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="recording", index=True)
    obs_output_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    recording_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    discovery: Mapped[Optional["LiveDiscovery"]] = relationship("LiveDiscovery", back_populates="recording_sessions")
    authorization: Mapped[Optional["CreatorAuthorization"]] = relationship("CreatorAuthorization", back_populates="recording_sessions")
    recording: Mapped[Optional["Recording"]] = relationship("Recording")

    __table_args__ = (
        CheckConstraint("status IN ('recording', 'completed', 'failed', 'aborted')", name="ck_recording_sessions_valid_status"),
        Index("ix_recording_sessions_status_started", "status", "started_at"),
    )

