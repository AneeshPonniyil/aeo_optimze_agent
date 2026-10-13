from fastapi import APIRouter
from app.api.v1.endpoints import health, validate, audit, history

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(validate.router, tags=["Security"])
api_router.include_router(audit.router, tags=["Audit Engine"])
api_router.include_router(history.router, tags=["Audit History"])
