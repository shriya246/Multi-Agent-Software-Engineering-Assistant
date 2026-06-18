from __future__ import annotations

from app.services.health import DependencyCheck


def test_live_health_endpoint(client) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}


def test_ready_health_endpoint(client, monkeypatch) -> None:
    container = client.app.state.container

    class FakeDatabase:
        async def healthcheck(self) -> tuple[str, str]:
            return "ready", "connected"

        async def dispose(self) -> None:
            return None

    class FakeRedis:
        async def healthcheck(self) -> tuple[str, str]:
            return "ready", "connected"

        async def close(self) -> None:
            return None

    async def qdrant_ready(*args, **kwargs) -> DependencyCheck:
        return DependencyCheck(status="ready", detail="reachable")

    async def ollama_ready(*args, **kwargs) -> DependencyCheck:
        return DependencyCheck(
            status="ready",
            detail="reachable",
            metadata={"service": "ready", "chat_model": "available"},
        )

    container.database = FakeDatabase()
    container.redis = FakeRedis()

    from app.services import health as health_service

    monkeypatch.setattr(health_service, "_http_dependency_check", qdrant_ready)
    monkeypatch.setattr(health_service, "_ollama_dependency_check", ollama_ready)

    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["postgres"]["status"] == "ready"
    assert payload["checks"]["ollama"]["metadata"]["chat_model"] == "available"


def test_version_endpoint(client) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


def test_ready_health_endpoint_marks_unavailable_dependency(client, monkeypatch) -> None:
    container = client.app.state.container

    class FakeDatabase:
        async def healthcheck(self) -> tuple[str, str]:
            return "ready", "connected"

        async def dispose(self) -> None:
            return None

    class FakeRedis:
        async def healthcheck(self) -> tuple[str, str]:
            return "ready", "connected"

        async def close(self) -> None:
            return None

    async def qdrant_down(*args, **kwargs) -> DependencyCheck:
        return DependencyCheck(status="degraded", detail="timeout")

    async def ollama_ready(*args, **kwargs) -> DependencyCheck:
        return DependencyCheck(
            status="ready",
            detail="reachable",
            metadata={"service": "ready", "chat_model": "missing"},
        )

    container.database = FakeDatabase()
    container.redis = FakeRedis()

    from app.services import health as health_service

    monkeypatch.setattr(health_service, "_http_dependency_check", qdrant_down)
    monkeypatch.setattr(health_service, "_ollama_dependency_check", ollama_ready)

    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["qdrant"]["status"] == "degraded"
