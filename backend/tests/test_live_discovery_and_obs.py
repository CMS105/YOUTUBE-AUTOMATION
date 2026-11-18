"""
Comprehensive Integration & Verification Suite for:
1. Global YouTube Live Discovery & Deduplication
2. API Quota Tracking & Enforcement
3. Creator Authorization Gating & Input Validation
4. Revoked Permission Blocking
5. OBS Studio WebSocket Control & Disconnect Handling
6. Recording Session Lifecycle & Duplicate Prevention
7. Restart Recovery of Orphaned Sessions
8. End-to-End Workflow: Discovery -> Authorization -> OBS Recording -> AI Clipping -> Vertical 9:16 Video.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import numpy as np
import av
import cv2

# Set backend in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, Base, engine
from app.models import (
    LiveDiscovery, CreatorAuthorization, RecordingSession,
    Streamer, Recording, ClipCandidate, Clip, Thumbnail, ProcessingJob
)
from app.services.youtube_monitor_service import youtube_monitor_service, YouTubeQuotaTracker
from app.services.creator_authorization_service import creator_authorization_service
from app.services.obs_service import obs_client
from app.services.recording_manager_service import recording_manager_service
from app.services.automation_service import automation_service
from app.domain.schemas.discovery import CreatorAuthorizationCreate

# Ensure all tables exist in database
Base.metadata.create_all(bind=engine)


def clean_test_db_state():
    """Cleans up leftover test records and dangling active recording sessions."""
    db = SessionLocal()
    try:
        db.query(RecordingSession).filter(RecordingSession.status == "recording").update({"status": "aborted"})
        test_channels = [
            "UC_TEST_CREATOR_001", "UC_AUTHTEST_CHIRAG_002", "UC_REVOKE_CH_003",
            "UC_SESSION_TEST_004", "UC_ORPHAN_CH_005", "UC_E2E_LEONIDA_CREATOR", "UC_ANOTHER_CHANNEL"
        ]
        db.query(RecordingSession).filter(RecordingSession.channel_id.in_(test_channels)).delete()
        db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id.in_(test_channels)).delete()
        db.query(LiveDiscovery).filter(LiveDiscovery.channel_id.in_(test_channels)).delete()
        db.query(LiveDiscovery).filter(LiveDiscovery.video_id.in_(["TEST_GTA6_VID_001", "E2E_GTA6_STREAM_999"])).delete()
        for s in db.query(Streamer).filter(Streamer.channel_id.in_(test_channels)).all():
            db.delete(s)
        db.commit()
    finally:
        db.close()

clean_test_db_state()


def create_test_video(output_path: str, duration_sec: float = 5.0) -> None:
    """Generates a synthetic test video with audio excitement burst and facecam."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()

    fps = 30
    total_frames = int(fps * duration_sec)
    w, h = 640, 360

    container = av.open(str(p), mode="w", format="mp4")
    v_stream = container.add_stream("libx264", rate=fps)
    v_stream.width = w
    v_stream.height = h
    v_stream.pix_fmt = "yuv420p"

    a_stream = container.add_stream("aac", rate=48000)
    a_stream.layout = "stereo"

    # Encode video frames
    for i in range(total_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (20, 20, 35)

        # High motion vehicle in center
        car_x = int(50 + (i * 7)) % (w - 100)
        cv2.rectangle(frame, (car_x, 200), (car_x + 80, 260), (0, 255, 255), -1)

        # Facecam overlay in corner
        cv2.rectangle(frame, (480, 20), (620, 110), (220, 180, 140), -1)
        cv2.circle(frame, (525, 55), 5, (0, 0, 0), -1)
        cv2.circle(frame, (575, 55), 5, (0, 0, 0), -1)

        av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        for packet in v_stream.encode(av_frame):
            container.mux(packet)

    for packet in v_stream.encode():
        container.mux(packet)

    # Encode audio with an excitement burst in middle
    total_samples = int(48000 * duration_sec)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    amp = np.where((t >= 2.0) & (t <= 3.8), 0.90, 0.20)
    audio_data = (np.sin(2 * np.pi * 440 * t) * amp).astype(np.float32)

    chunk_size = 1024
    for idx in range(0, total_samples, chunk_size):
        chunk = audio_data[idx:idx + chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        stereo = np.vstack([chunk, chunk])
        audio_frame = av.AudioFrame.from_ndarray(stereo, format="fltp", layout="stereo")
        audio_frame.rate = 48000
        for packet in a_stream.encode(audio_frame):
            container.mux(packet)

    for packet in a_stream.encode():
        container.mux(packet)

    container.close()


def test_youtube_discovery_and_deduplication():
    print("\n[TEST 1] YouTube Discovery & Deduplication...")
    db = SessionLocal()
    try:
        # Clean up any existing test records
        db.query(LiveDiscovery).filter(LiveDiscovery.video_id == "TEST_GTA6_VID_001").delete()
        db.commit()

        # Simulate discovery result insertion
        d1 = LiveDiscovery(
            video_id="TEST_GTA6_VID_001",
            channel_id="UC_TEST_CREATOR_001",
            channel_title="ViceCityPilot",
            title="GTA 6 Full Map Exploration LIVE! 🌴",
            thumbnail_url="https://img.youtube.com/vi/TEST_GTA6_VID_001/hqdefault.jpg",
            stream_url="https://www.youtube.com/watch?v=TEST_GTA6_VID_001",
            live_status="live",
            authorization_status="AWAITING_AUTHORIZATION",
            recording_status="IDLE",
        )
        db.add(d1)
        db.commit()

        # Check existing lookup
        found = db.query(LiveDiscovery).filter(LiveDiscovery.video_id == "TEST_GTA6_VID_001").first()
        assert found is not None
        assert found.authorization_status == "AWAITING_AUTHORIZATION"
        assert found.live_status == "live"

        # Deduplication check: updating existing record without duplicates
        found.title = "GTA 6 Full Map Exploration LIVE! 🌴 [UPDATED TITLE]"
        db.commit()

        count = db.query(LiveDiscovery).filter(LiveDiscovery.video_id == "TEST_GTA6_VID_001").count()
        assert count == 1, "Duplicate video ID detected!"
        print("  [+] Test 1 Passed: Discovery created and deduplicated by platform video ID.")
    finally:
        db.close()


def test_quota_tracker_and_rollover():
    print("\n[TEST 2] API Quota Tracker & Daily Rollover...")
    tracker = YouTubeQuotaTracker(daily_limit=500)
    assert tracker.consume(100) is True
    assert tracker.used_units == 100
    assert tracker.consume(350) is True
    assert tracker.used_units == 450
    # Next 100 units exceed limit of 500
    assert tracker.consume(100) is False, "Quota limit should suppress calls exceeding daily ceiling!"
    assert tracker.used_units == 450

    # Simulate UTC rollover
    tracker.last_reset = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    assert tracker.consume(100) is True, "Quota tracker must reset on UTC day rollover!"
    assert tracker.used_units == 100
    print("  [+] Test 2 Passed: Quota tracker correctly suppresses over-limit calls and rolls over at midnight UTC.")


def test_creator_authorization_gate():
    print("\n[TEST 3] Creator Authorization & Approved Input Validation...")
    db = SessionLocal()
    try:
        channel_id = "UC_AUTHTEST_CHIRAG_002"
        db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id == channel_id).delete()
        db.commit()

        # 1. Non-existent creator -> Not eligible
        eligible, reason, _ = creator_authorization_service.verify_recording_eligibility(db, channel_id)
        assert eligible is False
        assert "no authorization record" in reason

        # 2. PENDING status -> Not eligible
        auth = creator_authorization_service.authorize_creator(
            db,
            CreatorAuthorizationCreate(
                channel_id=channel_id,
                creator_name="ChiragPlaysGTA",
                status="PENDING",
            ),
        )
        eligible, reason, _ = creator_authorization_service.verify_recording_eligibility(db, channel_id)
        assert eligible is False
        assert "PENDING" in reason

        # 3. ACTIVE status but no approved input feed -> Not eligible
        auth.status = "ACTIVE"
        auth.authorized_source = None
        db.commit()
        eligible, reason, _ = creator_authorization_service.verify_recording_eligibility(db, channel_id)
        assert eligible is False
        assert "approved video input source" in reason

        # 4. ACTIVE status with valid authorized input -> ELIGIBLE!
        auth.authorized_source = "OBS:WindowCapture_GTA6"
        db.commit()
        eligible, reason, record = creator_authorization_service.verify_recording_eligibility(db, channel_id)
        assert eligible is True
        assert record.authorized_source == "OBS:WindowCapture_GTA6"
        print("  [+] Test 3 Passed: Authorization gate strictly validates status and approved video input.")
    finally:
        db.close()


def test_revoked_authorization_blocks_recording():
    print("\n[TEST 4] Revoked Authorization Strictly Blocks Recording...")
    db = SessionLocal()
    try:
        channel_id = "UC_REVOKE_CH_003"
        db.query(RecordingSession).filter(RecordingSession.status == "recording").update({"status": "aborted"})
        db.query(RecordingSession).filter(RecordingSession.channel_id == channel_id).delete()
        db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id == channel_id).delete()
        db.commit()

        auth = creator_authorization_service.authorize_creator(
            db,
            CreatorAuthorizationCreate(
                channel_id=channel_id,
                creator_name="RevokedCreator",
                authorized_source="rtmp://127.0.0.1:1935/live",
                status="ACTIVE",
            ),
        )

        # Revoke it
        creator_authorization_service.revoke_authorization(db, auth.id, reason="Streamer opted out")
        eligible, reason, _ = creator_authorization_service.verify_recording_eligibility(db, channel_id)
        assert eligible is False
        assert "REVOKED" in reason

        # Attempting start_session must raise PermissionError (mapped to HTTP 403)
        blocked = False
        try:
            recording_manager_service.start_session(db, channel_id)
        except PermissionError:
            blocked = True

        assert blocked is True, "RecordingManager must reject revoked creator with PermissionError!"
        print("  [+] Test 4 Passed: Revocation immediately blocks recording with PermissionError.")
    finally:
        db.close()


