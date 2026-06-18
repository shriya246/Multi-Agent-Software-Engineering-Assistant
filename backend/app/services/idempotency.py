from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from app.core.config import Settings
from app.core.exceptions import Conflict
from app.services.redis import RedisManager, dumps_json


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    fingerprint: str
    status: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class IdempotencyResult:
    created: bool
    record: IdempotencyRecord


class IdempotencyService:
    def __init__(self, redis_manager: RedisManager, settings: Settings) -> None:
        self.redis = redis_manager
        self.settings = settings

    def _key(self, idempotency_key: str) -> str:
        return self.redis.namespace("idempotency", idempotency_key)

    @staticmethod
    def fingerprint(payload: dict[str, Any]) -> str:
        return sha256(dumps_json(payload).encode("utf-8")).hexdigest()

    async def reserve(
        self,
        idempotency_key: str,
        *,
        payload: dict[str, Any],
    ) -> IdempotencyResult:
        key = self._key(idempotency_key)
        fingerprint = self.fingerprint(payload)
        record = {
            "key": idempotency_key,
            "fingerprint": fingerprint,
            "status": "pending",
            "payload": None,
        }
        created = await self.redis.set_json(
            key,
            record,
            ex=self.settings.idempotency_ttl_seconds,
            nx=True,
        )
        if created:
            return IdempotencyResult(
                created=True,
                record=IdempotencyRecord(
                    key=idempotency_key,
                    fingerprint=fingerprint,
                    status="pending",
                ),
            )

        existing = await self.redis.get_json(key)
        if not isinstance(existing, dict):
            raise Conflict("Idempotency record is corrupted")
        if existing.get("fingerprint") != fingerprint:
            raise Conflict("Idempotency key already used for a different request")
        return IdempotencyResult(
            created=False,
            record=IdempotencyRecord(
                key=str(existing.get("key", idempotency_key)),
                fingerprint=str(existing.get("fingerprint", fingerprint)),
                status=str(existing.get("status", "pending")),
                payload=existing.get("payload")
                if isinstance(existing.get("payload"), dict)
                else None,
            ),
        )

    async def store_result(
        self,
        idempotency_key: str,
        *,
        payload: dict[str, Any],
    ) -> None:
        key = self._key(idempotency_key)
        existing = await self.redis.get_json(key)
        if not isinstance(existing, dict):
            raise Conflict("Idempotency record is missing")
        existing["status"] = "completed"
        existing["payload"] = payload
        await self.redis.set_json(key, existing, ex=self.settings.idempotency_ttl_seconds)
