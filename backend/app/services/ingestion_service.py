"""
Media Ingestion Service:
Manages authorized video ingestion, SHA-256 deduplication, and container metadata probing.
Supports FFprobe extraction with OpenCV / PyAV fallback when ffprobe is not present in PATH.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
import cv2
import av

from app.core.config import settings
from app.core.logging import logger
from app.models import Recording, Streamer, AuditLog
from app.services.permission_service import permission_service
from app.services.file_service import file_service


class IngestionService:
    @staticmethod
    def probe_video_metadata(file_path: Path) -> Dict[str, Any]:
        """
        Extracts duration, width, height, fps, and codecs from video container.
        Attempts ffprobe first; falls back to OpenCV and PyAV.
        """
        meta = {
            "duration_seconds": 0.0,
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "codec_video": "h264",
            "codec_audio": "aac",
        }

        # 1. Attempt FFprobe
        try:
            cmd = [
                settings.FFPROBE_PATH,
                "-v", "error",
                "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_name,codec_type",
                "-of", "json",
                str(file_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                if "format" in data and "duration" in data["format"]:
                    meta["duration_seconds"] = float(data["format"]["duration"])
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        meta["width"] = int(stream.get("width", meta["width"]))
                        meta["height"] = int(stream.get("height", meta["height"]))
                        meta["codec_video"] = stream.get("codec_name", meta["codec_video"])
                        fps_str = stream.get("r_frame_rate", "30/1")
                        if "/" in fps_str:
                            num, den = fps_str.split("/")
                            meta["fps"] = round(float(num) / max(float(den), 1), 2)
                    elif stream.get("codec_type") == "audio":
                        meta["codec_audio"] = stream.get("codec_name", meta["codec_audio"])
                return meta
        except Exception as e:
            logger.info(f"FFprobe metadata extraction unavailable ({e}), using OpenCV + PyAV fallback.")

        # 2. Fallback: OpenCV for Video Stream
        try:
            cap = cv2.VideoCapture(str(file_path))
            if cap.isOpened():
                meta["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                meta["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                meta["fps"] = round(cap.get(cv2.CAP_PROP_FPS) or 30.0, 2)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if meta["fps"] > 0 and frame_count > 0:
                    meta["duration_seconds"] = round(frame_count / meta["fps"], 2)
            cap.release()
        except Exception as cv_err:
            logger.warning(f"OpenCV metadata probe failed: {cv_err}")

        # 3. Fallback: PyAV for Audio & Duration Check
        try:
            with av.open(str(file_path)) as container:
                if container.duration:
                    meta["duration_seconds"] = round(container.duration / av.time_base, 2)
                for stream in container.streams:
                    if stream.type == "video" and not meta.get("codec_video"):
                        meta["codec_video"] = stream.codec_context.name
                    elif stream.type == "audio":
                        meta["codec_audio"] = stream.codec_context.name
        except Exception as av_err:
            logger.warning(f"PyAV metadata probe failed: {av_err}")

        return meta

    @classmethod
    def ingest_local_file(
        cls,
        db: Session,
        streamer_id: int,
        source_path: str,
        stream_id: Optional[int] = None,
        copy_to_storage: bool = False,
    ) -> Recording:
        """
        Ingests an authorized local gameplay recording into the system.
        Enforces permission verification, SHA-256 calculation, and database registration.
        """
        # Step 1: Strict Permission Gate
        streamer_perm = permission_service.verify_streamer_authorized(db, streamer_id)

        # Step 2: Validate local file exists and is valid
        valid_path = file_service.validate_local_video_file(source_path)

        # Step 3: Compute SHA-256 hash
        file_hash = file_service.calculate_file_sha256(valid_path)
        file_size = valid_path.stat().st_size

        # Check for duplicate ingestion
        existing = db.query(Recording).filter(Recording.file_hash == file_hash).first()
        if existing:
            logger.info(f"File '{valid_path.name}' already ingested as Recording #{existing.id}.")
            return existing

        # Step 4: Optional copy into managed recordings directory
        dest_path = valid_path
        if copy_to_storage:
            recordings_dir = Path(settings.RECORDINGS_DIR)
            recordings_dir.mkdir(parents=True, exist_ok=True)
            dest_file = recordings_dir / f"{file_hash[:12]}_{valid_path.name}"
            if not dest_file.exists():
                shutil.copy2(valid_path, dest_file)
            dest_path = dest_file

        # Step 5: Probe metadata
        meta = cls.probe_video_metadata(dest_path)

        # Step 6: Create database record
        recording = Recording(
            streamer_id=streamer_id,
            stream_id=stream_id,
            file_path=str(dest_path),
            file_name=valid_path.name,
            file_hash=file_hash,
            file_size_bytes=file_size,
            duration_seconds=meta["duration_seconds"],
            width=meta["width"],
            height=meta["height"],
            fps=meta["fps"],
            codec_video=meta["codec_video"],
            codec_audio=meta["codec_audio"],
            status="ingested",
        )
        db.add(recording)

        # Step 7: Audit Log
        db.add(
            AuditLog(
                entity_type="recording",
                entity_id=None,
                action="ingested",
                details=(
                    f"Recording '{valid_path.name}' ingested for streamer #{streamer_id}. "
                    f"Duration: {meta['duration_seconds']}s, Size: {round(file_size / (1024*1024), 1)} MB. "
                    f"SHA-256: {file_hash[:12]}..."
                ),
            )
        )

        db.commit()
        db.refresh(recording)
        logger.info(
            f"[IngestionService] Successfully ingested Recording #{recording.id} "
            f"('{recording.file_name}', {recording.duration_seconds}s) for Streamer #{streamer_id}."
        )
        return recording


ingestion_service = IngestionService()
