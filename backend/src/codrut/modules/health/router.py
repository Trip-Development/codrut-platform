from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from codrut.modules.health import service

router = APIRouter()


class ReadinessResponse(BaseModel):
    status: Literal["ok"]
    checks: dict[str, Literal["ok"]]


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service not ready"}},
)
async def ready() -> ReadinessResponse:
    checks = await service.collect_readiness_checks()
    failures = [
        {"component": check.component, "code": check.code}
        for check in checks
        if not check.ok
    ]
    if failures:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "service_not_ready",
                "message": "One or more required services are not ready.",
                "details": failures,
            },
        )
    return ReadinessResponse(
        status="ok",
        checks={check.component: "ok" for check in checks},
    )
