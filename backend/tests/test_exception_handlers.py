from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pytest import LogCaptureFixture
from sqlalchemy.exc import SQLAlchemyError

from codrut.core.errors import DomainError, install_exception_handlers
from codrut.core.request_id import REQUEST_ID_HEADER, install_request_id_middleware


class ExamplePayload(BaseModel):
    email: str
    password: str


def create_test_app() -> FastAPI:
    app = FastAPI()
    install_request_id_middleware(app)
    install_exception_handlers(app)
    return app


def test_request_id_is_added_to_successful_responses() -> None:
    app = create_test_app()

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/ok", headers={REQUEST_ID_HEADER: "req-test-1"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-test-1"


def test_domain_errors_include_request_id_and_details() -> None:
    app = create_test_app()

    @app.get("/domain")
    async def domain() -> None:
        raise DomainError(
            "Invalid workflow state.",
            code="invalid_state",
            details={"field": "status"},
        )

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/domain", headers={REQUEST_ID_HEADER: "req-domain"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_state",
            "message": "Invalid workflow state.",
            "request_id": "req-domain",
            "details": {"field": "status"},
        }
    }


def test_http_exceptions_use_standard_error_envelope() -> None:
    app = create_test_app()

    @app.get("/auth")
    async def auth() -> None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/auth", headers={REQUEST_ID_HEADER: "req-auth"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "http_401",
            "message": "Not authenticated",
            "request_id": "req-auth",
        }
    }


def test_validation_errors_include_sanitized_details() -> None:
    app = create_test_app()

    @app.post("/validate")
    async def validate(_payload: ExamplePayload) -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/validate",
        headers={REQUEST_ID_HEADER: "req-validation"},
        json={"email": "trainer@example.com", "password": 123},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed."
    assert payload["error"]["request_id"] == "req-validation"
    assert payload["error"]["details"] == [
        {
            "loc": ["body", "password"],
            "message": "Input should be a valid string",
            "type": "string_type",
        }
    ]
    assert "123" not in str(payload)


def test_database_errors_are_logged_and_return_structured_response(
    caplog: LogCaptureFixture,
) -> None:
    app = create_test_app()

    @app.get("/boom")
    async def boom() -> None:
        raise SQLAlchemyError("connection failed")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom", headers={REQUEST_ID_HEADER: "req-db"})

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "req-db"
    assert "Database error while handling GET /boom" in caplog.text
    assert response.json() == {
        "error": {
            "code": "database_error",
            "message": "The request could not be completed because of a database error.",
            "request_id": "req-db",
        }
    }
