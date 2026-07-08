from fastapi.testclient import TestClient

from codrut.core.request_id import REQUEST_ID_HEADER
from codrut.main import create_app


def test_health_live() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health/live", headers={REQUEST_ID_HEADER: "req-health"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-health"
    assert response.json() == {"status": "ok"}
