"""Common Pydantic schemas used across modules."""

from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel, ConfigDict, Field


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    skip: int
    limit: int


class StatusMessage(BaseModel):
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    hardware: dict
    integrations: dict

