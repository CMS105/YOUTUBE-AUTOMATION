"""Health & system status router."""

from fastapi import APIRouter
from app.core.config import settings
from app.database import get_db_type

router = APIRouter(tags=["System"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "database": get_db_type(),
        "hardware": settings.gpu_info,
        "integrations": settings.get_integration_status(),
    }


@router.get("/integrations/status")
def integration_status():
    """Returns API integration status with masked secrets."""
    return settings.get_integration_status()

