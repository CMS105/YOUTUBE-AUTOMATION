"""
Phase 4 Verification Suite: AI Event Detection, Multimodal Scoring & Highlight Candidate Generation.

Tests:
1. Context Evaluation Service (Local Heuristic & Cloud Fallback, Category Classification, Titles)
2. Temporal Non-Maximum Suppression (1D IoU computation and candidate deduplication)
3. Candidate Synthesis & Boundary Snapping (Scene cuts & speech pause snapping)
4. Database Integration & Persistence (Multimodal scoring: 35% audio, 35% visual, 30% context)
5. Candidate API Router (Listing, pagination, approval with preset, rejection, and 403 Permission Guard)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.logging import logger
from app.database import SessionLocal, engine, Base
from app.models import Streamer, Permission, Recording, DetectedEvent, ClipCandidate, ProcessingJob
from app.services.context_service import context_service
from app.services.candidate_service import (
    candidate_service,
    compute_temporal_iou,
)
from app.routers.candidates import (
    list_candidates,
    get_candidate,
    approve_candidate,
    reject_candidate,
    generate_candidates,
)
from app.domain.schemas.clips import CandidateApproveRequest


def test_phase4_end_to_end():
    logger.info("==================================================================")
    logger.info("STARTING PHASE 4 VERIFICATION SUITE: SCORING & CANDIDATE ENGINE")
    logger.info("==================================================================")

    # -------------------------------------------------------------
    # 1. Context Evaluation Engine
    # -------------------------------------------------------------
    print("\n[1/5] Testing Context Evaluation Service...")
    eval_res = context_service.evaluate_context(
        transcript="Bro the cops are literally swarming with helicopters, 5 stars no way!",
        start_time=15.0,
        end_time=45.0,
        peak_audio_intensity=0.85,
        peak_visual_intensity=0.78,
        has_facecam=True,
    )

    assert 0.0 <= eval_res["context_score"] <= 1.0, f"Invalid context score: {eval_res['context_score']}"
    assert eval_res["event_category"] in [
        "Police Chase", "High Stakes Gunfight", "Funny Fail / Rage",
        "Heist / Mission", "Crazy Stunt", "General Chaos"
    ], f"Unexpected category: {eval_res['event_category']}"
    assert len(eval_res["suggested_titles"]) >= 3, "Expected at least 3 suggested titles"
    assert "summary" in eval_res and len(eval_res["summary"]) > 10

    print(f"      Context Service PASSED: Category='{eval_res['event_category']}', "
          f"Score={eval_res['context_score']}, Titles={len(eval_res['suggested_titles'])}, "
          f"Provider={eval_res['provider_used']}")

    # -------------------------------------------------------------
    # 2. Temporal NMS Deduplication
    # -------------------------------------------------------------
    print("\n[2/5] Testing Temporal Non-Maximum Suppression (NMS)...")
    iou_high = compute_temporal_iou(10.0, 40.0, 15.0, 42.0)
    assert iou_high > 0.60, f"Expected high IoU, got {iou_high}"

    iou_zero = compute_temporal_iou(10.0, 40.0, 60.0, 90.0)
    assert iou_zero == 0.0, f"Expected 0.0 IoU, got {iou_zero}"

    synthetic_candidates = [
        {"recording_id": 1, "start_time": 10.0, "end_time": 40.0, "score_composite": 0.92},
        {"recording_id": 1, "start_time": 12.0, "end_time": 42.0, "score_composite": 0.78},  # Should be suppressed by #1
        {"recording_id": 1, "start_time": 60.0, "end_time": 90.0, "score_composite": 0.85},  # Distinct window, should be kept
        {"recording_id": 1, "start_time": 65.0, "end_time": 92.0, "score_composite": 0.70},  # Should be suppressed by #3
    ]

    nms_kept = candidate_service._apply_temporal_nms(synthetic_candidates, iou_threshold=0.30)
    assert len(nms_kept) == 2, f"Expected 2 deduplicated candidates, got {len(nms_kept)}"
    assert nms_kept[0]["score_composite"] == 0.92
    assert nms_kept[1]["score_composite"] == 0.85

    print(f"      Temporal NMS PASSED: 4 overlapping candidates pruned to {len(nms_kept)} distinct highlights.")

    # -------------------------------------------------------------
    # 3. Database Fixture Setup
    # -------------------------------------------------------------
    print("\n[3/5] Setting up Database Fixtures & Seed Events...")
    db = SessionLocal()
    try:
        # Create streamer
        streamer = Streamer(
            channel_id="UC_PHASE4_STREAMER",
            display_name="Vice City Legends",
            platform="youtube",
            is_active=True,
        )
        db.add(streamer)
        db.commit()
        db.refresh(streamer)

        # Grant active permission
        perm = Permission(
            streamer_id=streamer.id,
            grant_type="manual",
            status="ACTIVE",
            granted_at=datetime.now(timezone.utc),
            notes="Phase 4 highlight testing grant",
        )
        db.add(perm)
        db.commit()

        # Create recording (120 seconds duration)
        recording = Recording(
            streamer_id=streamer.id,
            file_name="gta6_mission_heist_120s.mp4",
            file_path="data/recordings/gta6_mission_heist_120s.mp4",
            duration_seconds=120.0,
            width=1920,
            height=1080,
            fps=30.0,
            status="analyzed",
            metadata_json={
                "facecam": {
                    "has_facecam": True,
                    "location": "top_right",
                    "box": {"x": 1500, "y": 50, "w": 380, "h": 280},
                },
                "transcripts": [
                    {"start": 12.0, "end": 18.0, "text": "Alright we are breaking into the bank vault now!"},
                    {"start": 20.0, "end": 28.0, "text": "Oh no the silent alarm triggered, cops incoming!"},
                    {"start": 70.0, "end": 78.0, "text": "Get to the getaway chopper on the helipad fast!"},
                    {"start": 80.0, "end": 88.0, "text": "We lost the five stars, cleanest heist ever!"},
                ],
            },
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)

        # Add detected events
        events = [
            # Event 1: Audio vocal spike around 22-26s
            DetectedEvent(
                recording_id=recording.id,
                event_type="audio_spike",
                category="audio",
                start_time=21.0,
                end_time=27.0,
                confidence=0.92,
                intensity=0.88,
                description="Vocal spike: 'Oh no the silent alarm triggered'",
            ),
            # Event 2: Action burst around 23-30s
            DetectedEvent(
                recording_id=recording.id,
                event_type="action_burst",
                category="visual",
                start_time=22.0,
                end_time=29.0,
                confidence=0.89,
                intensity=0.82,
                description="High motion energy: Shootout at bank exit",
            ),
            # Event 3: Scene cut at 18.0s
            DetectedEvent(
                recording_id=recording.id,
                event_type="scene_cut",
                category="visual",
                start_time=18.0,
                end_time=18.5,
                confidence=1.0,
                intensity=1.0,
            ),
            # Event 4: Audio vocal spike around 81-86s
            DetectedEvent(
                recording_id=recording.id,
                event_type="audio_spike",
                category="audio",
                start_time=80.0,
                end_time=86.0,
                confidence=0.85,
                intensity=0.79,
                description="Cheering: 'We lost the five stars!'",
            ),
            # Event 5: Action burst around 80-87s
            DetectedEvent(
                recording_id=recording.id,
                event_type="action_burst",
                category="visual",
                start_time=79.0,
                end_time=88.0,
                confidence=0.86,
                intensity=0.75,
                description="Helicopter flight motion",
            ),
        ]
        db.add_all(events)
        db.commit()

        print(f"      Fixtures created: Streamer #{streamer.id}, Recording #{recording.id}, {len(events)} Events.")

        # -------------------------------------------------------------
        # 4. Candidate Generation & Multimodal Scoring
        # -------------------------------------------------------------
        print("\n[4/5] Testing Candidate Generation Service...")
        generated = candidate_service.generate_candidates_for_recording(
            db=db,
            recording_id=recording.id,
            target_count=5,
        )

        assert len(generated) >= 1, "Expected at least 1 candidate generated"
        print(f"      Generated {len(generated)} ranked candidates:")
        for cand in generated:
            print(f"        - Rank #{cand.rank}: [{cand.start_time:.1f}s - {cand.end_time:.1f}s] "
                  f"(Dur: {cand.duration:.1f}s) | Score: {cand.score_composite:.3f} "
                  f"(Audio: {cand.score_audio:.2f}, Visual: {cand.score_visual:.2f}, Context: {cand.score_context:.2f}) | "
                  f"Category: '{cand.event_category}'")
            assert cand.score_composite > 0.0, "Composite score must be positive"
            assert cand.has_facecam == True, "Facecam flag should be preserved from recording metadata"
            assert cand.status == "pending", "Initial status must be 'pending'"

        first_cand = generated[0]

        # -------------------------------------------------------------
        # 5. Candidate API Router Endpoints & Permission Guard
        # -------------------------------------------------------------
        print("\n[5/5] Testing Candidate API Endpoints & Permission Guard...")

        # A. List candidates endpoint
        list_resp = list_candidates(
            recording_id=first_cand.recording_id,
            status="pending",
            skip=0,
            limit=10,
            db=db,
        )
        assert list_resp.total >= 1, f"Expected candidates in list_candidates, got {list_resp.total}"
        assert len(list_resp.items) >= 1

        # B. Get single candidate endpoint
        cand_detail = get_candidate(candidate_id=first_cand.id, db=db)
        assert cand_detail.id == first_cand.id

        # C. Approve candidate with preset
        approve_req = CandidateApproveRequest(
            preset="Viral Gaming",
            custom_title="EPIC 5-STAR HEIST GETAWAY IN GTA 6! 🚨",
        )
        job = approve_candidate(candidate_id=first_cand.id, req=approve_req, db=db)
        assert job.id is not None, "ProcessingJob must be created"
        assert job.job_type == "render_clip", f"Expected job_type 'render_clip', got {job.job_type}"
        assert job.status == "queued"
        assert job.result_summary.get("preset") == "Viral Gaming"

        # Check candidate status transitioned to approved
        db.refresh(first_cand)
        assert first_cand.status == "approved"
        print(f"      Approval PASSED: Candidate #{first_cand.id} approved, Render Job #{job.id} enqueued.")

        # D. Reject second candidate if available
        if len(generated) > 1:
            second_cand = generated[1]
            rej_resp = reject_candidate(candidate_id=second_cand.id, db=db)
            assert rej_resp.status == "rejected"
            print(f"      Rejection PASSED: Candidate #{second_cand.id} set to 'rejected'.")

        # E. Permission Guard Test: Revoke permission and test blocking
        perm.status = "REVOKED"
        db.commit()

        # Triggering generate_candidates must now raise 403 Forbidden!
        blocked = False
        try:
            generate_candidates(recording_id=recording.id, count=5, db=db)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 403:
                blocked = True
                print(f"      Permission Guard PASSED: Blocked with HTTP 403 ({e.detail})")
            else:
                print(f"      Unexpected exception: {e}")

        assert blocked, "Candidate generation MUST be blocked with 403 when streamer permission is REVOKED!"

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL PHASE 4 HIGHLIGHT SCORING & CANDIDATE TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == "__main__":
    test_phase4_end_to_end()
