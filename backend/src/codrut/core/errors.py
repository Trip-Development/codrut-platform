import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from codrut.core.config import Settings, get_settings
from codrut.core.request_id import REQUEST_ID_HEADER, request_id_from_request

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    loc: list[str | int] | None = None
    message: str
    type: str | None = None


class ErrorPayload(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[ErrorDetail] | dict[str, Any] | list[Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload = Field(..., description="Standard API error envelope.")


ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Bad Request"},
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Unauthorized"},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Not Found"},
    422: {"model": ErrorResponse, "description": "Validation Error"},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Internal Server Error",
    },
}


class DomainError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "domain_error",
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    request_id = request_id_from_request(request)
    response_headers = dict(headers or {})
    if request_id:
        error["request_id"] = request_id
        response_headers.setdefault(REQUEST_ID_HEADER, request_id)
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
        headers=response_headers,
    )


def validation_error_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {
            "loc": list(error.get("loc", [])),
            "message": error.get("msg", "Invalid input."),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]


def http_error_payload(exc: HTTPException) -> tuple[str, str, Any | None]:
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", f"http_{exc.status_code}"))
        message = str(exc.detail.get("message", "HTTP error."))
        return code, message, exc.detail.get("details")
    if isinstance(exc.detail, str):
        return f"http_{exc.status_code}", exc.detail, None
    return f"http_{exc.status_code}", "HTTP error.", None


def install_exception_handlers(app: FastAPI, *, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=422,
            code="validation_error",
            message="Request validation failed.",
            details=validation_error_details(exc),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code, message, details = http_error_payload(exc)
        return error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return error_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        request_id = request_id_from_request(request)
        error_category = type(exc).__name__
        log_context = {
            "request_id": request_id,
            "error_category": error_category,
        }
        if active_settings.is_production:
            logger.error(
                "Database error request_id=%s category=%s",
                request_id or "unknown",
                error_category,
                extra=log_context,
            )
        else:
            logger.exception(
                "Database error while handling %s %s request_id=%s category=%s",
                request.method,
                request.url.path,
                request_id or "unknown",
                error_category,
                exc_info=exc,
                extra=log_context,
            )
        return error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="database_error",
            message="The request could not be completed because of a database error.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_from_request(request)
        error_category = type(exc).__name__
        log_context = {
            "request_id": request_id,
            "error_category": error_category,
        }
        if active_settings.is_production:
            logger.error(
                "Unexpected error request_id=%s category=%s",
                request_id or "unknown",
                error_category,
                extra=log_context,
            )
        else:
            logger.exception(
                "Unexpected error while handling %s %s request_id=%s category=%s",
                request.method,
                request.url.path,
                request_id or "unknown",
                error_category,
                exc_info=exc,
                extra=log_context,
            )
        return error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="unexpected_error",
            message="The request could not be completed because of an unexpected error.",
        )
