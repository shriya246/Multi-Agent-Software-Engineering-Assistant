from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import NotFound
from app.db.base import Base
from app.models.domain import Repository, RepositoryFile, RepositoryRevision, User
from app.services.database import DatabaseManager
from app.services.indexing import DeterministicEmbeddingProvider, IndexingService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "indexing"


async def _build_database(tmp_path: Path) -> DatabaseManager:
    database = DatabaseManager(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'indexing.db').as_posix()}",
            secret_key="indexing-test-secret-that-is-long-enough",
        )
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


async def _create_user(session, email: str) -> User:
    user = User(
        email=email,
        password_hash="hash",
        display_name=email,
        role="user",
        is_active=True,
        email_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_repository(
    session,
    *,
    owner_id,
    name: str,
    revision_sha: str,
    files: list[tuple[str, str, str | None]],
    status: str = "ready_for_indexing",
) -> tuple[Repository, RepositoryRevision]:
    repository = Repository(
        owner_id=owner_id,
        name=name,
        normalized_clone_url=f"https://github.com/example/{name}",
        default_branch="main",
        status=status,
        indexing_config={},
    )
    session.add(repository)
    await session.flush()
    revision = RepositoryRevision(
        repository_id=repository.id,
        commit_sha=revision_sha,
        ref="main",
        status="ready_for_indexing",
        file_count=len(files),
        total_bytes=0,
    )
    session.add(revision)
    await session.flush()
    repository.latest_revision_id = revision.id
    for normalized_path, content, language in files:
        encoded = content.encode("utf-8")
        session.add(
            RepositoryFile(
                revision_id=revision.id,
                normalized_path=normalized_path,
                language=language,
                size=len(encoded),
                content_hash=hashlib.sha256(encoded).hexdigest(),
                line_count=len(content.splitlines()),
                indexing_status="accepted",
                excluded_reason=None,
                content=content,
            )
        )
    await session.flush()
    return repository, revision


async def _add_revision(
    session,
    *,
    repository: Repository,
    revision_sha: str,
    files: list[tuple[str, str, str | None]],
) -> RepositoryRevision:
    revision = RepositoryRevision(
        repository_id=repository.id,
        commit_sha=revision_sha,
        ref="main",
        status="ready_for_indexing",
        file_count=len(files),
        total_bytes=0,
    )
    session.add(revision)
    await session.flush()
    repository.latest_revision_id = revision.id
    for normalized_path, content, language in files:
        encoded = content.encode("utf-8")
        session.add(
            RepositoryFile(
                revision_id=revision.id,
                normalized_path=normalized_path,
                language=language,
                size=len(encoded),
                content_hash=hashlib.sha256(encoded).hexdigest(),
                line_count=len(content.splitlines()),
                indexing_status="accepted",
                excluded_reason=None,
                content=content,
            )
        )
    await session.flush()
    return revision


@pytest.mark.asyncio
async def test_indexing_creates_searchable_chunks_and_reuses_incrementally(
    tmp_path: Path,
) -> None:
    database = await _build_database(tmp_path)
    provider = DeterministicEmbeddingProvider(dimensions=32)
    async with database.session() as session:
        owner = await _create_user(session, "alice@example.com")
        python_source = (FIXTURES / "python" / "sample.py").read_text(encoding="utf-8")
        js_source = (FIXTURES / "javascript" / "sample.js").read_text(encoding="utf-8")
        repository, _ = await _seed_repository(
            session,
            owner_id=owner.id,
            name="demo",
            revision_sha="a" * 40,
            files=[
                ("python/sample.py", python_source, "Python"),
                ("javascript/sample.js", js_source, "JavaScript"),
            ],
        )
        await session.commit()

    async with database.session() as session:
        service = IndexingService(session, database.settings, embedding_provider=provider)
        repository, run, created = await service.create_index_run(
            owner.id, repository.id, "corr-1", "127.0.0.1"
        )
        assert created is True
        snapshot = await service.index_repository(repository.id, run.id)
        assert snapshot.status == "ready"
        assert snapshot.statistics["files_seen"] == 2
        assert snapshot.statistics["symbols_extracted"] > 0
        assert snapshot.statistics["chunks_produced"] > 0
        index_status = await service.get_index_status(owner.id, repository.id)
        assert index_status["latest_indexed_revision_id"] == str(repository.latest_revision_id)
        symbols = await service.list_symbols(owner.id, repository.id)
        assert symbols
        assert any(symbol["symbol_type"] == "class" for symbol in symbols)
        evidence = await service.search(owner.id, repository.id, "friendly greeting")
        assert evidence
        assert evidence[0].path == "python/sample.py"
        assert evidence[0].retrieval_method == "hybrid"
        assert "greet" in evidence[0].exact_content

        chunks_before = await service.chunks.for_repository_revision(
            repository.id, repository.latest_revision_id
        )
        chunk_ids_before = [chunk.id for chunk in chunks_before]
        first_batch_sizes = list(provider.batch_sizes)
        await session.commit()

    async with database.session() as session:
        service = IndexingService(session, database.settings, embedding_provider=provider)
        modified_python = python_source.replace("return f\"Hello, {name}\"", "return f\"Hola, {name}\"")
        fresh_repository = await session.get(Repository, repository.id)
        assert fresh_repository is not None
        second_revision = await _add_revision(
            session,
            repository=fresh_repository,
            revision_sha="b" * 40,
            files=[
                ("python/sample.py", modified_python, "Python"),
            ],
        )
        fresh_repository.status = "ready_for_indexing"
        await session.commit()

    async with database.session() as session:
        service = IndexingService(session, database.settings, embedding_provider=provider)
        repository, run, created = await service.create_index_run(
            owner.id, repository.id, "corr-2", "127.0.0.1"
        )
        assert created is True
        snapshot = await service.index_repository(repository.id, run.id)
        assert snapshot.statistics["files_deleted"] == 1
        assert snapshot.statistics["reused_vectors"] > 0
        chunks_after = await service.chunks.for_repository_revision(
            repository.id, second_revision.id
        )
        assert chunks_after
        assert [chunk.id for chunk in chunks_after] != chunk_ids_before
        second_batch_sizes = provider.batch_sizes[len(first_batch_sizes) :]
        assert sum(second_batch_sizes) < sum(first_batch_sizes)
        search_results = await service.search(owner.id, repository.id, "Hola")
        assert search_results
        assert search_results[0].revision_id == str(second_revision.id)
        await session.commit()

    await database.dispose()


@pytest.mark.asyncio
async def test_indexing_rejects_cross_user_access(tmp_path: Path) -> None:
    database = await _build_database(tmp_path)
    async with database.session() as session:
        owner = await _create_user(session, "owner@example.com")
        other = await _create_user(session, "other@example.com")
        repository, _ = await _seed_repository(
            session,
            owner_id=owner.id,
            name="private",
            revision_sha="c" * 40,
            files=[("python/sample.py", (FIXTURES / "python" / "sample.py").read_text(encoding="utf-8"), "Python")],
        )
        await session.commit()

    async with database.session() as session:
        service = IndexingService(session, database.settings)
        with pytest.raises(NotFound):
            await service.get_index_status(other.id, repository.id)
        with pytest.raises(NotFound):
            await service.search(other.id, repository.id, "hello")
        with pytest.raises(NotFound):
            await service.list_symbols(other.id, repository.id)

    await database.dispose()


@pytest.mark.asyncio
async def test_large_symbol_is_split_and_chunk_ids_are_stable(tmp_path: Path) -> None:
    database = await _build_database(tmp_path)
    provider = DeterministicEmbeddingProvider(dimensions=16)
    big_function_lines = ["def big_function():"]
    big_function_lines.extend(f"    value_{index} = {index}" for index in range(360))
    big_function_lines.append("    return value_359")
    large_source = "\n".join(big_function_lines)

    async with database.session() as session:
        owner = await _create_user(session, "split@example.com")
        repository, _ = await _seed_repository(
            session,
            owner_id=owner.id,
            name="split-demo",
            revision_sha="d" * 40,
            files=[("python/large.py", large_source, "Python")],
        )
        await session.commit()

    async with database.session() as session:
        service = IndexingService(session, database.settings, embedding_provider=provider)
        repository, run, created = await service.create_index_run(
            owner.id, repository.id, "corr-3", "127.0.0.1"
        )
        assert created is True
        snapshot = await service.index_repository(repository.id, run.id)
        assert snapshot.status == "ready"
        chunks = await service.chunks.for_repository_revision(
            repository.id, repository.latest_revision_id
        )
        large_chunks = [chunk for chunk in chunks if chunk.normalized_path == "python/large.py"]
        assert large_chunks
        assert max(chunk.part_count for chunk in large_chunks) > 1
        chunk_ids = [chunk.id for chunk in large_chunks]

        rerun, rerun_task, created_again = await service.create_index_run(
            owner.id, repository.id, "corr-4", "127.0.0.1"
        )
        assert created_again is True
        rerun_snapshot = await service.index_repository(rerun.id, rerun_task.id)
        assert rerun_snapshot.id == snapshot.id
        repeated_chunks = await service.chunks.for_repository_revision(
            repository.id, repository.latest_revision_id
        )
        assert [chunk.id for chunk in repeated_chunks if chunk.normalized_path == "python/large.py"] == chunk_ids

    await database.dispose()
