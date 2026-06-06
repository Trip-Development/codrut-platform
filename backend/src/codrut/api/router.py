from fastapi import APIRouter

from codrut.modules.assignments.router import router as assignments_router
from codrut.modules.companies.router import router as companies_router
from codrut.modules.communications.router import router as communications_router
from codrut.modules.forms.router import router as forms_router
from codrut.modules.health.router import router as health_router
from codrut.modules.identity.router import router as identity_router
from codrut.modules.scoring.router import router as scoring_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(identity_router, prefix="/auth", tags=["auth"])
api_router.include_router(companies_router, prefix="/companies", tags=["companies"])
api_router.include_router(communications_router, prefix="/communications", tags=["communications"])
api_router.include_router(assignments_router, tags=["assignments"])
api_router.include_router(forms_router, prefix="/forms", tags=["forms"])
api_router.include_router(scoring_router, prefix="/scoring", tags=["scoring"])
