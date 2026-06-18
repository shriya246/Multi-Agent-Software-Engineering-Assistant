from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

import httpx

from app.core.config import Settings
from app.schemas.common import HealthCheck, HealthResponse
from app.services.database import DatabaseManager
from app.services.redis import RedisManager

DependencyState = Literal["ready", "degraded"]


@dataclass(slots=True)
class DependencyCheck:
    status: DependencyState
    detail: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def _check(status: DependencyState, detail: str | None = None, **metadata: str) -> HealthCheck:
    return HealthCheck(
        status=status,
        detail=detail,
        metadata={key: value for key, value in metadata.items()},
    )


async def _http_dependency_check(
    url: str,
    *,
    path: str,
    timeout_seconds: float,
) -> DependencyCheck:
    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)
    try:
        async with httpx.AsyncClient(
            base_url=url,
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            response = await client.get(path)
            if response.status_code >= 400:
                return DependencyCheck(
                    status="degraded",
                    detail=f"http_{response.status_code}",
                )
    except Exception as exc:  # pragma: no cover - network failure path
        return DependencyCheck(status="degraded", detail=exc.__class__.__name__)
    return DependencyCheck(status="ready", detail="reachable")


async def _ollama_dependency_check(settings: Settings) -> DependencyCheck:
    try:
        timeout = httpx.Timeout(
            settings.ollama_health_timeout_seconds,
            connect=settings.ollama_health_timeout_seconds,
        )
        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=timeout) as client:
            response = await client.get("/api/tags")
            if response.status_code >= 400:
                return DependencyCheck(
                    status="degraded",
                    detail=f"http_{response.status_code}",
                    metadata={"service": "down"},
                )
            payload = cast(dict[str, object], response.json())
            models = cast(list[dict[str, object]], payload.get("models", []))
            model_available = any(
                model.get("name") == settings.ollama_chat_model
                for model in models
                if isinstance(model, dict)
            )
    except Exception as exc:  # pragma: no cover - malformed response / network failure
        return DependencyCheck(
            status="degraded",
            detail=exc.__class__.__name__,
            metadata={"service": "down"},
        )

    return DependencyCheck(
        status="ready",
        detail="reachable",
        metadata={
            "service": "ready",
            "chat_model": "available" if model_available else "missing",
            "embedding_model": settings.ollama_embedding_model,
        },
    )


async def build_readiness_payload(
    settings: Settings,
    database: DatabaseManager,
    redis: RedisManager,
) -> HealthResponse:
    postgres_status, postgres_detail = await database.healthcheck()
    redis_status, redis_detail = await redis.healthcheck()
    qdrant = await _http_dependency_check(
        settings.qdrant_url,
        path="/healthz",
        timeout_seconds=settings.qdrant_health_timeout_seconds,
    )
    ollama = await _ollama_dependency_check(settings)

    checks = {
        "postgres": _check(postgres_status, postgres_detail),
        "redis": _check(redis_status, redis_detail),
        "qdrant": _check(qdrant.status, qdrant.detail, **qdrant.metadata),
        "ollama": _check(ollama.status, ollama.detail, **ollama.metadata),
    }
    mandatory_ready = all(
        checks[name].status == "ready" for name in ("postgres", "redis", "qdrant")
    )
    status = "ready" if mandatory_ready and checks["ollama"].status == "ready" else "degraded"
    return HealthResponse(status=status, checks=checks)
