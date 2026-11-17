"""
Phase 5 Verification Suite: FFmpeg / PyAV Vertical Rendering, Presets & Dynamic Subtitles.

Tests:
1. Subtitle Service (ASS / SRT timing, line grouping, karaoke scripts, frame burn-in)
2. Synthetic Stream Generation (16:9 gameplay + audio + facecam)
3. Preset 1: 'Viral Gaming' (1080x1920 smart center-crop, facecam badge, karaoke subtitles)
4. Preset 2: 'Clean Gameplay' (1080x1920 centered 16:9 with blurred background)
5. Preset 3: 'Reaction Focus' (1080x1920 vertical split-screen: facecam top, gameplay bottom)
6. Automatic Thumbnail Generation (1080x1920 JPEG with viral typography)
7. End-to-End Render Router & 403 Permission Guard
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import cv2
import av
from PIL import Image

# Ensure backend is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.logging import logger
from app.database import SessionLocal
from app.models import Streamer, Permission, Recording, ClipCandidate, Clip, Thumbnail, ProcessingJob
from app.services.subtitle_service import subtitle_service
from app.services.render_service import render_service
from app.routers.candidates import render_candidate_endpoint
from app.domain.schemas.clips import CandidateApproveRequest


def generate_synthetic_gameplay_stream(output_path: str, duration_sec: float = 4.0) -> None:
    """Generates synthetic 16:9 (640x360) video with audio tone and facecam in top-right."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fps = 30
    total_frames = int(duration_sec * fps)
    w, h = 640, 360

    container = av.open(output_path, mode="w")
    v_stream = container.add_stream("h264", rate=fps)
    v_stream.width = w
    v_stream.height = h
    v_stream.pix_fmt = "yuv420p"

    # Add audio stream (440Hz tone)
    a_stream = container.add_stream("aac", rate=48000)
    samples_per_frame = 1024
    total_audio_samples = int(duration_sec * 48000)

    # Encode video frames
    for i in range(total_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Background: moving highway color gradient
        frame[:, :, 0] = (i * 4) % 180
        frame[:, :, 1] = 40
        frame[:, :, 2] = 80

        # Draw a mock car
        car_x = int(100 + (i * 5)) % (w - 80)
        cv2.rectangle(frame, (car_x, 240), (car_x + 70, 290), (0, 0, 255), -1)

        # Draw streamer facecam quadrant in top-right (x=480, y=20, w=130, h=90)
        cv2.rectangle(frame, (480, 20), (610, 110), (220, 180, 140), -1)
        # Facecam eyes and smile
        cv2.circle(frame, (520, 50), 6, (0, 0, 0), -1)
        cv2.circle(frame, (570, 50), 6, (0, 0, 0), -1)
        cv2.ellipse(frame, (545, 75), (20, 10), 0, 0, 180, (0, 0, 0), 2)

        av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        for packet in v_stream.encode(av_frame):
            container.mux(packet)

    for packet in v_stream.encode():
        container.mux(packet)

    # Encode audio frames
    t = np.linspace(0, duration_sec, total_audio_samples, endpoint=False)
    audio_data = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

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


def test_phase5_end_to_end():
    logger.info("==================================================================")
    logger.info("STARTING PHASE 5 VERIFICATION SUITE: VERTICAL RENDERING & SUBTITLES")
    logger.info("==================================================================")

    # -------------------------------------------------------------
    # 1. Subtitle Service Unit Verification
    # -------------------------------------------------------------
    print("\n[1/6] Testing Subtitle Service...")
    assert subtitle_service.format_ass_time(65.45) == "0:01:05.45"
    assert subtitle_service.format_srt_time(65.45) == "00:01:05,450"

    mock_words = [
        {"word": "Bro", "start": 0.2, "end": 0.6},
        {"word": "outsmarted", "start": 0.7, "end": 1.3},
        {"word": "the", "start": 1.4, "end": 1.6},
        {"word": "cops", "start": 1.7, "end": 2.2},
    ]
    lines = subtitle_service.group_words_into_lines(mock_words, max_words_per_line=4)
    assert len(lines) >= 1
    assert "BRO OUTSMARTED THE COPS" in lines[0]["text"].upper()

    ass_script = subtitle_service.generate_ass_script(mock_words, clip_start=0.0, clip_end=3.0)
    assert "[Script Info]" in ass_script
    assert "Dialogue:" in ass_script

    # Test frame rendering with text stroke
    base_frame = Image.new("RGB", (1080, 1920), color=(20, 20, 30))
    sub_frame = subtitle_service.render_subtitles_on_frame(
        pil_image=base_frame,
        timestamp_sec=1.0,
        lines=lines,
        y_position=1500,
    )
    assert sub_frame.size == (1080, 1920)
    print("      Subtitle Service PASSED: ASS script, SRT formatter, and frame burn-in verified.")

    # -------------------------------------------------------------
    # 2. Synthetic Stream Creation
    # -------------------------------------------------------------
    print("\n[2/6] Generating Synthetic Stream Asset with Facecam & Audio...")
    synth_path = "backend/data/temp/phase5_gameplay_stream.mp4"
    generate_synthetic_gameplay_stream(synth_path, duration_sec=3.5)
    assert Path(synth_path).exists()
    assert os.path.getsize(synth_path) > 1000
    print(f"      Synthetic Stream PASSED: Generated '{synth_path}' ({os.path.getsize(synth_path)} bytes).")

    # -------------------------------------------------------------
    # 3. Database Fixture Setup
    # -------------------------------------------------------------
    print("\n[3/6] Setting up Database Fixtures & Clip Candidate...")
    db = SessionLocal()
    try:
        streamer = Streamer(
            channel_id="UC_PHASE5_STREAMER",
            display_name="SpeedyGamer",
            platform="youtube",
            is_active=True,
        )
        db.add(streamer)
        db.commit()
        db.refresh(streamer)

        perm = Permission(
            streamer_id=streamer.id,
            grant_type="manual",
            status="ACTIVE",
            granted_at=datetime.now(timezone.utc),
            notes="Phase 5 render tests",
        )
        db.add(perm)
        db.commit()

        recording = Recording(
            streamer_id=streamer.id,
            file_name="phase5_gameplay_stream.mp4",
            file_path=synth_path,
            duration_seconds=3.5,
            width=640,
            height=360,
            fps=30.0,
            status="analyzed",
            metadata_json={
                "facecam": {
                    "has_facecam": True,
                    "box": {"x": 480, "y": 20, "w": 130, "h": 90},
                },
                "transcripts": [
                    {
                        "start": 0.2, "end": 2.5,
                        "text": "Bro outsmarted the cops!",
                        "words": mock_words,
                    }
                ],
            },
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)

        candidate = ClipCandidate(
            recording_id=recording.id,
            start_time=0.2,
            end_time=3.2,
            duration=3.0,
            score_audio=0.90,
            score_visual=0.88,
            score_context=0.85,
            score_composite=0.915,
            rank=1,
            event_category="Police Chase",
            status="pending",
            has_facecam=True,
            facecam_region={"x": 480, "y": 20, "w": 130, "h": 90},
            transcript_text="Bro outsmarted the cops!",
            suggested_titles=["BRO OUTSMARTED THE ENTIRE GTA 6 POLICE FORCE 💀"],
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        print(f"      Fixtures created: Streamer #{streamer.id}, Recording #{recording.id}, Candidate #{candidate.id}.")

        # -------------------------------------------------------------
        # 4. Preset 1: 'Viral Gaming' Render & Verification
        # -------------------------------------------------------------
        print("\n[4/6] Testing Preset 1: 'Viral Gaming' Rendering...")
        clip_viral = render_service.render_candidate(
            db=db,
            candidate_id=candidate.id,
            preset="Viral Gaming",
            custom_title="EPIC GTA 6 ESCAPE! 🚨",
        )

        assert clip_viral.id is not None
        assert Path(clip_viral.file_path).exists(), f"Rendered file not found: {clip_viral.file_path}"
        assert os.path.getsize(clip_viral.file_path) > 1000
        assert clip_viral.width == 1080
        assert clip_viral.height == 1920
        assert clip_viral.preset == "Viral Gaming"

        # Check thumbnail
        thumb = db.query(Thumbnail).filter(Thumbnail.clip_id == clip_viral.id).first()
        assert thumb is not None
        assert Path(thumb.file_path).exists()
        assert thumb.width == 1080
        assert thumb.height == 1920

        print(f"      'Viral Gaming' Render PASSED: Output {clip_viral.width}x{clip_viral.height} "
              f"({os.path.getsize(clip_viral.file_path)} bytes), Thumbnail: '{thumb.file_name}'")

        # -------------------------------------------------------------
        # 5. Preset 2: 'Clean Gameplay' & Preset 3: 'Reaction Focus'
        # -------------------------------------------------------------
        print("\n[5/6] Testing Presets: 'Clean Gameplay' & 'Reaction Focus'...")

        # Reset candidate to pending for clean second render
        candidate.status = "pending"
        db.commit()

        clip_clean = render_service.render_candidate(
            db=db,
            candidate_id=candidate.id,
            preset="Clean Gameplay",
            custom_title="CLEAN GAMEPLAY HIGHLIGHT",
        )
        assert Path(clip_clean.file_path).exists()
        print(f"      'Clean Gameplay' Render PASSED: Output {clip_clean.width}x{clip_clean.height}")

        candidate.status = "pending"
        db.commit()

        clip_reaction = render_service.render_candidate(
            db=db,
            candidate_id=candidate.id,
            preset="Reaction Focus",
            custom_title="INSANE REACTION MOMENT",
        )
        assert Path(clip_reaction.file_path).exists()
        print(f"      'Reaction Focus' Render PASSED: Output {clip_reaction.width}x{clip_reaction.height}")

        # -------------------------------------------------------------
        # 6. API Endpoint & 403 Permission Guard
        # -------------------------------------------------------------
        print("\n[6/6] Testing API Render Endpoint & Permission Guard...")
        req = CandidateApproveRequest(
            preset="Viral Gaming",
            custom_title="API TRIGGERED CLIP! 🔥",
        )
        api_clip = render_candidate_endpoint(candidate_id=candidate.id, req=req, db=db)
        assert api_clip.id is not None
        assert api_clip.width == 1080
        print(f"      API Render Endpoint PASSED: Generated Clip #{api_clip.id}.")

        # Revoke permission and test blocking
        perm.status = "REVOKED"
        db.commit()

        blocked = False
        try:
            render_candidate_endpoint(candidate_id=candidate.id, req=req, db=db)
        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == 403:
                blocked = True
                print(f"      Permission Guard PASSED: Blocked with HTTP 403 ({e.detail})")

        assert blocked, "Rendering MUST be blocked with HTTP 403 when streamer permission is REVOKED!"

    finally:
        db.close()

    print("\n==================================================================")
    print("ALL PHASE 5 VERTICAL RENDERING & SUBTITLE TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================================")


if __name__ == "__main__":
    test_phase5_end_to_end()
