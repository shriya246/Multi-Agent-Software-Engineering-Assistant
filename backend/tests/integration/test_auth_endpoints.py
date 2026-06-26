from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.v1.dependencies import get_rate_limit_service
from app.core.config import Settings
from app.core.container import AppContainer
from app.db.base import Base
from app.main import create_app
from app.models.domain import AuditLog, RefreshToken
from app.services.database import DatabaseManager


class NoopRateLimits:
    async def enforce(self, scope: str, identity: str, limit: int, *, fail_closed: bool) -> None:
        return None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_authentication_flow(tmp_path: Path) -> None:
    database = DatabaseManager(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'api-auth.db').as_posix()}",
            secret_key="integration-test-secret-that-is-long-enough",
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        registration = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "api@example.com",
                "password": "a secure api password",
                "display_name": "API User",
            },
        )
        assert registration.status_code == 201
        assert registration.json()["user"]["email"] == "api@example.com"
        assert "codepilot_refresh" in registration.headers["set-cookie"]
        assert "HttpOnly" in registration.headers["set-cookie"]
        original_refresh = client.cookies.get("codepilot_refresh")
        csrf = client.cookies.get("codepilot_csrf")
        assert original_refresh and csrf

        duplicate = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "API@example.com",
                "password": "a different password",
                "display_name": "Duplicate",
            },
        )
        assert duplicate.status_code == 409

        bad_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
        )
        assert bad_login.status_code == 401
        assert bad_login.json()["error"]["message"] == "Invalid email or password"

        no_csrf = await client.post("/api/v1/auth/refresh")
        assert no_csrf.status_code == 401
        refreshed = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert refreshed.status_code == 200
        replacement_refresh = client.cookies.get("codepilot_refresh")
        csrf = client.cookies.get("codepilot_csrf")
        assert replacement_refresh and replacement_refresh != original_refresh
        assert csrf

        access = refreshed.json()["access_token"]
        current = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert current.status_code == 200

        client.cookies.set("codepilot_refresh", original_refresh, path="/api/v1/auth")
        replay = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert replay.status_code == 401

    async with database.session() as session:
        audit_count = await session.scalar(select(func.count()).select_from(AuditLog))
        active_tokens = await session.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        assert audit_count == 4
        assert active_tokens == 0
    await database.dispose()
