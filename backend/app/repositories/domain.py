from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update

from app.models.domain import (
    AgentRun,
    AgentRunEvent,
    Artifact,
    AuditLog,
    CodeSymbol,
    CodeChunk,
    Patch,
    RefreshToken,
    Repository,
    RepositoryIndexSnapshot,
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
    async def list_for_owner(self, owner_id: UUID) -> list[Repository]:
        result = await self.session.scalars(
            select(Repository)
            .where(Repository.owner_id == owner_id, Repository.deleted_at.is_(None))
            .order_by(Repository.created_at.desc())
        )
        return list(result.all())

    async def by_owner_url(self, owner_id: UUID, normalized_clone_url: str) -> Repository | None:
        result = await self.session.execute(
            select(Repository).where(
                Repository.owner_id == owner_id,
                Repository.normalized_clone_url == normalized_clone_url,
                Repository.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

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
    async def list_for_repository(self, owner_id: UUID, repository_id: UUID) -> list[AgentRun]:
        result = await self.session.scalars(
            select(AgentRun)
            .where(AgentRun.owner_id == owner_id, AgentRun.repository_id == repository_id)
            .order_by(AgentRun.created_at.desc())
        )
        return list(result.all())

    async def active_for_repository(
        self, repository_id: UUID, *, run_type: str | None = None
    ) -> AgentRun | None:
        predicates = [
            AgentRun.repository_id == repository_id,
            AgentRun.status.in_(("queued", "running")),
        ]
        if run_type is not None:
            predicates.append(AgentRun.run_type == run_type)
        result = await self.session.execute(
            select(AgentRun)
            .where(*predicates)
            .order_by(AgentRun.created_at.desc())
        )
        return result.scalars().first()

    async def owned_by_id(self, owner_id: UUID, run_id: UUID) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.owner_id == owner_id)
        )
        return result.scalar_one_or_none()


class RepositoryRevisionRepository(BaseRepository):
    async def latest_for_repository(self, repository_id: UUID) -> RepositoryRevision | None:
        result = await self.session.execute(
            select(RepositoryRevision)
            .where(RepositoryRevision.repository_id == repository_id)
            .order_by(RepositoryRevision.created_at.desc())
        )
        return result.scalars().first()

    async def by_repository_commit(
        self, repository_id: UUID, commit_sha: str
    ) -> RepositoryRevision | None:
        result = await self.session.execute(
            select(RepositoryRevision).where(
                RepositoryRevision.repository_id == repository_id,
                RepositoryRevision.commit_sha == commit_sha,
            )
        )
        return result.scalar_one_or_none()

    async def for_repository(self, repository_id: UUID) -> list[RepositoryRevision]:
        result = await self.session.scalars(
            select(RepositoryRevision).where(RepositoryRevision.repository_id == repository_id)
        )
        return list(result.all())


class RepositoryFileRepository(BaseRepository):
    async def for_revision(self, revision_id: UUID) -> list[RepositoryFile]:
        result = await self.session.scalars(
            select(RepositoryFile)
            .where(RepositoryFile.revision_id == revision_id)
            .order_by(RepositoryFile.normalized_path)
        )
        return list(result.all())

    async def replace_for_revision(self, revision_id: UUID, files: list[Any]) -> None:
        await self.session.execute(
            delete(RepositoryFile).where(RepositoryFile.revision_id == revision_id)
        )
        for item in files:
            self.session.add(
                RepositoryFile(
                    revision_id=revision_id,
                    normalized_path=item.normalized_path,
                    language=item.language,
                    size=item.size,
                    content_hash=item.content_hash,
                    line_count=item.line_count,
                    indexing_status=item.indexing_status,
                    excluded_reason=item.excluded_reason,
                    content=item.content,
                )
            )

    async def by_revision_path(self, revision_id: UUID, normalized_path: str) -> RepositoryFile | None:
        result = await self.session.execute(
            select(RepositoryFile).where(
                RepositoryFile.revision_id == revision_id,
                RepositoryFile.normalized_path == normalized_path,
            )
        )
        return result.scalar_one_or_none()

    async def accepted_for_revision(self, revision_id: UUID) -> list[RepositoryFile]:
        result = await self.session.scalars(
            select(RepositoryFile)
            .where(
                RepositoryFile.revision_id == revision_id,
                RepositoryFile.indexing_status == "accepted",
            )
            .order_by(RepositoryFile.normalized_path)
        )
        return list(result.all())


class CodeSymbolRepository(BaseRepository):
    async def for_file(self, file_id: UUID) -> list[CodeSymbol]:
        result = await self.session.scalars(select(CodeSymbol).where(CodeSymbol.file_id == file_id))
        return list(result.all())

    async def delete_for_file_ids(self, file_ids: list[UUID]) -> None:
        if not file_ids:
            return
        await self.session.execute(delete(CodeSymbol).where(CodeSymbol.file_id.in_(file_ids)))

    async def for_repository_revision(
        self,
        repository_id: UUID,
        revision_id: UUID,
        *,
        symbol_type: str | None = None,
        name_query: str | None = None,
        normalized_path: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[tuple[CodeSymbol, RepositoryFile]]:
        stmt = (
            select(CodeSymbol, RepositoryFile)
            .join(RepositoryFile, CodeSymbol.file_id == RepositoryFile.id)
            .join(RepositoryRevision, RepositoryFile.revision_id == RepositoryRevision.id)
            .where(
                RepositoryFile.revision_id == revision_id,
                RepositoryRevision.repository_id == repository_id,
            )
        )
        if symbol_type is not None:
            stmt = stmt.where(CodeSymbol.symbol_type == symbol_type)
        if name_query is not None:
            stmt = stmt.where(CodeSymbol.name.ilike(f"%{name_query}%"))
        if normalized_path is not None:
            stmt = stmt.where(RepositoryFile.normalized_path == normalized_path)
        stmt = stmt.order_by(RepositoryFile.normalized_path, CodeSymbol.start_line)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return [(symbol, file) for symbol, file in result.all()]


class AgentRunEventRepository(BaseRepository):
    async def add(self, event: AgentRunEvent) -> AgentRunEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def next_sequence(self, run_id: UUID) -> int:
        result = await self.session.scalar(
            select(func.max(AgentRunEvent.sequence)).where(AgentRunEvent.run_id == run_id)
        )
        return int(result or 0) + 1

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


class RepositoryIndexSnapshotRepository(BaseRepository):
    async def latest_for_repository(self, repository_id: UUID) -> RepositoryIndexSnapshot | None:
        result = await self.session.execute(
            select(RepositoryIndexSnapshot)
            .where(RepositoryIndexSnapshot.repository_id == repository_id)
            .order_by(RepositoryIndexSnapshot.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def latest_ready_for_repository(
        self, repository_id: UUID
    ) -> RepositoryIndexSnapshot | None:
        result = await self.session.execute(
            select(RepositoryIndexSnapshot)
            .where(
                RepositoryIndexSnapshot.repository_id == repository_id,
                RepositoryIndexSnapshot.status == "ready",
            )
            .order_by(RepositoryIndexSnapshot.indexed_at.desc().nullslast())
        )
        return result.scalar_one_or_none()

    async def by_revision(
        self, repository_id: UUID, revision_id: UUID
    ) -> RepositoryIndexSnapshot | None:
        result = await self.session.execute(
            select(RepositoryIndexSnapshot).where(
                RepositoryIndexSnapshot.repository_id == repository_id,
                RepositoryIndexSnapshot.revision_id == revision_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, snapshot: RepositoryIndexSnapshot) -> RepositoryIndexSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot


class CodeChunkRepository(BaseRepository):
    async def delete_for_repository(self, repository_id: UUID) -> None:
        await self.session.execute(delete(CodeChunk).where(CodeChunk.repository_id == repository_id))

    async def delete_for_snapshot(self, snapshot_id: UUID) -> None:
        await self.session.execute(delete(CodeChunk).where(CodeChunk.snapshot_id == snapshot_id))

    async def add_all(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        for chunk in chunks:
            self.session.add(chunk)
        await self.session.flush()
        return chunks

    async def for_snapshot(self, snapshot_id: UUID) -> list[CodeChunk]:
        result = await self.session.scalars(
            select(CodeChunk).where(CodeChunk.snapshot_id == snapshot_id).order_by(
                CodeChunk.normalized_path,
                CodeChunk.start_line,
                CodeChunk.part_number,
            )
        )
        return list(result.all())

    async def for_repository_revision(
        self,
        repository_id: UUID,
        revision_id: UUID,
        *,
        path_prefix: str | None = None,
        language: str | None = None,
    ) -> list[CodeChunk]:
        stmt = select(CodeChunk).where(
            CodeChunk.repository_id == repository_id,
            CodeChunk.revision_id == revision_id,
        )
        if path_prefix is not None:
            stmt = stmt.where(CodeChunk.normalized_path.ilike(f"{path_prefix}%"))
        if language is not None:
            stmt = stmt.where(CodeChunk.language == language)
        stmt = stmt.order_by(CodeChunk.normalized_path, CodeChunk.start_line, CodeChunk.part_number)
        result = await self.session.scalars(stmt)
        return list(result.all())
