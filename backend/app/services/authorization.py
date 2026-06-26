from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.domain import AgentRun, Repository
from app.repositories.domain import AgentRunRepository, RepositoryRepository


class AuthorizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repositories = RepositoryRepository(session)
        self.runs = AgentRunRepository(session)

    async def require_repository(self, owner_id: UUID, repository_id: UUID) -> Repository:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        return repository

    async def require_run(self, owner_id: UUID, run_id: UUID) -> AgentRun:
        run = await self.runs.owned_by_id(owner_id, run_id)
        if run is None:
            raise NotFound()
        return run
