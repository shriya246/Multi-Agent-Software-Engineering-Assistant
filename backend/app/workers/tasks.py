from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.services.database import DatabaseManager
from app.services.indexing import IndexingService
from app.services.ingestion import IngestionService


def ping() -> str:
    return "pong"


def cleanup_stale_artifacts() -> dict[str, str]:
    return {"status": "noop"}


async def _ingest_repository(repository_id: UUID, run_id: UUID) -> None:
    database = DatabaseManager(get_settings())
    try:
        async with database.session() as session:
            try:
                await IngestionService(session, database.settings).ingest(repository_id, run_id)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await database.dispose()


def ingest_repository(repository_id: str, run_id: str) -> dict[str, str]:
    asyncio.run(_ingest_repository(UUID(repository_id), UUID(run_id)))
    return {"status": "completed", "repository_id": repository_id, "run_id": run_id}


async def _index_repository(repository_id: UUID, run_id: UUID) -> None:
    database = DatabaseManager(get_settings())
    try:
        async with database.session() as session:
            try:
                await IndexingService(session, database.settings).index_repository(
                    repository_id, run_id
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await database.dispose()


def index_repository(repository_id: str, run_id: str) -> dict[str, str]:
    asyncio.run(_index_repository(UUID(repository_id), UUID(run_id)))
    return {"status": "completed", "repository_id": repository_id, "run_id": run_id}


async def _cleanup_repository_workspace(repository_id: UUID) -> None:
    database = DatabaseManager(get_settings())
    try:
        async with database.session() as session:
            await IngestionService(session, database.settings).delete_workspace_and_mark_deleted(
                repository_id
            )
            await IndexingService(session, database.settings).cleanup_repository(repository_id)
            await session.commit()
    finally:
        await database.dispose()


def cleanup_repository_workspace(repository_id: str) -> dict[str, str]:
    asyncio.run(_cleanup_repository_workspace(UUID(repository_id)))
    return {"status": "completed", "repository_id": repository_id}
