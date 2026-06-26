from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from app.models.domain import (
    AgentRun,
    AgentRunEvent,
    Artifact,
    AuditLog,
    CodeSymbol,
    Patch,
    RefreshToken,
    Repository,
    RepositoryFile,
    RepositoryRevision,
    TestExecution,
    User,
)
from app.repositories.base import Repository as BaseRepository


class UserRepository(BaseRepository):
    async def by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)


class RefreshTokenRepository(BaseRepository):
    async def by_hash_for_update(self, token_hash: bytes) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )
        return result.scalar_one_or_none()

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )

    async def revoke_all(self, user_id: UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )


class RepositoryRepository(BaseRepository):
    async def owned_by_id(self, owner_id: UUID, repository_id: UUID) -> Repository | None:
        result = await self.session.execute(
            select(Repository).where(
                Repository.id == repository_id,
                Repository.owner_id == owner_id,
                Repository.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


class AgentRunRepository(BaseRepository):
    async def owned_by_id(self, owner_id: UUID, run_id: UUID) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.owner_id == owner_id)
        )
        return result.scalar_one_or_none()


class RepositoryRevisionRepository(BaseRepository):
    async def for_repository(self, repository_id: UUID) -> list[RepositoryRevision]:
        result = await self.session.scalars(
            select(RepositoryRevision).where(RepositoryRevision.repository_id == repository_id)
        )
        return list(result.all())


class RepositoryFileRepository(BaseRepository):
    async def for_revision(self, revision_id: UUID) -> list[RepositoryFile]:
        result = await self.session.scalars(
            select(RepositoryFile).where(RepositoryFile.revision_id == revision_id)
        )
        return list(result.all())


class CodeSymbolRepository(BaseRepository):
    async def for_file(self, file_id: UUID) -> list[CodeSymbol]:
        result = await self.session.scalars(select(CodeSymbol).where(CodeSymbol.file_id == file_id))
        return list(result.all())


class AgentRunEventRepository(BaseRepository):
    async def for_run(self, run_id: UUID) -> list[AgentRunEvent]:
        result = await self.session.scalars(
            select(AgentRunEvent)
            .where(AgentRunEvent.run_id == run_id)
            .order_by(AgentRunEvent.sequence)
        )
        return list(result.all())


class ArtifactRepository(BaseRepository):
    async def owned_by_id(self, owner_id: UUID, artifact_id: UUID) -> Artifact | None:
        result = await self.session.execute(
            select(Artifact)
            .join(AgentRun, Artifact.run_id == AgentRun.id)
            .where(Artifact.id == artifact_id, AgentRun.owner_id == owner_id)
        )
        return result.scalar_one_or_none()


class PatchRepository(BaseRepository):
    async def owned_by_id(self, owner_id: UUID, patch_id: UUID) -> Patch | None:
        result = await self.session.execute(
            select(Patch)
            .join(AgentRun, Patch.run_id == AgentRun.id)
            .where(Patch.id == patch_id, AgentRun.owner_id == owner_id)
        )
        return result.scalar_one_or_none()


class TestExecutionRepository(BaseRepository):
    async def owned_by_id(self, owner_id: UUID, execution_id: UUID) -> TestExecution | None:
        result = await self.session.execute(
            select(TestExecution)
            .join(AgentRun, TestExecution.run_id == AgentRun.id)
            .where(TestExecution.id == execution_id, AgentRun.owner_id == owner_id)
        )
        return result.scalar_one_or_none()


class AuditLogRepository(BaseRepository):
    async def add(self, audit_log: AuditLog) -> AuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log
