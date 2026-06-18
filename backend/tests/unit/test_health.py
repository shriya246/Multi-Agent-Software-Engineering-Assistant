from __future__ import annotations


def test_live_health_endpoint(client) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}


def test_ready_health_endpoint(client) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert "ollama" in payload["checks"]


def test_version_endpoint(client) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"
