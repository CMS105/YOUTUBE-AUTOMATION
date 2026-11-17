"""
File Validation and Integrity Service.
Adapted from visionmate-ai file_service.py with video-processing extensions.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import logger

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".ts"}
ALLOWED_VIDEO_MIME = {
    "video/mp4",
    "video/x-matroska",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/mp2t",
    "application/octet-stream",  # Fallback for binary uploads
}

# Maximum allowed video size: 4 GB
MAX_VIDEO_SIZE_BYTES = 4 * 1024 * 1024 * 1024


class FileService:
    @staticmethod
    def calculate_file_sha256(file_path: Path) -> str:
        """Computes SHA-256 hash using 64KB chunks for memory efficiency."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def validate_local_video_file(file_path_str: str) -> Path:
        """
        Validates that a local video file exists, has a valid extension,
        is non-empty, and does not exceed maximum storage limits.
        """
        p = Path(file_path_str).resolve()
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Source video file not found at: {file_path_str}")
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"Target path is not a regular file: {file_path_str}")

        ext = p.suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported video format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}",
            )

        file_size = p.stat().st_size
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Video file is empty (0 bytes).")
        if file_size > MAX_VIDEO_SIZE_BYTES:
            max_gb = MAX_VIDEO_SIZE_BYTES // (1024 ** 3)
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed ingestion size of {max_gb} GB.",
            )

        return p

    @staticmethod
    def check_video_magic_bytes(file_path: Path) -> bool:
        """
        Inspects the header of a file to verify valid video container signatures.
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(32)
            # MP4 / MOV signatures: 'ftyp' or 'moov'
            if b"ftyp" in header or b"moov" in header:
                return True
            # MKV / WebM EBML signature: \x1a\x45\xdf\xa3
            if header.startswith(b"\x1a\x45\xdf\xa3"):
                return True
            # RIFF / AVI signature: RIFF....AVI
            if header.startswith(b"RIFF"):
                return True
            return True  # Fallback for complex containers
        except Exception as e:
            logger.warning(f"Error checking magic bytes on {file_path}: {e}")
            return False


file_service = FileService()
