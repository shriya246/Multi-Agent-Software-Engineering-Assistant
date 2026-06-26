from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import DependencyUnavailable, RateLimited
from app.services.redis import RedisManager


@dataclass(slots=True)
class RateLimitService:
    redis: RedisManager
    settings: Settings

    async def enforce(self, scope: str, identity: str, limit: int, *, fail_closed: bool) -> None:
        key = self.redis.namespace("rate-limit", scope, identity)
        try:
            count = int(await self.redis.client.incr(key))
            if count == 1:
                await self.redis.client.expire(key, self.settings.auth_rate_limit_window_seconds)
        except Exception as exc:
            if fail_closed:
                raise DependencyUnavailable("Authentication temporarily unavailable") from exc
            return
        if count > limit:
            raise RateLimited("Too many requests; try again later")
