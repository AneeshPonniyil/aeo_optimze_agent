from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check():
    """
    Returns service health status and active configuration options.
    """
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "environment": "development" if settings.DEBUG else "production",
        "llm_provider": settings.LLM_PROVIDER,
    }