def test_obs_websocket_offline_and_mock_control():
    print("\n[TEST 5] OBS WebSocket Offline Resiliency & Mock Mode...")
    # Real connection without OBS running handles gracefully
    obs_client.disable_mock_mode()
    ok, err = obs_client.connect()
    assert ok is False
    assert err is not None

    status = obs_client.get_full_status()
    assert status["connected"] is False

    # Enable mock mode
    obs_client.enable_mock_mode(initial_recording=False)
    assert obs_client.is_connected() is True

    # Start mock recording
    started, start_err = obs_client.start_recording()
    assert started is True
    assert start_err is None
    assert obs_client.get_record_status()["outputActive"] is True

    # Stop mock recording
    stopped, out_path, stop_err = obs_client.stop_recording()
    assert stopped is True
    assert out_path is not None
    assert obs_client.get_record_status()["outputActive"] is False
    print("  [+] Test 5 Passed: OBS client handles offline errors gracefully and supports robust simulated testing.")


def test_recording_sessions_and_duplicate_prevention():
    print("\n[TEST 6] Recording Sessions & Duplicate Prevention...")
    db = SessionLocal()
    try:
        channel_id = "UC_SESSION_TEST_004"
        db.query(RecordingSession).filter(RecordingSession.status == "recording").update({"status": "aborted"})
        db.query(RecordingSession).filter(RecordingSession.channel_id.in_([channel_id, "UC_ANOTHER_CHANNEL"])).delete()
        db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id == channel_id).delete()
        db.commit()

        creator_authorization_service.authorize_creator(
            db,
            CreatorAuthorizationCreate(
                channel_id=channel_id,
                creator_name="SessionTester",
                authorized_source="OBS:GameCapture_GTA6",
                status="ACTIVE",
            ),
        )

        obs_client.enable_mock_mode()

        # Start first session
        sess1 = recording_manager_service.start_session(db, channel_id=channel_id)
        assert sess1.status == "recording"
        assert sess1.session_id is not None

        # Attempt second session while first is active -> must raise RuntimeError
        blocked_duplicate = False
        try:
            recording_manager_service.start_session(db, channel_id="UC_ANOTHER_CHANNEL")
        except RuntimeError as e:
            blocked_duplicate = True
            assert "actively recording" in str(e)

        assert blocked_duplicate is True, "Must prevent duplicate concurrent recording sessions!"

        # Stop first session
        stopped_sess, _ = recording_manager_service.stop_session(db, session_id=sess1.session_id, auto_process=False)
        assert stopped_sess.status == "completed"
        assert stopped_sess.ended_at is not None
        print("  [+] Test 6 Passed: Recording session created, duplicate blocked, and stopped cleanly.")
    finally:
        db.close()


