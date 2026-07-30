from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from codrut.core.config import Settings
from codrut.core.maintenance import (
    MAINTENANCE_BYPASS_HEADER,
    install_maintenance_middleware,
)

MAINTENANCE_TOKEN = "maintenance-test-token-with-at-least-32-characters"  # noqa: S105


def maintenance_app() -> FastAPI:
    app = FastAPI()
    install_maintenance_middleware(
        app,
        Settings(
            maintenance_mode=True,
            maintenance_bypass_token=SecretStr(MAINTENANCE_TOKEN),
        ),
    )

    @app.get("/api/read")
    async def read() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/write")
    async def write() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/communications/webhooks/brevo")
    async def webhook() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/communications/campaigns/unsubscribe/token")
    async def unsubscribe() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_maintenance_mode_blocks_normal_mutations_but_keeps_reads_available() -> None:
    client = TestClient(maintenance_app())

    assert client.get("/api/read").status_code == 200
    response = client.post("/api/write")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert response.json()["error"]["code"] == "maintenance_mode"


def test_maintenance_bypass_is_exact_and_never_accepted_by_prefix() -> None:
    client = TestClient(maintenance_app())

    rejected = client.post(
        "/api/write",
        headers={MAINTENANCE_BYPASS_HEADER: f"{MAINTENANCE_TOKEN}-wrong"},
    )
    accepted = client.post(
        "/api/write",
        headers={MAINTENANCE_BYPASS_HEADER: MAINTENANCE_TOKEN},
    )

    assert rejected.status_code == 503
    assert accepted.status_code == 200


def test_delivery_webhooks_and_unsubscribe_remain_available_during_maintenance() -> None:
    client = TestClient(maintenance_app())

    assert client.post("/api/communications/webhooks/brevo").status_code == 200
    assert (
        client.post("/api/communications/campaigns/unsubscribe/token").status_code
        == 200
    )


def test_maintenance_mode_refuses_a_missing_or_short_bypass_secret() -> None:
    try:
        Settings(maintenance_mode=True)
    except ValidationError as exc:
        assert "at least 32 characters" in str(exc)
    else:
        raise AssertionError("Maintenance mode accepted a missing bypass token.")
