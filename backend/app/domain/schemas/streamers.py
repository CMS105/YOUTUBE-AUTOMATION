"""Pydantic schemas for Streamer entities."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class StreamerBase(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    platform: str = Field(default="youtube", max_length=50)
    channel_id: Optional[str] = Field(None, max_length=100)
    channel_url: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None


class StreamerCreate(StreamerBase):
    pass


class StreamerUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    platform: Optional[str] = Field(None, max_length=50)
    channel_id: Optional[str] = Field(None, max_length=100)
    channel_url: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class StreamerResponse(StreamerBase):
    id: int
    uuid: str
    is_active: bool
    permission_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StreamerListResponse(BaseModel):
    items: list[StreamerResponse]
    total: int
    skip: int
    limit: int

