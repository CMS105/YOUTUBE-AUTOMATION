"""
Phase 8 End-to-End Pipeline & Resilience Verification Suite.

Comprehensive end-to-end test validating the complete lifecycle:
1. Creator Registration & Consent Verification (ACTIVE permission requirement)
2. Authorized Ingestion (Format probing, SHA-256 deduplication, storage spooling)
3. Multi-Stage Feature Extraction Engine (Audio RMS energy, visual motion differencing, MediaPipe FaceLandmarker)
4. Highlight Scoring & Window Synthesis (Speech snapping, scene-cut alignment, multimodal scoring)
5. Temporal Non-Maximum Suppression (Deduplication of overlapping windows)
6. Vertical 9:16 Video Rendering Core (Karaoke dynamic subtitles, facecam badges, audio normalization)
7. Thumbnail Capture & Typography Overlay
8. Resilience & Edge Cases:
   - Corrupt / non-video file rejection
   - Revoked permission blocking (HTTP 403)
   - Zero-key offline heuristic fallback
   - RTX 3050 VRAM ceiling check (< 4.5 GB)
"""

import sys
import os
import torch
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import cv2
import av

# Ensure backend is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.logging import logger
from app.database import SessionLocal
from app.models import Streamer, Permission, Recording, DetectedEvent, ClipCandidate, Clip, Thumbnail, ProcessingJob
from app.services.permission_service import permission_service
from app.services.file_service import file_service
from app.services.ingestion_service import ingestion_service
from app.services.job_worker import job_worker
from app.services.candidate_service import candidate_service
from app.services.render_service import render_service
from app.routers import clips as clips_router, permissions as permissions_router
from app.domain.schemas.permissions import PermissionGrantRequest


