"""
Phase 2 Verification Test Suite:
Tests Permission Management, File Validation, Video Ingestion, and Retention Policies.
"""

import os
import sys
import numpy as np
import cv2
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, engine, SessionLocal
from app.models import Streamer, Permission, Recording
from app.services.permission_service import permission_service
from app.services.file_service import file_service
from app.services.ingestion_service import ingestion_service
from app.services.retention_service import retention_service
from app.routers import ingestion


def create_synthetic_mp4(target_path: Path, duration_seconds: int = 3, fps: int = 30):
    """Generates a small valid MP4 test video using OpenCV."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    width, height = 640, 360
    out = cv2.VideoWriter(str(target_path), fourcc, float(fps), (width, height))

    total_frames = duration_seconds * fps
    for i in range(total_frames):
        # Create a frame with changing colors and timestamp text
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        color_val = int((i / total_frames) * 255)
        frame[:, :] = (color_val, 120, 255 - color_val)
        cv2.putText(
            frame,
            f"GTA 6 TEST FRAME {i}/{total_frames}",
            (30, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        out.write(frame)
    out.release()
    print(f"      Synthetic test video created at: {target_path} ({target_path.stat().st_size} bytes)")


def run():
    print("[1/5] Setting up Test Database and Synthetic Video Asset...")
    Base.metadata.create_all(bind=engine)
    test_video_path = Path("data/temp/test_gameplay_stream.mp4")
    create_synthetic_mp4(test_video_path, duration_seconds=3, fps=30)

    db = SessionLocal()
    try:
        print("[2/5] Testing Permission Gating on Ingestion...")
        # Create unpermitted streamer
        unpermitted_streamer = Streamer(
            display_name="UnauthorizedUser",
            platform="youtube",
            channel_id="UC_UNAUTH_999",
        )
        db.add(unpermitted_streamer)
        db.commit()
        db.refresh(unpermitted_streamer)

        # Attempt to ingest for unpermitted streamer — MUST FAIL with 403
        try:
            ingestion_service.ingest_local_file(
                db=db,
                streamer_id=unpermitted_streamer.id,
                source_path=str(test_video_path),
            )
            assert False, "Should have raised 403 HTTPException for unpermitted streamer"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403
            print(f"      Permission Gate PASSED: Successfully rejected unpermitted streamer with 403 ({exc.detail})")

        # Now grant permission
        perm = Permission(
            streamer_id=unpermitted_streamer.id,
            status="ACTIVE",
            grant_type="manual",
            scope="clip_creation",
        )
        db.add(perm)
        db.commit()
        print(f"      Granted ACTIVE permission to streamer #{unpermitted_streamer.id}.")

        print("[3/5] Testing Authorized Ingestion & Metadata Probing...")
        rec = ingestion_service.ingest_local_file(
            db=db,
            streamer_id=unpermitted_streamer.id,
            source_path=str(test_video_path),
            copy_to_storage=True,
        )
        assert rec.id is not None
        assert rec.duration_seconds >= 2.9
        assert rec.width == 640
        assert rec.height == 360
        assert rec.fps == 30.0
        assert len(rec.file_hash) == 64  # SHA-256
        print(f"      Authorized Ingestion PASSED: Recording #{rec.id} ({rec.width}x{rec.height}, {rec.fps}fps, {rec.duration_seconds}s)")

        print("[4/5] Testing SHA-256 Deduplication on Ingestion...")
        rec2 = ingestion_service.ingest_local_file(
            db=db,
            streamer_id=unpermitted_streamer.id,
            source_path=str(test_video_path),
        )
        assert rec2.id == rec.id, "Duplicate file hash should return existing recording record"
        print(f"      Deduplication PASSED: Returned existing recording #{rec2.id} without creating duplicate row.")

        print("[5/5] Testing File Validation & Retention Cleanup...")
        # Validate rejection of non-video file
        fake_txt = Path("data/temp/bad_file.txt")
        fake_txt.write_text("not a video")
        try:
            file_service.validate_local_video_file(str(fake_txt))
            assert False, "Should reject .txt file"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 415
            print(f"      Format Validation PASSED: Rejected invalid file extension with 415.")
        finally:
            if fake_txt.exists():
                fake_txt.unlink()

        # Run retention sweep
        sweep_res = retention_service.apply_retention_policy(db, max_days=30)
        assert "purged_count" in sweep_res
        print(f"      Retention Policy PASSED: Evaluated retention rules.")

    finally:
        db.close()
        # Clean up test video
        if test_video_path.exists():
            test_video_path.unlink()

    print("\n==================================================================")
    print("ALL PHASE 2 INGESTION & PERMISSION TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == "__main__":
    run()
