"""
GTA 6 AI Clip Factory — FastAPI Application Entry Point.

Adapted from API-TASKFLOW (demo123) main.py and BMSC-HACKATHON backend.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import logger
from app.database import engine, Base, get_db_type, SessionLocal
from app.routers import (
    health, streamers, permissions, clips, ingestion,
    candidates, youtube, authorizations, obs, recording_sessions
)
from app.services.recording_manager_service import recording_manager_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Database: {get_db_type()}")
    logger.info(f"Hardware: {settings.gpu_info}")
    logger.info(f"VLM Provider: {settings.active_vlm_provider}")
    logger.info(f"OBS Studio Integration: {'ENABLED' if settings.OBS_ENABLED else 'DISABLED'}")
    logger.info(f"Auto-Publish: {'DISABLED (safe)' if not settings.ENABLE_AUTO_PUBLISH else 'WARNING: ENABLED'}")

    # Ensure data directories exist
    settings.ensure_directories()

    # Create database tables (dev mode — Alembic manages production)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified.")

    # Recover any hanging recording sessions after restart
    db = SessionLocal()
    try:
        recovered = recording_manager_service.recover_hanging_sessions(db)
        if recovered > 0:
            logger.info(f"Recovered {recovered} hanging recording sessions on startup.")
    except Exception as e:
        logger.warning(f"Error during startup session recovery: {e}")
    finally:
        db.close()

    yield

    logger.info(f"{settings.APP_NAME} shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    description="Automated GTA 6 livestream discovery, authorized recording, and AI highlight clipping engine",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(streamers.router, prefix=settings.API_PREFIX)
app.include_router(permissions.router, prefix=settings.API_PREFIX)
app.include_router(clips.router, prefix=settings.API_PREFIX)
app.include_router(candidates.router, prefix=settings.API_PREFIX)
app.include_router(ingestion.router, prefix=settings.API_PREFIX)
app.include_router(youtube.router, prefix=settings.API_PREFIX)
app.include_router(authorizations.router, prefix=settings.API_PREFIX)
app.include_router(obs.router, prefix=settings.API_PREFIX)
app.include_router(recording_sessions.router, prefix=settings.API_PREFIX)

# Serve clip files and thumbnails as static assets
clips_dir = Path(settings.CLIPS_DIR)
thumbs_dir = Path(settings.THUMBNAILS_DIR)
clips_dir.mkdir(parents=True, exist_ok=True)
thumbs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/clips", StaticFiles(directory=str(clips_dir)), name="clips_static")
app.mount("/static/thumbnails", StaticFiles(directory=str(thumbs_dir)), name="thumbnails_static")


@app.get("/", include_in_schema=False)
def root():
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "api_docs": f"{settings.API_PREFIX}/docs",
        "dashboard": "http://localhost:3000",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

