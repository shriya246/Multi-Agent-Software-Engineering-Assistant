from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.core.config import Settings
from app.core.exceptions import Conflict
from app.services.idempotency import IdempotencyService


@dataclass
class FakeRedisManager:
    storage: dict[str, dict[str, object]] = field(default_factory=dict)

    def namespace(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(
        self, key: str, value: dict[str, object], *, ex: int | None = None, nx: bool = False
    ) -> bool:
        if nx and key in self.storage:
            return False
        self.storage[key] = value
        return True

    async def get_json(self, key: str) -> dict[str, object] | None:
        return self.storage.get(key)


@pytest.mark.asyncio
async def test_idempotency_reserve_and_replay() -> None:
    service = IdempotencyService(FakeRedisManager(), Settings())
    first = await service.reserve("abc", payload={"kind": "bug-fix"})
    second = await service.reserve("abc", payload={"kind": "bug-fix"})

    assert first.created is True
    assert second.created is False


@pytest.mark.asyncio
async def test_idempotency_rejects_different_payloads() -> None:
    service = IdempotencyService(FakeRedisManager(), Settings())
    await service.reserve("abc", payload={"kind": "bug-fix"})

    with pytest.raises(Conflict):
        await service.reserve("abc", payload={"kind": "test-gen"})
