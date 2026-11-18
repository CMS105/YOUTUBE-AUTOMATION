import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import torch

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Centralized configuration for GTA 6 AI Clip Factory.
    Adapted from visionmate-ai config.py with video pipeline extensions.
    All secrets loaded from environment variables / .env file.
    """

    # --- Application ---
    APP_NAME: str = "GTA 6 AI Clip Factory"
    APP_ENV: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gta6_clip_factory"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Task Queue & Cache ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # --- Hardware & Acceleration ---
    DEVICE: str = "auto"
    CUDA_DEVICE_INDEX: int = 0
    MAX_GPU_MEMORY_MB: int = 5120

    # --- Local File Storage Paths ---
    DATA_DIR: str = str(BASE_DIR / "data")
    RECORDINGS_DIR: str = str(BASE_DIR / "data" / "recordings")
    CLIPS_DIR: str = str(BASE_DIR / "data" / "clips")
    THUMBNAILS_DIR: str = str(BASE_DIR / "data" / "thumbnails")
    TEMP_DIR: str = str(BASE_DIR / "data" / "temp")
    MAX_RECORDING_RETENTION_DAYS: int = 7
    MAX_STORAGE_QUOTA_GB: int = 100

    # --- FFmpeg ---
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # --- Speech-to-Text (Faster-Whisper) ---
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "auto"
    WHISPER_COMPUTE_TYPE: str = "float16"

    # --- YouTube Data API v3 ---
    YOUTUBE_API_KEY: Optional[str] = None
    YOUTUBE_POLL_INTERVAL_SECONDS: int = 120

    # --- YouTube OAuth 2.0 ---
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/youtube/callback"

    # --- Google Gemini API ---
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # --- OpenAI API ---
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # --- VLM Provider Selection ---
    VLM_PROVIDER: str = "auto"  # "gemini", "openai", "local", "auto"

    # --- Clip Generation ---
    DEFAULT_CLIP_PRESET: str = "Viral Gaming"
    MIN_CLIP_DURATION_SECONDS: int = 15
    MAX_CLIP_DURATION_SECONDS: int = 60
    VERTICAL_RENDER_WIDTH: int = 1080
    VERTICAL_RENDER_HEIGHT: int = 1920
    VIDEO_BITRATE: str = "6000k"
    AUDIO_BITRATE: str = "192k"
    TARGET_FPS: int = 30

    # --- Safety Guard ---
    ENABLE_AUTO_PUBLISH: bool = False

    # --- OBS Studio WebSocket Integration ---
    OBS_HOST: str = "127.0.0.1"
    OBS_PORT: int = 4455
    OBS_PASSWORD: Optional[str] = None
    OBS_ENABLED: bool = True
    OBS_RECORDING_DIRECTORY: Optional[str] = None

    # --- Global Livestream Discovery ---
    YOUTUBE_DISCOVERY_KEYWORDS: str = "GTA 6,GTA VI,Grand Theft Auto 6,GTA 6 gameplay,GTA 6 online,GTA 6 live"
    YOUTUBE_DISCOVERY_INTERVAL_SECONDS: int = 180
    AUTO_DISCOVERY_ENABLED: bool = True

    # --- Automated Recording & Pipeline ---
    AUTO_RECORD_AUTHORIZED: bool = True
    MAX_RECORDING_DURATION_MINUTES: int = 30
    MIN_DISK_FREE_SPACE_GB: float = 5.0
    AUTO_PROCESS_AFTER_RECORDING: bool = True

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Computed Properties ---

    @property
    def resolved_device(self) -> str:
        """Determines whether to use CUDA or CPU based on config and hardware."""
        if self.DEVICE.lower() == "cpu":
            return "cpu"
        if torch.cuda.is_available():
            idx = self.CUDA_DEVICE_INDEX
            return f"cuda:{idx}" if torch.cuda.device_count() > idx else "cuda"
        return "cpu"

    @property
    def has_cuda(self) -> bool:
        return torch.cuda.is_available() and self.resolved_device.startswith("cuda")

    @property
    def gpu_info(self) -> dict:
        if not torch.cuda.is_available():
            return {"cuda_available": False, "device": "cpu"}
        try:
            idx = self.CUDA_DEVICE_INDEX if torch.cuda.device_count() > self.CUDA_DEVICE_INDEX else 0
            name = torch.cuda.get_device_name(idx)
            total = torch.cuda.get_device_properties(idx).total_memory / (1024 ** 2)
            reserved = torch.cuda.memory_reserved(idx) / (1024 ** 2)
            allocated = torch.cuda.memory_allocated(idx) / (1024 ** 2)
            return {
                "cuda_available": True,
                "device_name": name,
                "device_index": idx,
                "total_vram_mb": round(total, 1),
                "reserved_vram_mb": round(reserved, 1),
                "allocated_vram_mb": round(allocated, 1),
                "free_vram_mb": round(total - reserved, 1),
            }
        except Exception:
            return {"cuda_available": True, "device": self.resolved_device}

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def has_youtube_api(self) -> bool:
        key = self.YOUTUBE_API_KEY
        return bool(key and len(key.strip()) > 10 and not key.startswith("your-"))

    @property
    def has_youtube_oauth(self) -> bool:
        return bool(self.YOUTUBE_CLIENT_ID and self.YOUTUBE_CLIENT_SECRET)

    @property
    def has_gemini(self) -> bool:
        key = self.GEMINI_API_KEY
        return bool(key and len(key.strip()) > 10 and not key.startswith("your-"))

    @property
    def has_openai(self) -> bool:
        key = self.OPENAI_API_KEY
        return bool(key and len(key.strip()) > 10 and not key.startswith("sk-your-"))

    @property
    def active_vlm_provider(self) -> str:
        """Determine active VLM provider based on config and available keys."""
        if self.VLM_PROVIDER == "gemini" and self.has_gemini:
            return "gemini"
        if self.VLM_PROVIDER == "openai" and self.has_openai:
            return "openai"
        if self.VLM_PROVIDER == "local":
            return "local"
        # Auto mode: prefer Gemini, then OpenAI, then local
        if self.has_gemini:
            return "gemini"
        if self.has_openai:
            return "openai"
        return "local"

    @property
    def discovery_keywords_list(self) -> List[str]:
        return [k.strip() for k in self.YOUTUBE_DISCOVERY_KEYWORDS.split(",") if k.strip()]

    def mask_key(self, key: Optional[str]) -> str:
        """Masks API key for safe display: shows first 4 and last 4 chars."""
        if not key or len(key) < 12:
            return "not_configured"
        return f"{key[:4]}...{key[-4:]}"

    def get_integration_status(self) -> dict:
        """Returns safe-to-display integration status (no raw secrets)."""
        return {
            "youtube_api": {
                "configured": self.has_youtube_api,
                "key_hint": self.mask_key(self.YOUTUBE_API_KEY),
                "poll_interval_s": self.YOUTUBE_POLL_INTERVAL_SECONDS,
                "discovery_interval_s": self.YOUTUBE_DISCOVERY_INTERVAL_SECONDS,
                "auto_discovery_enabled": self.AUTO_DISCOVERY_ENABLED,
            },
            "obs_websocket": {
                "enabled": self.OBS_ENABLED,
                "host": self.OBS_HOST,
                "port": self.OBS_PORT,
                "password_configured": bool(self.OBS_PASSWORD),
                "auto_record_authorized": self.AUTO_RECORD_AUTHORIZED,
                "max_recording_minutes": self.MAX_RECORDING_DURATION_MINUTES,
                "min_disk_free_gb": self.MIN_DISK_FREE_SPACE_GB,
            },
            "youtube_oauth": {
                "configured": self.has_youtube_oauth,
                "client_id_hint": self.mask_key(self.YOUTUBE_CLIENT_ID),
            },
            "gemini": {
                "configured": self.has_gemini,
                "model": self.GEMINI_MODEL,
                "key_hint": self.mask_key(self.GEMINI_API_KEY),
            },
            "openai": {
                "configured": self.has_openai,
                "model": self.OPENAI_MODEL,
                "key_hint": self.mask_key(self.OPENAI_API_KEY),
            },
            "active_vlm": self.active_vlm_provider,
            "hardware": self.gpu_info,
            "auto_publish": self.ENABLE_AUTO_PUBLISH,
        }

    def ensure_directories(self) -> None:
        """Create all required data directories on startup."""
        for d in [self.DATA_DIR, self.RECORDINGS_DIR, self.CLIPS_DIR,
                  self.THUMBNAILS_DIR, self.TEMP_DIR]:
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()

