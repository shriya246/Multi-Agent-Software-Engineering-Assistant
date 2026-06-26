from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import DependencyUnavailable, RateLimited, Unauthorized
from app.db.base import Base
from app.models.domain import AuditLog, Repository, User
from app.repositories.domain import RepositoryRepository
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, decode_access_token, hash_refresh_token
from app.services.auth import AuthService
from app.services.database import DatabaseManager
from app.services.rate_limit import RateLimitService


@pytest.fixture()
async def database(tmp_path: Path):
    manager = DatabaseManager(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}",
            secret_key="test-secret-that-is-long-enough-for-signing",
        )
    )
    async with manager.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield manager
    await manager.dispose()


def test_argon2id_password_hashing() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert password_hash.startswith("$argon2id$")
    assert "correct horse" not in password_hash
    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "wrong")


def test_access_token_expiry_is_enforced() -> None:
    settings = Settings(
        secret_key="test-secret-that-is-more-than-long-enough", access_token_ttl_seconds=-1
    )
    token, _ = create_access_token(uuid4(), "user", settings)
    assert decode_access_token(token, settings) is None


@pytest.mark.asyncio
async def test_registration_login_rotation_replay_logout_and_audit(
    database: DatabaseManager,
) -> None:
    settings = database.settings
    async with database.session() as session:
        service = AuthService(session, settings)
        registered = await service.register(
            " Person@Example.COM ", "a secure password 123", "Person", "corr-1", "127.0.0.1", "test"
        )
        await session.commit()
        assert registered.user.email == "person@example.com"
        assert registered.user.password_hash != "a secure password 123"

        with pytest.raises(Unauthorized, match="Invalid email or password"):
            await service.login("person@example.com", "wrong", "corr-2", "127.0.0.1", "test")
        await session.commit()

        logged_in = await service.login(
            "person@example.com", "a secure password 123", "corr-3", "127.0.0.1", "test"
        )
        rotated = await service.rotate(logged_in.refresh_token, "corr-4", "127.0.0.1", "test")
        await session.commit()
        assert rotated.refresh_token != logged_in.refresh_token

        with pytest.raises(Unauthorized, match="Invalid session"):
            await service.rotate(logged_in.refresh_token, "corr-5", "127.0.0.1", "test")
        await session.commit()

        replacement = await service.tokens.by_hash_for_update(
            hash_refresh_token(rotated.refresh_token)
        )
        assert replacement is not None and replacement.revoked_at is not None
        await service.logout(registered.refresh_token, "corr-6", "127.0.0.1")
        await service.logout_all(registered.user, "corr-7", "127.0.0.1")
        await session.commit()

        audit_count = await session.scalar(select(func.count()).select_from(AuditLog))
        assert audit_count == 7
        reuse = await session.scalar(
            select(AuditLog).where(AuditLog.action == "auth.refresh_reuse")
        )
        assert reuse is not None and reuse.details == {"family_revoked": True}


@pytest.mark.asyncio
async def test_duplicate_email_constraint_and_disabled_user(database: DatabaseManager) -> None:
    async with database.session() as session:
        first = User(
            email="duplicate@example.com",
            password_hash=hash_password("password one 123"),
            display_name="One",
        )
        session.add(first)
        await session.commit()
        session.add(
            User(
                email="duplicate@example.com",
                password_hash=hash_password("password two 123"),
                display_name="Two",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        first.is_active = False
        await session.commit()
        with pytest.raises(Unauthorized, match="Invalid email or password"):
            await AuthService(session, database.settings).login(
                first.email, "password one 123", "corr", "127.0.0.1", "test"
            )


@pytest.mark.asyncio
async def test_repository_queries_are_owner_scoped(database: DatabaseManager) -> None:
    async with database.session() as session:
        owner = User(email="owner@example.com", password_hash="hash", display_name="Owner")
        other = User(email="other@example.com", password_hash="hash", display_name="Other")
        session.add_all([owner, other])
        await session.flush()
        repository = Repository(
            owner_id=owner.id,
            name="example",
            normalized_clone_url="https://github.com/example/example.git",
            status="ready",
            indexing_config={},
        )
        session.add(repository)
        await session.commit()
        scoped = RepositoryRepository(session)
        assert await scoped.owned_by_id(owner.id, repository.id) is repository
        assert await scoped.owned_by_id(other.id, repository.id) is None
        assert await scoped.owned_by_id(uuid4(), repository.id) is None


class FakeRedisClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.value = 0
        self.fail = fail

    async def incr(self, key: str) -> int:
        if self.fail:
            raise ConnectionError
        self.value += 1
        return self.value

    async def expire(self, key: str, ttl: int) -> bool:
        return True


class FakeRedisManager:
    def __init__(self, client: FakeRedisClient) -> None:
        self.client = client

    def namespace(self, *parts: str) -> str:
        return ":".join(parts)


@pytest.mark.asyncio
async def test_rate_limit_and_redis_outage_policy() -> None:
    settings = Settings(auth_rate_limit_window_seconds=60)
    manager = FakeRedisManager(FakeRedisClient())
    limiter = RateLimitService(manager, settings)  # type: ignore[arg-type]
    await limiter.enforce("login", "identity", 1, fail_closed=True)
    with pytest.raises(RateLimited):
        await limiter.enforce("login", "identity", 1, fail_closed=True)

    unavailable = RateLimitService(
        FakeRedisManager(FakeRedisClient(fail=True)),
        settings,  # type: ignore[arg-type]
    )
    with pytest.raises(DependencyUnavailable):
        await unavailable.enforce("login", "identity", 1, fail_closed=True)
    await unavailable.enforce("authenticated", "identity", 1, fail_closed=False)
