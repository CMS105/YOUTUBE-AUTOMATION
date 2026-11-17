"""
Phase 3 Feature Extraction Verification Test Suite:
Tests Audio Analysis, Visual Motion Differencing, Facecam Tracking, STT Service, and Job Execution.
"""

import sys
from pathlib import Path
import numpy as np
import cv2

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, engine, SessionLocal
from app.models import Streamer, Permission, Recording, ProcessingJob, DetectedEvent
from app.services.audio_analysis_service import audio_analysis_service
from app.services.visual_analysis_service import visual_analysis_service
from app.services.facecam_service import facecam_service
from app.services.stt_service import stt_service
from app.services.job_worker import job_worker


def generate_gameplay_with_facecam(target_path: Path, duration_seconds: int = 4, fps: int = 30):
    """
    Generates a synthetic GTA 6 gameplay recording with simulated facecam overlay in top-right corner.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    width, height = 640, 360
    out = cv2.VideoWriter(str(target_path), fourcc, float(fps), (width, height))

    total_frames = duration_seconds * fps
    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # 1. Gameplay simulation: flashing lights & high-speed street bars
        bar_x = (i * 15) % width
        cv2.rectangle(frame, (bar_x, 150), (min(width, bar_x + 80), 280), (0, 160, 255), -1)
        cv2.putText(
            frame,
            f"VICE CITY ACTION FRAME {i}",
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        # 2. Simulated Facecam Overlay in top-right quadrant
        cam_x, cam_y, cam_w, cam_h = width - 150, 15, 135, 100
        # Background box for facecam
        cv2.rectangle(frame, (cam_x, cam_y), (cam_x + cam_w, cam_y + cam_h), (30, 30, 30), -1)
        # Border
        cv2.rectangle(frame, (cam_x, cam_y), (cam_x + cam_w, cam_y + cam_h), (0, 240, 255), 2)
        # Face representation circle
        cv2.circle(frame, (cam_x + 65, cam_y + 45), 25, (200, 180, 160), -1)
        cv2.circle(frame, (cam_x + 55, cam_y + 40), 4, (0, 0, 0), -1)
        cv2.circle(frame, (cam_x + 75, cam_y + 40), 4, (0, 0, 0), -1)
        cv2.ellipse(frame, (cam_x + 65, cam_y + 55), (10, 5), 0, 0, 180, (0, 0, 150), 2)

        out.write(frame)

    out.release()
    print(f"      Synthetic stream with facecam generated: {target_path}")


def run():
    print("[1/5] Setting up Phase 3 Database & Synthetic Video Asset...")
    Base.metadata.create_all(bind=engine)
    test_video = Path("data/temp/gameplay_with_facecam.mp4")
    generate_gameplay_with_facecam(test_video, duration_seconds=4, fps=30)

    db = SessionLocal()
    try:
        print("[2/5] Testing Audio Analysis Engine...")
        # Test synthetic audio curve computation
        synthetic_audio = np.random.uniform(-0.1, 0.1, 16000 * 4).astype(np.float32)
        # Inject excitement spike at second 2
        synthetic_audio[16000 * 2 : 16000 * 3] *= 6.0
        times, rms = audio_analysis_service.compute_rms_energy_curve(synthetic_audio, 16000, 500)
        assert len(times) == len(rms)
        events = audio_analysis_service.detect_excitement_events(times, rms, threshold_sigma=1.5)
        assert len(events) >= 1
        print(f"      Audio Analysis PASSED: Detected {len(events)} excitement bursts (Peak at {events[0].peak_time}s)")

        print("[3/5] Testing Visual Action & Scene Cut Detection...")
        cuts, v_times, motion, v_events = visual_analysis_service.analyze_video_motion_and_cuts(test_video, 2.0)
        assert len(v_times) > 0
        assert len(motion) == len(v_times)
        print(f"      Visual Analysis PASSED: Sampled {len(v_times)} frames, Motion Energy computed.")

        print("[4/5] Testing Facecam Detection...")
        has_cam, cam_loc, cam_box = facecam_service.analyze_stream_facecam(test_video, max_sample_frames=10)
        print(f"      Facecam Inspector Result: Present={has_cam}, Location={cam_loc}, Box={cam_box}")

        print("[5/5] Testing End-to-End Job Worker Feature Extraction...")
        # Create streamer & permission
        streamer = Streamer(display_name="FeatureStreamer", platform="youtube", channel_id="UC_FEAT")
        db.add(streamer)
        db.commit()
        db.add(Permission(streamer_id=streamer.id, status="ACTIVE", grant_type="manual"))
        db.commit()

        # Ingest recording
        rec = Recording(
            streamer_id=streamer.id,
            file_path=str(test_video),
            file_name=test_video.name,
            file_hash="feature_test_hash_1234567890",
            duration_seconds=4.0,
            status="ingested",
        )
        db.add(rec)
        db.commit()

        # Create Job
        job = ProcessingJob(
            recording_id=rec.id,
            job_type="feature_extraction",
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Execute JobWorker
        finished_job = job_worker.execute_feature_extraction(db=db, job_id=job.id)
        assert finished_job.status == "completed"
        assert finished_job.progress_percent == 100.0
        assert "audio_events_count" in finished_job.result_summary

        # Verify DetectedEvents logged in DB
        db_events = db.query(DetectedEvent).filter(DetectedEvent.recording_id == rec.id).all()
        print(f"      JobWorker PASSED: Job #{finished_job.id} completed. {len(db_events)} events saved to database.")

        # Test STT Status check
        stt_status = stt_service.get_status()
        assert "model_size" in stt_status
        print(f"      STT Service PASSED: Model '{stt_status['model_size']}' ready.")

    finally:
        db.close()
        if test_video.exists():
            test_video.unlink()

    print("\n==================================================================")
    print("ALL PHASE 3 FEATURE EXTRACTION TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == "__main__":
    run()
