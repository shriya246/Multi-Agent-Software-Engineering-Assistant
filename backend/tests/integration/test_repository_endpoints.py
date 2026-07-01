from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_rate_limit_service
from app.core.config import Settings
from app.core.container import AppContainer
from app.db.base import Base
from app.main import create_app
from app.services.database import DatabaseManager


class NoopRateLimits:
    async def enforce(self, scope: str, identity: str, limit: int, *, fail_closed: bool) -> None:
        return None


async def _register(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "a secure password", "display_name": email},
    )
    assert response.status_code == 201
    return str(response.json()["access_token"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_lifecycle_and_cross_user_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = DatabaseManager(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'repos.db').as_posix()}",
            secret_key="integration-test-secret-that-is-long-enough",
        )
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    enqueued: list[tuple[str, str]] = []
    cleanups: list[str] = []
    app = create_app()
    app.state.container = AppContainer(
        settings=database.settings,
        database=database,
        redis=None,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_rate_limit_service] = lambda: NoopRateLimits()

    def fake_send_task(name: str, args: list[str]) -> None:
        if name.endswith("ingest_repository"):
            enqueued.append((args[0], args[1]))
        if name.endswith("cleanup_repository_workspace"):
            cleanups.append(args[0])

    monkeypatch.setattr("app.api.v1.repositories.celery_app.send_task", fake_send_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        alice_access = await _register(client, "alice@example.com")
        bob_access = await _register(client, "bob@example.com")
        alice_headers = {"Authorization": f"Bearer {alice_access}"}
        bob_headers = {"Authorization": f"Bearer {bob_access}"}

        created = await client.post(
            "/api/v1/repositories",
            headers=alice_headers,
            json={"clone_url": "https://github.com/example/project.git", "ref": "main"},
        )
        assert created.status_code == 202
        repository = created.json()["repository"]
        run = created.json()["run"]
        assert repository["normalized_clone_url"] == "https://github.com/example/project"
        assert run["status"] == "queued"
        assert len(enqueued) == 1

        duplicate = await client.post(
            "/api/v1/repositories",
            headers=alice_headers,
            json={"clone_url": "https://github.com/example/project", "ref": "main"},
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["repository"]["id"] == repository["id"]
        assert len(enqueued) == 1

        hidden = await client.get(f"/api/v1/repositories/{repository['id']}", headers=bob_headers)
        assert hidden.status_code == 404

        files = await client.get(
            f"/api/v1/repositories/{repository['id']}/files", headers=alice_headers
        )
        assert files.status_code == 200
        assert files.json()["files"] == []

        run_response = await client.get(f"/api/v1/runs/{run['id']}", headers=alice_headers)
        assert run_response.status_code == 200
        bob_run = await client.get(f"/api/v1/runs/{run['id']}", headers=bob_headers)
        assert bob_run.status_code == 404

        invalid = await client.post(
            "/api/v1/repositories",
            headers=alice_headers,
            json={"clone_url": "git://github.com/example/unsafe"},
        )
        assert invalid.status_code == 400

        deleted = await client.delete(
            f"/api/v1/repositories/{repository['id']}", headers=alice_headers
        )
        assert deleted.status_code == 202
        assert deleted.json()["status"] == "deleting"
        assert cleanups == [repository["id"]]

    await database.dispose()
