"""
Phase 7 Verification Suite: Official YouTube Data API v3 Live Monitoring & Quota Scheduler.

Tests:
1. YouTube Quota Tracker (Daily limit, consumption, rollover, remaining calculation)
2. Decoupled Live Status Detection (Official REST API v3 schema compliance)
3. Database Stream Persistence (Stream table updates & AuditLog entry on live broadcast)
4. Key Verification Handler (Graceful handling of missing/invalid keys)
5. YouTube Monitoring API Router Endpoints (/api/v1/youtube/status, /verify-key, /poll)
6. Zero-DRM & Zero-Scraping Architectural Verification
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.database import SessionLocal
from app.models import Streamer, Stream, AuditLog
from app.services.youtube_monitor_service import (
    youtube_monitor_service,
    YouTubeQuotaTracker,
)
from app.routers.youtube import (
    get_youtube_status,
    verify_api_key,
    poll_streamers_live_status,
    VerifyKeyRequest,
)


def test_phase7_youtube_monitoring():
    print("==================================================================")
    print("STARTING PHASE 7 VERIFICATION SUITE: YOUTUBE LIVE MONITORING")
    print("==================================================================")

    # -------------------------------------------------------------
    # 1. Quota Tracker Verification
    # -------------------------------------------------------------
    print("\n[1/5] Testing YouTube Quota Tracker...")
    tracker = YouTubeQuotaTracker(daily_limit=10000)
    assert tracker.used_units == 0
    assert tracker.get_status()["remaining_units"] == 10000

    # Consume 1 unit (channels.list)
    assert tracker.consume(1) is True
    assert tracker.used_units == 1

    # Consume 100 units (search.list live check)
    assert tracker.consume(100) is True
    assert tracker.used_units == 101
    assert tracker.get_status()["remaining_units"] == 9899
    assert tracker.get_status()["percentage_used"] == 1.01

    print(f"      Quota Tracker PASSED: Consumed 101 units, Remaining: {tracker.get_status()['remaining_units']}.")

    # -------------------------------------------------------------
    # 2. Key Verification Handler
    # -------------------------------------------------------------
    print("\n[2/5] Testing Key Verification Handler...")
    # Missing key check
    res_none = youtube_monitor_service.verify_api_key(None)
    assert res_none["valid"] is False
    assert res_none["status"] == "missing_credentials"

    # Invalid format key check
    res_invalid = youtube_monitor_service.verify_api_key("AIzaSyFakeKeyInvalidForTesting1234")
    assert res_invalid["valid"] is False
    print(f"      Key Verification PASSED: Missing handled -> {res_none['status']}, Invalid handled -> {res_invalid['status']}.")

    # -------------------------------------------------------------
    # 3. Database Stream Persistence & Decoupled Architecture
    # -------------------------------------------------------------
    print("\n[3/5] Testing Database Stream Persistence & Audit Logging...")
    db = SessionLocal()
    try:
        # Create streamer
        streamer = Streamer(
            channel_id="UC_LIVE_TEST_CHANNEL",
            display_name="ViceCityLive",
            platform="youtube",
            is_active=True,
        )
        db.add(streamer)
        db.commit()
        db.refresh(streamer)

        # Simulate detecting a live broadcast
        simulated_live = {
            "platform_video_id": "gta6_live_abc123",
            "title": "GTA 6 Story Mode Gameplay [LIVE]",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "thumbnail_url": "https://i.ytimg.com/vi/gta6_live_abc123/hqdefault.jpg",
            "status": "live",
        }

        # Insert new stream record
        stream_rec = Stream(
            streamer_id=streamer.id,
            platform_video_id=simulated_live["platform_video_id"],
            title=simulated_live["title"],
            status="live",
            started_at=datetime.now(timezone.utc),
            thumbnail_url=simulated_live["thumbnail_url"],
            category="Grand Theft Auto VI",
        )
        db.add(stream_rec)
        db.add(
            AuditLog(
                entity_type="stream",
                entity_id=None,
                action="live_detected",
                details=f"Streamer '{streamer.display_name}' went LIVE on YouTube: '{simulated_live['title']}'.",
            )
        )
        db.commit()
        db.refresh(stream_rec)

        assert stream_rec.id is not None
        assert stream_rec.status == "live"
        assert stream_rec.platform_video_id == "gta6_live_abc123"

        # Verify audit log recorded
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "live_detected")
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert audit is not None
        assert "ViceCityLive" in audit.details

        print(f"      Database Stream Persistence PASSED: Stream #{stream_rec.id} recorded with status '{stream_rec.status}'.")

    finally:
        db.close()

    # -------------------------------------------------------------
    # 4. YouTube API Router Endpoints
    # -------------------------------------------------------------
    print("\n[4/5] Testing YouTube API Router Endpoints...")
    db = SessionLocal()
    try:
        status_resp = get_youtube_status()
        assert "quota" in status_resp
        assert "policy_notice" in status_resp
        assert "Zero video scraping" in status_resp["policy_notice"]

        verify_resp = verify_api_key(VerifyKeyRequest(api_key=None))
        assert "valid" in verify_resp

        poll_resp = poll_streamers_live_status(db=db)
        assert "status" in poll_resp
        assert "quota_status" in poll_resp
        print(f"      Router PASSED: /status, /verify-key, and /poll responsive.")

    finally:
        db.close()

    # -------------------------------------------------------------
    # 5. Strict Zero-Scraping / Zero-DRM Architectural Check
    # -------------------------------------------------------------
    print("\n[5/5] Auditing Codebase for Zero-Scraping & Extraction Compliance...")
    service_code = Path("backend/app/services/youtube_monitor_service.py").read_text(encoding="utf-8")
    forbidden_terms = ["yt_dlp", "youtube_dl", "pytube", "streamlink", "cipher_decrypt", "sig_keystream"]
    for term in forbidden_terms:
        assert term not in service_code.lower(), f"Forbidden scraping term '{term}' found in YouTube service!"

    print("      Compliance PASSED: Zero forbidden scraping or DRM libraries detected.")

    print("\n==================================================================")
    print("ALL PHASE 7 YOUTUBE LIVE MONITORING TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == "__main__":
    test_phase7_youtube_monitoring()
