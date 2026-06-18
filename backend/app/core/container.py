from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.services.database import DatabaseManager
from app.services.redis import RedisManager


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    database: DatabaseManager
    redis: RedisManager


def build_container(settings: Settings) -> AppContainer:
    return AppContainer(
        settings=settings,
        database=DatabaseManager(settings),
        redis=RedisManager(settings),
    )
