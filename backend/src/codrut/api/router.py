from fastapi import APIRouter

from codrut.modules.health.router import router as health_router
from codrut.modules.identity.router import router as identity_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(identity_router, prefix="/auth", tags=["auth"])
