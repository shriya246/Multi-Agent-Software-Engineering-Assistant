from __future__ import annotations

import pytest

from app.api.v1.auth import _validate_csrf
from app.core.config import Settings
from app.core.container import AppContainer
from app.core.exceptions import Unauthorized


class CookieRequest:
    cookies = {"codepilot_csrf": "csrf-value"}


def test_csrf_double_submit_validation() -> None:
    container = AppContainer(settings=Settings(), database=None, redis=None)  # type: ignore[arg-type]
    request = CookieRequest()
    _validate_csrf(request, container, "csrf-value")  # type: ignore[arg-type]
    with pytest.raises(Unauthorized):
        _validate_csrf(request, container, "different")  # type: ignore[arg-type]


def test_openapi_documents_auth_endpoints(client) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path in ("register", "login", "refresh", "logout", "logout-all", "me"):
        assert f"/api/v1/auth/{path}" in paths


def test_openapi_documents_repository_ingestion_endpoints(client) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path in (
        "/api/v1/repositories",
        "/api/v1/repositories/{repository_id}",
        "/api/v1/repositories/{repository_id}/sync",
        "/api/v1/repositories/{repository_id}/files",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/events",
    ):
        assert path in paths
