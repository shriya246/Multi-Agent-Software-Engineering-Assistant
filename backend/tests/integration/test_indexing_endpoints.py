from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_rate_limit_service
from app.core.config import Settings
from app.core.container import AppContainer
from app.db.base import Base
from app.main import create_app
from app.models.domain import Repository, RepositoryFile, RepositoryRevision, User
from app.services.database import DatabaseManager
from app.services.indexing import IndexingService


class NoopRateLimits:
    async def enforce(self, scope: str, identity: str, limit: int, *, fail_closed: bool) -> None:
        return None


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "a secure password", "display_name": email},
    )
    assert response.status_code == 201
    payload = response.json()
    return {"access_token": payload["access_token"], "user_id": payload["user"]["id"]}


async def _seed_repository(
    session,
    *,
    owner: User,
    revision_sha: str,
    content: str,
) -> tuple[Repository, RepositoryRevision]:
    repository = Repository(
        owner_id=owner.id,
        name="endpoint-demo",
        normalized_clone_url="https://github.com/example/endpoint-demo",
        default_branch="main",
        status="ready_for_indexing",
        indexing_config={},
    )
    session.add(repository)
    await session.flush()
    revision = RepositoryRevision(
        repository_id=repository.id,
        commit_sha=revision_sha,
        ref="main",
        status="ready_for_indexing",
        file_count=1,
        total_bytes=len(content.encode("utf-8")),
    )
    session.add(revision)
    await session.flush()
    repository.latest_revision_id = revision.id
    session.add(
        RepositoryFile(
            revision_id=revision.id,
            normalized_path="python/sample.py",
            language="Python",
            size=len(content.encode("utf-8")),
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            line_count=len(content.splitlines()),
            indexing_status="accepted",
            excluded_reason=None,
            content=content,
        )
    )
    await session.flush()
    return repository, revision


@pytest.mark.integration
@pytest.mark.asyncio
async def test_indexing_endpoints_are_owner_scoped_and_return_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = DatabaseManager(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'indexing-endpoints.db').as_posix()}",
            secret_key="indexing-endpoints-secret-that-is-long-enough",
        )
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    app = create_app()
    app.state.container = AppContainer(
        settings=database.settings,
        database=database,
        redis=None,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_rate_limit_service] = lambda: NoopRateLimits()

    enqueued: list[tuple[str, str]] = []

    def fake_send_task(name: str, args: list[str]) -> None:
        enqueued.append((name, args[0]))

    monkeypatch.setattr("app.api.v1.indexing.celery_app.send_task", fake_send_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        alice = await _register(client, "alice@example.com")
        bob = await _register(client, "bob@example.com")
        alice_headers = {"Authorization": f"Bearer {alice['access_token']}"}
        bob_headers = {"Authorization": f"Bearer {bob['access_token']}"}

        fixture = (
            Path(__file__).resolve().parents[1] / "fixtures" / "indexing" / "python" / "sample.py"
        ).read_text(encoding="utf-8")
        async with database.session() as session:
            owner = await session.get(User, UUID(alice["user_id"]))
            assert owner is not None
            repository, revision = await _seed_repository(
                session,
                owner=owner,
                revision_sha="e" * 40,
                content=fixture,
            )
            await session.commit()

        status_before = await client.get(
            f"/api/v1/repositories/{repository.id}/index-status", headers=alice_headers
        )
        assert status_before.status_code == 200
        assert status_before.json()["snapshot"] is None

        index_response = await client.post(
            f"/api/v1/repositories/{repository.id}/index", headers=alice_headers
        )
        assert index_response.status_code == 202
        assert index_response.json()["repository_id"] == str(repository.id)
        assert enqueued

        async with database.session() as session:
            service = IndexingService(session, database.settings)
            run_id = UUID(index_response.json()["run_id"])
            await service.index_repository(repository.id, run_id)
            await session.commit()

        status_after = await client.get(
            f"/api/v1/repositories/{repository.id}/index-status", headers=alice_headers
        )
        assert status_after.status_code == 200
        assert status_after.json()["latest_indexed_revision_id"] == str(revision.id)

        symbols = await client.get(
            f"/api/v1/repositories/{repository.id}/symbols", headers=alice_headers
        )
        assert symbols.status_code == 200
        assert symbols.json()["symbols"]

        search = await client.get(
            f"/api/v1/repositories/{repository.id}/search",
            headers=alice_headers,
            params={"q": "friendly greeting"},
        )
        assert search.status_code == 200
        evidence = search.json()["evidence"]
        assert evidence
        assert evidence[0]["path"] == "python/sample.py"
        assert evidence[0]["revision_id"] == str(revision.id)

        hidden = await client.get(
            f"/api/v1/repositories/{repository.id}/index-status", headers=bob_headers
        )
        assert hidden.status_code == 404

    await database.dispose()