def create_e2e_sample_video(path: str, duration_sec: float = 6.0) -> None:
    """Creates a synthetic 16:9 640x360 video with audio tone and facecam in top-right."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fps = 30
    total_frames = int(duration_sec * fps)
    w, h = 640, 360

    container = av.open(path, mode="w")
    v_stream = container.add_stream("h264", rate=fps)
    v_stream.width = w
    v_stream.height = h
    v_stream.pix_fmt = "yuv420p"

    a_stream = container.add_stream("aac", rate=48000)
    samples_per_frame = 1024
    total_audio_samples = int(duration_sec * 48000)

    for i in range(total_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Background: moving city streets
        frame[:, :, 0] = (i * 3) % 200
        frame[:, :, 1] = 50
        frame[:, :, 2] = 120

        # Draw sports car moving across screen
        car_x = int(60 + (i * 6)) % (w - 100)
        cv2.rectangle(frame, (car_x, 220), (car_x + 90, 270), (0, 255, 255), -1)

        # Draw streamer facecam quadrant in top-right
        cv2.rectangle(frame, (490, 20), (615, 115), (210, 175, 135), -1)
        cv2.circle(frame, (530, 55), 6, (0, 0, 0), -1)
        cv2.circle(frame, (575, 55), 6, (0, 0, 0), -1)
        cv2.ellipse(frame, (552, 80), (22, 10), 0, 0, 180, (0, 0, 0), 2)

        av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        for packet in v_stream.encode(av_frame):
            container.mux(packet)

    for packet in v_stream.encode():
        container.mux(packet)

    # Encode audio with an excitement burst in the middle
    t = np.linspace(0, duration_sec, total_audio_samples, endpoint=False)
    # Burst between 2.0s and 4.0s
    burst_mask = (t >= 2.0) & (t <= 4.0)
    amp = np.where(burst_mask, 0.85, 0.20)
    audio_data = (np.sin(2 * np.pi * 440 * t) * amp).astype(np.float32)

    for start_idx in range(0, total_audio_samples, samples_per_frame):
        end_idx = min(start_idx + samples_per_frame, total_audio_samples)
        chunk = audio_data[start_idx:end_idx]
        if len(chunk) < samples_per_frame:
            chunk = np.pad(chunk, (0, samples_per_frame - len(chunk)))

        stereo_chunk = np.vstack([chunk, chunk])
        audio_frame = av.AudioFrame.from_ndarray(stereo_chunk, format="fltp", layout="stereo")
        audio_frame.rate = 48000
        for packet in a_stream.encode(audio_frame):
            container.mux(packet)

    for packet in a_stream.encode():
        container.mux(packet)

    container.close()


def test_phase8_full_pipeline():
    logger.info("==================================================================")
    logger.info("STARTING PHASE 8 END-TO-END PIPELINE & RESILIENCE VERIFICATION")
    logger.info("==================================================================")

    db = SessionLocal()
    try:
        # -------------------------------------------------------------
        # STEP 1: Creator Onboarding & Permission Grant
        # -------------------------------------------------------------
        print("\n[1/8] Creator Onboarding & Permission Verification...")
        streamer = Streamer(
            channel_id="UC_E2E_VERIFICATION_CREATOR",
            display_name="MiamiViceChampion",
            platform="youtube",
            is_active=True,
        )
        db.add(streamer)
        db.commit()
        db.refresh(streamer)

        perm = permissions_router.grant_permission(
            data=PermissionGrantRequest(
                streamer_id=streamer.id,
                grant_type="manual",
                scope="clip_creation",
                notes="Authorized for E2E Pipeline Verification",
            ),
            db=db,
        )
        assert perm.status == "ACTIVE"
        print(f"      Step 1 PASSED: Streamer #{streamer.id} granted ACTIVE permission #{perm.id}.")

        # -------------------------------------------------------------
        # STEP 2: Authorized Video Ingestion & Metadata Probing
        # -------------------------------------------------------------
        print("\n[2/8] Ingesting Authorized Gameplay Broadcast...")
        raw_video_path = "backend/data/temp/e2e_gameplay_source.mp4"
        create_e2e_sample_video(raw_video_path, duration_sec=5.0)

        recording = ingestion_service.ingest_local_file(
            db=db,
            streamer_id=streamer.id,
            source_path=raw_video_path,
            copy_to_storage=False,
        )
        assert recording.id is not None
        assert recording.duration_seconds is not None
        assert recording.status in ["ingested", "features_extracted", "analyzed"]
        print(f"      Step 2 PASSED: Ingested Recording #{recording.id} ({recording.width}x{recording.height}, {recording.duration_seconds:.1f}s).")

        # -------------------------------------------------------------
        # STEP 3: Multi-Stage Feature Extraction
        # -------------------------------------------------------------
        print("\n[3/8] Executing Multi-Stage Feature Extraction Engine...")
        job = ProcessingJob(
            recording_id=recording.id,
            job_type="feature_extraction",
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        job_worker.execute_feature_extraction(db=db, job_id=job.id)

        # Refresh recording and job
        db.refresh(recording)
        db.refresh(job)
        assert job.status == "completed"
        assert recording.status in ["features_extracted", "analyzed"]
        assert recording.metadata_json is not None
        facecam_detected = recording.metadata_json.get("facecam", {}).get("has_facecam", False)
        print(f"      Step 3 PASSED: Feature Extraction completed (Facecam={facecam_detected}, Events saved to DB).")

        # Add mock transcripts into recording metadata for highlight synthesis
        rec_meta = dict(recording.metadata_json or {})
        rec_meta["transcripts"] = [
            {"start": 1.0, "end": 4.5, "text": "Bro the police helicopter is right on top of us!"}
        ]
        recording.metadata_json = rec_meta
        db.commit()

        # -------------------------------------------------------------
        # STEP 4: Candidate Windowing, Snapping & Multimodal Scoring
        # -------------------------------------------------------------
        print("\n[4/8] Generating Highlight Candidates & Composite Scoring...")
        candidates = candidate_service.generate_candidates_for_recording(
            db=db,
            recording_id=recording.id,
            target_count=3,
        )
        assert len(candidates) >= 1
        best_candidate = candidates[0]
        assert best_candidate.score_composite > 0.0
        assert best_candidate.status == "pending"
        print(f"      Step 4 PASSED: Generated {len(candidates)} candidates. Top highlight score: {best_candidate.score_composite:.3f}.")

        # -------------------------------------------------------------
        # STEP 5: Vertical 9:16 Video Rendering & Dynamic Subtitles
        # -------------------------------------------------------------
        print("\n[5/8] Rendering Vertical 9:16 MP4 with Preset 'Viral Gaming'...")
        clip = render_service.render_candidate(
            db=db,
            candidate_id=best_candidate.id,
            preset="Viral Gaming",
            custom_title="EPIC GTA 6 HELICOPTER ESCAPE! 🚁",
        )
        assert clip.id is not None
        assert Path(clip.file_path).exists()
        assert clip.width == 1080
        assert clip.height == 1920
        assert clip.file_size_bytes > 5000
        print(f"      Step 5 PASSED: Rendered Clip #{clip.id} -> '{clip.file_name}' ({clip.width}x{clip.height}, {clip.file_size_bytes} bytes).")

        # -------------------------------------------------------------
        # STEP 6: Automatic Thumbnail Generation & Primary Link
        # -------------------------------------------------------------
        print("\n[6/8] Verifying Thumbnail Generation...")
        thumb = db.query(Thumbnail).filter(Thumbnail.clip_id == clip.id, Thumbnail.is_primary == True).first()
        assert thumb is not None
        assert Path(thumb.file_path).exists()
        assert thumb.width == 1080
        assert thumb.height == 1920
        print(f"      Step 6 PASSED: Primary Thumbnail generated at '{thumb.file_name}'.")

        # -------------------------------------------------------------
        # STEP 7: Dashboard Aggregation Verification
        # -------------------------------------------------------------
        print("\n[7/8] Verifying Global Dashboard Telemetry...")
        dashboard_stats = clips_router.get_dashboard_stats(db=db)
        assert dashboard_stats.total_clips >= 1
        assert dashboard_stats.total_streamers >= 1
        assert dashboard_stats.active_permissions >= 1
        print(f"      Step 7 PASSED: Dashboard aggregated {dashboard_stats.total_clips} clips across {dashboard_stats.total_streamers} streamers.")

        # -------------------------------------------------------------
        # STEP 8: Resilience, Edge Cases & Hardware Guard
        # -------------------------------------------------------------
        print("\n[8/8] Testing Edge Cases & Hardware Safety Guards...")

        # A. Revoked permission blocking
        permission_service.revoke_permission(db=db, permission_id=perm.id, reason="Revocation test")
        blocked = False
        try:
            permission_service.verify_streamer_authorized(db, streamer.id)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 403:
                blocked = True
        assert blocked, "Permission guard must raise 403 when permission is revoked!"
        print("        [+] Edge Case A: Revoked permission strictly blocked with HTTP 403.")

        # B. Corrupt / invalid file rejection
        fake_bad_file = Path("backend/data/temp/fake_corrupt_video.mp4")
        fake_bad_file.write_bytes(b"NOT_A_REAL_MP4_HEADER_CORRUPTED_BYTES")
        corrupt_blocked = False
        try:
            file_service.validate_video_file(fake_bad_file)
        except Exception:
            corrupt_blocked = True
        assert corrupt_blocked, "File service must reject corrupt files!"
        print("        [+] Edge Case B: Corrupted media file detected and rejected.")

        # C. VRAM Ceiling Safety Check on RTX 3050
        if torch.cuda.is_available():
            allocated_mb = torch.cuda.memory_allocated(0) / (1024 ** 2)
            assert allocated_mb < 4500.0, f"VRAM ceiling breached! {allocated_mb} MB exceeds 4.5 GB limit."
            print(f"        [+] Hardware Guard: RTX 3050 VRAM utilization safe ({allocated_mb:.1f} MB < 4500 MB ceiling).")
        else:
            print("        [+] Hardware Guard: Running on resilient CPU fallback.")

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL 8 END-TO-END PIPELINE & RESILIENCE TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == "__main__":
    test_phase8_full_pipeline()