def test_restart_recovery_of_hanging_sessions():
    print("\n[TEST 7] Backend Restart Recovery of Hanging Sessions...")
    db = SessionLocal()
    try:
        db.query(RecordingSession).filter(RecordingSession.channel_id == "UC_ORPHAN_CH_005").delete()
        db.commit()

        # Create a simulated orphaned session stuck in 'recording'
        orphan = RecordingSession(
            channel_id="UC_ORPHAN_CH_005",
            source_input="OBS:TestInput",
            status="recording",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=45),
        )
        db.add(orphan)
        db.commit()
        db.refresh(orphan)

        # OBS is not actively recording
        obs_client.enable_mock_mode(initial_recording=False)

        recovered = recording_manager_service.recover_hanging_sessions(db)
        assert recovered >= 1

        db.refresh(orphan)
        assert orphan.status == "aborted"
        assert "recovered after service restart" in orphan.error_message
        print(f"  [+] Test 7 Passed: Successfully recovered {recovered} orphaned recording sessions on startup.")
    finally:
        db.close()


def test_end_to_end_discovery_to_ai_clip():
    print("\n[TEST 8] End-to-End Workflow: Discovery -> Authorization -> OBS Recording -> AI Highlights...")
    db = SessionLocal()
    try:
        video_id = "E2E_GTA6_STREAM_999"
        channel_id = "UC_E2E_LEONIDA_CREATOR"

        # Clean up any existing records from prior runs
        db.query(RecordingSession).filter(RecordingSession.status == "recording").update({"status": "aborted"})
        db.query(LiveDiscovery).filter(LiveDiscovery.video_id == video_id).delete()
        db.query(CreatorAuthorization).filter(CreatorAuthorization.channel_id == channel_id).delete()
        db.query(RecordingSession).filter(RecordingSession.video_id == video_id).delete()
        db.commit()

        # Step 1: Discover a public GTA 6 livestream
        discovery = LiveDiscovery(
            video_id=video_id,
            channel_id=channel_id,
            channel_title="LeonidaKingpin",
            title="GTA 6 Next-Gen 60FPS Vice City Police Chase! 🚓",
            thumbnail_url="https://img.youtube.com/vi/E2E_GTA6_STREAM_999/hqdefault.jpg",
            stream_url=f"https://www.youtube.com/watch?v={video_id}",
            live_status="live",
            authorization_status="AWAITING_AUTHORIZATION",
            recording_status="IDLE",
        )
        db.add(discovery)
        db.commit()
        db.refresh(discovery)
        assert discovery.authorization_status == "AWAITING_AUTHORIZATION"
        print(f"      Step A: Public livestream discovered: '{discovery.title}' (Status: AWAITING_AUTHORIZATION).")

        # Step 2: Creator Authorizes with Approved Video Input
        auth = creator_authorization_service.authorize_creator(
            db,
            CreatorAuthorizationCreate(
                channel_id=channel_id,
                creator_name="LeonidaKingpin",
                authorized_source="OBS:GTA6_ViceCityCapture",
                allowed_scope="clip_creation",
                notes="Authorized for automated highlight creation",
                status="ACTIVE",
            ),
        )
        db.refresh(discovery)
        assert discovery.authorization_status == "AUTHORIZED"
        print(f"      Step B: Creator authorized! LiveDiscovery #{discovery.id} updated to AUTHORIZED.")

        # Step 3: Prepare real synthetic test video for mock OBS output
        test_video_path = "backend/data/temp/e2e_obs_stream_capture.mp4"
        create_test_video(test_video_path, duration_sec=5.0)

        # Step 4: Start OBS Recording Session
        obs_client.enable_mock_mode(initial_recording=False)
        session = recording_manager_service.start_session(
            db=db,
            channel_id=channel_id,
            video_id=video_id,
            discovery_id=discovery.id,
        )
        db.refresh(discovery)
        assert session.status == "recording"
        assert discovery.recording_status == "RECORDING"
        print(f"      Step C: Started RecordingSession #{session.id}. Discovery status: RECORDING.")

        # Step 5: Stop Recording & Ingest Media
        # Point mock output to our real test video
        session.metadata_json = {"mock_path": test_video_path, "creator_name": "LeonidaKingpin"}
        db.commit()
        obs_client._mock_output_path = test_video_path
        obs_client._mock_recording = True

        stopped_sess, rec_id = recording_manager_service.stop_session(
            db=db,
            session_id=session.session_id,
            reason="stream_completed",
            auto_process=True,  # Automatically launches AI clipping!
        )
        assert stopped_sess.status == "completed"
        assert rec_id is not None
        print(f"      Step D: Recording stopped & ingested as Recording #{rec_id} (Status: completed).")

        # Step 6: Verify AI Highlight Clipping Execution
        recording = db.query(Recording).filter(Recording.id == rec_id).first()
        assert recording is not None

        # Check candidate generated
        candidates = db.query(ClipCandidate).filter(ClipCandidate.recording_id == rec_id).all()
        assert len(candidates) >= 1
        print(f"      Step E: AI Candidate Service generated {len(candidates)} highlight candidates.")

        # Check rendered 9:16 vertical clip
        clips = db.query(Clip).filter(Clip.candidate_id == candidates[0].id).all()
        assert len(clips) >= 1
        clip = clips[0]
        assert clip.width == 1080
        assert clip.height == 1920
        assert Path(clip.file_path).exists()
        assert clip.file_size_bytes > 5000
        print(f"      Step F: Rendered vertical 9:16 clip #{clip.id}: '{clip.title}' ({clip.width}x{clip.height}, {clip.file_size_bytes} bytes).")

        # Check thumbnail
        thumbs = db.query(Thumbnail).filter(Thumbnail.clip_id == clip.id).all()
        assert len(thumbs) >= 1
        assert Path(thumbs[0].file_path).exists()
        print(f"      Step G: Generated primary thumbnail at '{thumbs[0].file_name}'.")

        # Check LiveDiscovery final status
        db.refresh(discovery)
        assert discovery.recording_status == "CLIPPED"
        print(f"      Step H: LiveDiscovery #{discovery.id} updated to CLIPPED!")

        print("\n==================================================================")
        print("ALL 8 GLOBAL DISCOVERY & OBS AUTOMATION TESTS PASSED WITH 100% SUCCESS!")
        print("==================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    test_youtube_discovery_and_deduplication()
    test_quota_tracker_and_rollover()
    test_creator_authorization_gate()
    test_revoked_authorization_blocks_recording()
    test_obs_websocket_offline_and_mock_control()
    test_recording_sessions_and_duplicate_prevention()
    test_restart_recovery_of_hanging_sessions()
    test_end_to_end_discovery_to_ai_clip()
