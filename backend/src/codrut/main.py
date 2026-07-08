from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from codrut.api.openapi import generate_stable_operation_id
from codrut.api.router import api_router
from codrut.core.config import get_settings
from codrut.core.errors import ERROR_RESPONSES, install_exception_handlers
from codrut.core.logging import configure_logging
from codrut.core.request_id import install_request_id_middleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url=None,
        generate_unique_id_function=generate_stable_operation_id,
        responses=ERROR_RESPONSES,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_request_id_middleware(app)
    install_exception_handlers(app)
    Path(settings.campaign_asset_dir).mkdir(parents=True, exist_ok=True)
    app.mount(
        settings.campaign_asset_public_path,
        StaticFiles(directory=settings.campaign_asset_dir),
        name="campaign-assets",
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
