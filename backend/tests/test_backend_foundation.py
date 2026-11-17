"""
Phase 1 Foundation Test Suite:
Tests models, database, permission gating, and API endpoints.
Adapted from API-TASKFLOW test_api.py and TETHR testing patterns.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure test DB is in-memory SQLite before settings and database are imported
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database import engine, Base, SessionLocal, get_db
from app.models import (
    Streamer, Permission, Stream, Recording,
    ClipCandidate, Clip, Thumbnail, ProcessingJob, AuditLog
)
from app.main import app


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "hardware" in data
    assert "integrations" in data


def test_integration_status_endpoint(client):
    response = client.get("/api/v1/integrations/status")
    assert response.status_code == 200
    data = response.json()
    assert "youtube_api" in data
    assert "gemini" in data
    assert "active_vlm" in data
    assert data["auto_publish"] is False  # Safety guard verified


def test_streamer_crud_and_permission_flow(client):
    # 1. Create Streamer
    create_payload = {
        "display_name": "ViceCityKing",
        "platform": "youtube",
        "channel_id": "UC_TEST_123456",
        "channel_url": "https://youtube.com/@ViceCityKing",
        "description": "Top GTA 6 Streamer"
    }
    res = client.post("/api/v1/streamers", json=create_payload)
    assert res.status_code == 201
    streamer = res.json()
    streamer_id = streamer["id"]
    assert streamer["display_name"] == "ViceCityKing"
    assert streamer["permission_status"] is None

    # 2. Grant Permission
    grant_payload = {
        "streamer_id": streamer_id,
        "grant_type": "manual",
        "scope": "clip_creation",
        "notes": "Verified written consent received."
    }
    perm_res = client.post("/api/v1/permissions/grant", json=grant_payload)
    assert perm_res.status_code == 201
    perm = perm_res.json()
    assert perm["status"] == "ACTIVE"
    perm_id = perm["id"]

    # 3. Check Streamer detail reflects ACTIVE permission
    st_res = client.get(f"/api/v1/streamers/{streamer_id}")
    assert st_res.status_code == 200
    assert st_res.json()["permission_status"] == "ACTIVE"

    # 4. Revoke Permission
    revoke_res = client.post(f"/api/v1/permissions/{perm_id}/revoke", json={"reason": "Streamer requested stop"})
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOKED"

    # 5. Check Streamer detail reflects REVOKED permission
    st_res2 = client.get(f"/api/v1/streamers/{streamer_id}")
    assert st_res2.json()["permission_status"] == "REVOKED"


def test_permission_blocking_guard(client, db):
    # Create streamer without permission
    streamer = Streamer(display_name="NoPermissionGamer", platform="youtube", channel_id="UC_NOPERM")
    db.add(streamer)
    db.commit()
    db.refresh(streamer)

    # Ingest a fake recording
    recording = Recording(
        streamer_id=streamer.id,
        file_path="data/recordings/test.mp4",
        file_name="test.mp4",
        duration_seconds=600.0,
        status="ingested"
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    # Attempt to create processing job - must be blocked with 403 Forbidden!
    job_payload = {
        "recording_id": recording.id,
        "job_type": "full_pipeline"
    }
    job_res = client.post("/api/v1/jobs", json=job_payload)
    assert job_res.status_code == 403
    assert "ACTIVE permission" in job_res.json()["detail"]


def test_dashboard_stats(client):
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_streamers" in stats
    assert "active_permissions" in stats
    assert "total_clips" in stats
    assert "total_storage_mb" in stats
