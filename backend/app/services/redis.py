from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from redis.asyncio import from_url as redis_from_url

from app.core.config import Settings


def dumps_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def loads_json(payload: str) -> Any:
    return json.loads(payload)


def build_namespace(settings: Settings, *parts: str) -> str:
    app_slug = settings.app_name.lower().replace(" ", "-")
    safe_parts = [part.strip(":") for part in parts if part]
    return ":".join([settings.environment, app_slug, *safe_parts])


@dataclass(slots=True)
class RedisManager:
    settings: Settings
    client: Any = field(init=False)

    def __post_init__(self) -> None:
        self.client = redis_from_url(  # type: ignore[no-untyped-call]
            self.settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=self.settings.redis_socket_connect_timeout_seconds,
            socket_timeout=self.settings.redis_socket_timeout_seconds,
            health_check_interval=self.settings.redis_health_check_interval_seconds,
            retry_on_timeout=True,
        )

    def namespace(self, *parts: str) -> str:
        return build_namespace(self.settings, *parts)

    async def ping(self) -> None:
        await asyncio.wait_for(
            self.client.ping(),
            timeout=self.settings.redis_health_timeout_seconds,
        )

    async def healthcheck(self) -> tuple[Literal["ready", "degraded"], str]:
        try:
            await self.ping()
        except Exception as exc:  # pragma: no cover - network failure path
            return "degraded", exc.__class__.__name__
        return "ready", "connected"

    async def get_json(self, key: str) -> Any | None:
        payload = await self.client.get(key)
        if payload is None:
            return None
        return loads_json(payload)

    async def set_json(
        self,
        key: str,
        value: Any,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        payload = dumps_json(value)
        result = await self.client.set(key, payload, ex=ex, nx=nx)
        return bool(result)

    async def delete(self, *keys: str) -> int:
        return int(await self.client.delete(*keys))

    async def close(self) -> None:
        await self.client.aclose()
