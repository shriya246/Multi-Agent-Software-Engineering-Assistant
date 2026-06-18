from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.common import HealthCheck


@dataclass(slots=True)
class ReadinessPayload:
    status: str
    checks: dict[str, HealthCheck]


async def build_readiness_payload(settings: Settings) -> ReadinessPayload:
    checks = {
        "api": HealthCheck(status="ready"),
        "postgres": _dependency_check(settings.database_url),
        "redis": _dependency_check(settings.redis_url),
        "qdrant": _dependency_check(settings.qdrant_url),
        "ollama": HealthCheck(
            status="ready"
            if _configured(settings.ollama_base_url) == "configured"
            and _configured(settings.ollama_chat_model) == "configured"
            else "degraded",
            detail=(
                f"base_url={_configured(settings.ollama_base_url)}; "
                f"model={_configured(settings.ollama_chat_model)}"
            ),
        ),
    }
    status = "ready" if all(check.status == "ready" for check in checks.values()) else "degraded"
    return ReadinessPayload(status=status, checks=checks)


def _configured(value: str) -> str:
    if value and not value.startswith("change-me"):
        return "configured"
    return "unconfigured"


def _dependency_check(value: str) -> HealthCheck:
    configured = _configured(value)
    return HealthCheck(
        status="ready" if configured == "configured" else "degraded",
        detail=configured,
    )
