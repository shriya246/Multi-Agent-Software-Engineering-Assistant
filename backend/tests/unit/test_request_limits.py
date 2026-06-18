from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.main import create_app


def test_request_size_limit_rejects_large_body(monkeypatch) -> None:
    monkeypatch.setenv("CODEPILOT_MAX_REQUEST_SIZE_BYTES", "8")
    reset_settings_cache()
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/health/live",
            content=b"x" * 64,
            headers={"content-length": "64"},
        )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "request_too_large"
