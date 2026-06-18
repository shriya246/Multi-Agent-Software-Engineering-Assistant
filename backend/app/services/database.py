from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings


@dataclass(slots=True)
class DatabaseManager:
    settings: Settings
    engine: AsyncEngine = field(init=False)
    session_factory: async_sessionmaker[AsyncSession] = field(init=False)

    def __post_init__(self) -> None:
        self.engine = create_async_engine(
            self.settings.database_url,
            echo=False,
            pool_pre_ping=True,
            **self._engine_kwargs(),
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _engine_kwargs(self) -> dict[str, object]:
        url = make_url(self.settings.database_url)
        if url.get_backend_name() == "sqlite":
            return {"poolclass": NullPool}

        connect_args: dict[str, object] = {}
        if (
            url.get_backend_name() == "postgresql"
            and self.settings.database_statement_timeout_ms > 0
        ):
            connect_args["server_settings"] = {
                "statement_timeout": str(self.settings.database_statement_timeout_ms)
            }
            connect_args["command_timeout"] = self.settings.database_connect_timeout_seconds

        return {
            "pool_size": self.settings.database_pool_size,
            "max_overflow": self.settings.database_max_overflow,
            "pool_timeout": self.settings.database_pool_timeout_seconds,
            "connect_args": connect_args,
        }

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            async with session.begin():
                yield session

    async def ping(self) -> None:
        async with self.session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def healthcheck(self) -> tuple[Literal["ready", "degraded"], str]:
        try:
            await asyncio.wait_for(
                self.ping(),
                timeout=self.settings.database_health_timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - network/database failure path
            return "degraded", exc.__class__.__name__
        return "ready", "connected"

    async def dispose(self) -> None:
        await self.engine.dispose()
