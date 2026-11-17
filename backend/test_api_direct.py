"""
Phase 1 Foundation Verification Test:
Tests database engine, 12 models, schema validation, permissions logic, and CRUD operations.
Adapted from API-TASKFLOW (demo123) test_api.py.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.database import Base, engine, SessionLocal, get_db_type
from app.models import (
    Streamer, Permission, Stream, MediaSource, Recording,
    DetectedEvent, ClipCandidate, Clip, Thumbnail, ProcessingJob,
    UserSettings, AuditLog
)
from app.routers import streamers, permissions, clips, health

def run():
    print("[1/6] Verifying Database Connection...")
    db_type = get_db_type()
    print(f"      Active Database: {db_type} ({engine.url})")

    print("[2/6] Creating All Tables...")
    Base.metadata.create_all(bind=engine)
    print("      12 Table definitions created successfully.")

    db = SessionLocal()
    try:
        print("[3/6] Testing Streamer & Permission Entities...")
        # Create Streamer
        streamer = Streamer(
            display_name="SpeedyGamer6",
            platform="youtube",
            channel_id="UC_SPEEDY_GTA6",
            channel_url="https://youtube.com/@SpeedyGamer6",
            description="High-speed chases in Vice City"
        )
        db.add(streamer)
        db.commit()
        db.refresh(streamer)
        assert streamer.id is not None
        assert streamer.uuid is not None
        print(f"      Streamer created: ID={streamer.id}, UUID={streamer.uuid}")

        # Permission flow: Initial grant
        perm = Permission(
            streamer_id=streamer.id,
            status="ACTIVE",
            grant_type="manual",
            scope="clip_creation",
            notes="Signed consent agreement."
        )
        db.add(perm)
        db.add(AuditLog(
            entity_type="permission",
            entity_id=streamer.id,
            action="permission_granted",
            details="Consent granted."
        ))
        db.commit()
        db.refresh(perm)
        assert perm.id is not None
        assert perm.status == "ACTIVE"
        print(f"      Permission granted: ID={perm.id}, Status={perm.status}")

        print("[4/6] Testing Recording & Job Entities...")
        # Create Recording
        recording = Recording(
            streamer_id=streamer.id,
            file_path="data/recordings/vice_city_stunt.mp4",
            file_name="vice_city_stunt.mp4",
            file_hash="a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
            file_size_bytes=524288000,
            duration_seconds=1200.0,
            width=1920,
            height=1080,
            fps=60.0,
            codec_video="h264",
            codec_audio="aac",
            status="analyzed"
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)
        assert recording.id is not None
        print(f"      Recording created: ID={recording.id}, Duration={recording.duration_seconds}s")

        # Create DetectedEvent
        event = DetectedEvent(
            recording_id=recording.id,
            event_type="police_chase",
            category="action",
            start_time=120.0,
            end_time=165.0,
            confidence=0.92,
            intensity=0.88,
            description="5-star wanted level police pursuit on Ocean Drive"
        )
        db.add(event)
        db.commit()
        print(f"      DetectedEvent logged: {event.event_type} (Confidence: {event.confidence})")

        # Create ClipCandidate
        candidate = ClipCandidate(
            recording_id=recording.id,
            start_time=120.0,
            end_time=155.0,
            duration=35.0,
            score_audio=82.0,
            score_visual=89.0,
            score_context=91.0,
            score_composite=87.1,
            event_category="police_chase",
            has_facecam=True,
            transcript_text="Look at the cops! They're coming from the bridge!",
            suggested_titles={"titles": ["INSANE 5-STAR CHASE IN VICE CITY!", "I ALMOST DIED HERE LOL", "GTA 6 POLICE AI IS CRAZY"]}
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        assert candidate.id is not None
        print(f"      ClipCandidate created: ID={candidate.id}, Score={candidate.score_composite}")

        # Create Clip (Final Rendered)
        clip = Clip(
            candidate_id=candidate.id,
            title="INSANE 5-STAR CHASE IN VICE CITY!",
            file_path="data/clips/clip_001.mp4",
            file_name="clip_001.mp4",
            file_size_bytes=24500000,
            duration_seconds=35.0,
            width=1080,
            height=1920,
            preset="Viral Gaming",
            score=87.1,
            event_category="police_chase",
            has_subtitles=True,
            is_favorite=True
        )
        db.add(clip)
        db.commit()
        db.refresh(clip)
        assert clip.id is not None
        print(f"      Rendered Clip logged: ID={clip.id}, Preset='{clip.preset}'")

        # Create Thumbnail
        thumb = Thumbnail(
            clip_id=clip.id,
            file_path="data/thumbnails/clip_001_thumb.jpg",
            file_name="clip_001_thumb.jpg",
            width=1080,
            height=1920,
            timestamp_seconds=15.0,
            is_primary=True
        )
        db.add(thumb)
        db.commit()
        print(f"      Thumbnail logged: ID={thumb.id}")

        # Create ProcessingJob
        job = ProcessingJob(
            recording_id=recording.id,
            job_type="full_pipeline",
            status="completed",
            progress_percent=100.0,
            current_stage="rendering_complete"
        )
        db.add(job)
        db.commit()
        print(f"      ProcessingJob logged: ID={job.id}, Status={job.status}")

        print("[5/6] Testing Router Functions Directly...")
        # Test health function
        h_data = health.health()
        assert h_data["status"] == "ok"
        assert h_data["database"] in ("sqlite", "postgresql")
        print(f"      health() -> {h_data['status']}, HW: {h_data['hardware']['device_name']}")

        # Test integration_status function
        int_data = health.integration_status()
        assert int_data["auto_publish"] is False
        print(f"      integration_status() -> AutoPublish={int_data['auto_publish']}, ActiveVLM={int_data['active_vlm']}")

        # Test streamers list function
        st_list = streamers.list_streamers(skip=0, limit=10, db=db)
        assert st_list.total >= 1
        print(f"      list_streamers() -> {st_list.total} total streamers found.")

        # Test permissions list function
        perm_list = permissions.list_permissions(db=db)
        assert len(perm_list) >= 1
        print(f"      list_permissions() -> {len(perm_list)} permissions found.")

        # Test dashboard stats function
        dash_stats = clips.get_dashboard_stats(db=db)
        assert dash_stats.total_streamers >= 1
        assert dash_stats.active_permissions >= 1
        assert dash_stats.total_clips >= 1
        print(f"      get_dashboard_stats() -> {dash_stats.total_streamers} streamers, {dash_stats.total_clips} clips, {dash_stats.total_storage_mb} MB storage.")

        print("[6/6] Testing Permission Revocation & Gating...")
        # Revoke permission
        rev_data = permissions.PermissionRevokeRequest(reason="End of stream season")
        rev_perm = permissions.revoke_permission(permission_id=perm.id, data=rev_data, db=db)
        assert rev_perm.status == "REVOKED"
        print(f"      Permission #{rev_perm.id} successfully REVOKED.")

        # Attempt to create job for unpermitted streamer must raise 403
        try:
            job_req = clips.ProcessingJobCreate(recording_id=recording.id)
            clips.create_job(data=job_req, db=db)
            assert False, "Should have raised 403 HTTPException"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403
            print(f"      Permission Guard verified: {exc.detail}")

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL PHASE 1 BACKEND FOUNDATION TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")

if __name__ == "__main__":
    run()
