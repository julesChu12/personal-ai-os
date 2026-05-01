from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "qdrant_url": settings.qdrant_url,
        "model_configured": bool(settings.minimax_api_key or settings.openai_api_key),
    }
