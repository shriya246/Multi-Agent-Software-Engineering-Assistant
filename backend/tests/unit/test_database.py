from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.core.config import Settings
from app.db.base import Base
from app.models.system import SystemMetadata
from app.repositories.system_metadata import SystemMetadataRepository
from app.services.database import DatabaseManager


@pytest.mark.asyncio
async def test_database_transaction_rolls_back(tmp_path: Path) -> None:
    database = DatabaseManager(
        Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'codepilot.db').as_posix()}")
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    with pytest.raises(RuntimeError, match="boom"):
        async with database.transaction() as session:
            repository = SystemMetadataRepository(session)
            await repository.upsert("example", {"value": "first"})
            raise RuntimeError("boom")

    async with database.session() as session:
        result = await session.execute(select(SystemMetadata))
        assert result.scalars().all() == []

    await database.dispose()


@pytest.mark.asyncio
async def test_database_health_check(tmp_path: Path) -> None:
    database = DatabaseManager(
        Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'health.db').as_posix()}")
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    status, detail = await database.healthcheck()
    assert status == "ready"
    assert detail == "connected"
    await database.dispose()


@pytest.mark.asyncio
async def test_database_session_can_query(tmp_path: Path) -> None:
    database = DatabaseManager(
        Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'query.db').as_posix()}")
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with database.session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

    await database.dispose()
