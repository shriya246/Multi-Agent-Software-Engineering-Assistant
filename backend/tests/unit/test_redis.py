from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.core.config import Settings
from app.services.redis import RedisManager


@dataclass
class FakeRedisClient:
    data: dict[str, str] = field(default_factory=dict)

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.data:
                deleted += 1
                self.data.pop(key, None)
        return deleted

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_redis_health_check() -> None:
    manager = RedisManager(Settings(redis_url="redis://localhost:6379/0"))
    manager.client = FakeRedisClient()  # type: ignore[assignment]

    status, detail = await manager.healthcheck()
    assert status == "ready"
    assert detail == "connected"


def test_redis_namespace_uses_environment_and_app_name() -> None:
    manager = RedisManager(Settings(redis_url="redis://localhost:6379/0"))
    assert manager.namespace("jobs", "123").startswith("development:CodePilot".lower())
