from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from codrut.core.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    csrf_token_for_session,
    install_csrf_middleware,
)
from codrut.core.request_id import REQUEST_ID_HEADER, install_request_id_middleware
from codrut.main import create_app
from codrut.modules.identity.session_cookie import SESSION_COOKIE_NAME, delete_session_cookie

SESSION_TOKEN = "session-token"  # noqa: S105


def create_csrf_test_app() -> FastAPI:
    app = FastAPI()
    install_csrf_middleware(app, session_cookie_name=SESSION_COOKIE_NAME)
    install_request_id_middleware(app)

    @app.get("/api/protected")
    async def protected_read() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/protected")
    async def protected_write() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/auth/login")
    async def public_login() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/logout")
    async def protected_logout(response: Response) -> Response:
        delete_session_cookie(response)
        response.status_code = 204
        return response

    return app


def client_with_session() -> TestClient:
    client = TestClient(create_csrf_test_app())
    client.cookies.set(SESSION_COOKIE_NAME, SESSION_TOKEN)
    return client


def test_safe_requests_refresh_csrf_cookie_for_session() -> None:
    client = client_with_session()

    response = client.get("/api/protected")

    assert response.status_code == 200
    assert response.cookies[CSRF_COOKIE_NAME] == csrf_token_for_session(SESSION_TOKEN)


def test_unsafe_session_request_requires_csrf_token() -> None:
    client = client_with_session()

    response = client.post("/api/protected", headers={REQUEST_ID_HEADER: "req-csrf"})

    assert response.status_code == 403
    assert response.headers[REQUEST_ID_HEADER] == "req-csrf"
    assert response.json() == {
        "error": {
            "code": "csrf_failed",
            "message": "CSRF token is required.",
            "request_id": "req-csrf",
        }
    }
    assert response.cookies[CSRF_COOKIE_NAME] == csrf_token_for_session(SESSION_TOKEN)


def test_unsafe_session_request_accepts_matching_valid_csrf_token() -> None:
    client = client_with_session()
    token = csrf_token_for_session(SESSION_TOKEN)
    client.cookies.set(CSRF_COOKIE_NAME, token)

    response = client.post("/api/protected", headers={CSRF_HEADER_NAME: token})

    assert response.status_code == 200


def test_csrf_middleware_does_not_overwrite_route_cookie_deletion() -> None:
    client = client_with_session()
    token = csrf_token_for_session(SESSION_TOKEN)
    client.cookies.set(CSRF_COOKIE_NAME, token)

    response = client.post("/api/logout", headers={CSRF_HEADER_NAME: token})

    assert response.status_code == 204
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(header.startswith(f"{SESSION_COOKIE_NAME}=") for header in set_cookie_headers)
    assert any(header.startswith(f"{CSRF_COOKIE_NAME}=") for header in set_cookie_headers)
    assert not any(
        header.startswith(f"{CSRF_COOKIE_NAME}={token}") for header in set_cookie_headers
    )


def test_unsafe_session_request_rejects_invalid_csrf_token() -> None:
    client = client_with_session()
    client.cookies.set(CSRF_COOKIE_NAME, "bad-token")

    response = client.post("/api/protected", headers={CSRF_HEADER_NAME: "bad-token"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert response.json()["error"]["message"] == "CSRF token is invalid."


def test_public_auth_mutations_are_csrf_exempt() -> None:
    client = client_with_session()

    response = client.post("/api/auth/login")

    assert response.status_code == 200


def test_unsafe_request_without_session_cookie_is_not_blocked_by_csrf() -> None:
    client = TestClient(create_csrf_test_app())

    response = client.post("/api/protected")

    assert response.status_code == 200


def test_csrf_endpoint_returns_token_for_session_cookie() -> None:
    client = TestClient(create_app())
    client.cookies.set(SESSION_COOKIE_NAME, SESSION_TOKEN)

    response = client.get("/api/auth/csrf")

    assert response.status_code == 200
    assert response.json() == {"csrf_token": csrf_token_for_session(SESSION_TOKEN)}
    assert response.cookies[CSRF_COOKIE_NAME] == csrf_token_for_session(SESSION_TOKEN)


def test_csrf_endpoint_requires_session_cookie() -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.get("/api/auth/csrf")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Not authenticated"
