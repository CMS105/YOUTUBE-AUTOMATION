"""Pydantic schemas for Permission entities."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

PermissionStatus = Literal["ACTIVE", "PENDING", "REVOKED", "EXPIRED"]
GrantType = Literal["manual", "oauth", "api", "email"]


class PermissionCreate(BaseModel):
    streamer_id: int
    status: PermissionStatus = "PENDING"
    grant_type: GrantType = "manual"
    scope: str = Field(default="clip_creation", max_length=200)
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class PermissionUpdate(BaseModel):
    status: Optional[PermissionStatus] = None
    scope: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class PermissionResponse(BaseModel):
    id: int
    streamer_id: int
    status: str
    grant_type: str
    granted_at: Optional[datetime]
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    scope: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionGrantRequest(BaseModel):
    """Grant active permission to a streamer."""
    streamer_id: int
    grant_type: GrantType = "manual"
    scope: str = "clip_creation"
    notes: Optional[str] = None


class PermissionRevokeRequest(BaseModel):
    """Revoke an existing permission."""
    reason: Optional[str] = None

