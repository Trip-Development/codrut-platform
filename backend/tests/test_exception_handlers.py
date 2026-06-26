from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import LogCaptureFixture
from sqlalchemy.exc import SQLAlchemyError

from codrut.core.errors import install_exception_handlers


def test_database_errors_are_logged_and_return_structured_response(
    caplog: LogCaptureFixture,
) -> None:
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise SQLAlchemyError("connection failed")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert "Database error while handling GET /boom" in caplog.text
    assert response.json() == {
        "error": {
            "code": "database_error",
            "message": "The request could not be completed because of a database error.",
        }
    }
