from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codrut.api.router import api_router
from codrut.core.config import get_settings
from codrut.core.errors import install_exception_handlers
from codrut.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_exception_handlers(app)
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
