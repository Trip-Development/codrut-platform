from fastapi import APIRouter

from codrut.modules.assignments.router import router as assignments_router
from codrut.modules.companies.router import router as companies_router
from codrut.modules.health.router import router as health_router
from codrut.modules.identity.router import router as identity_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(identity_router, prefix="/auth", tags=["auth"])
api_router.include_router(companies_router, prefix="/companies", tags=["companies"])
api_router.include_router(assignments_router, tags=["assignments"])
