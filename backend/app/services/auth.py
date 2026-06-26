from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import Conflict, Unauthorized
from app.models.domain import AuditLog, RefreshToken, User
from app.repositories.domain import AuditLogRepository, RefreshTokenRepository, UserRepository
from app.security.passwords import hash_password, password_needs_rehash, verify_password
from app.security.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_metadata,
    hash_refresh_token,
)

GENERIC_LOGIN_ERROR = "Invalid email or password"
DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    access_token: str
    access_expires_at: datetime
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit_logs = AuditLogRepository(session)

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().casefold()

    async def audit(
        self,
        action: str,
        result: str,
        correlation_id: str,
        ip: str,
        *,
        actor: UUID | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        await self.audit_logs.add(
            AuditLog(
                actor_user_id=actor,
                action=action,
                resource_type="authentication",
                resource_id=actor,
                result=result,
                correlation_id=correlation_id[:128],
                ip_hash=hash_metadata(ip, self.settings.secret_key),
                details=details or {},
            )
        )

    async def register(
        self,
        email: str,
        password: str,
        display_name: str,
        correlation_id: str,
        ip: str,
        user_agent: str,
    ) -> AuthResult:
        normalized = self.normalize_email(email)
        if await self.users.by_email(normalized) is not None:
            raise Conflict("An account with this email already exists")
        user = User(
            email=normalized,
            password_hash=hash_password(password),
            display_name=display_name,
            role="user",
        )
        self.session.add(user)
        await self.session.flush()
        await self.audit("auth.register", "success", correlation_id, ip, actor=user.id)
        return await self._new_session(user, user_agent)

    async def login(
        self, email: str, password: str, correlation_id: str, ip: str, user_agent: str
    ) -> AuthResult:
        user = await self.users.by_email(self.normalize_email(email))
        if user is None:
            verify_password(DUMMY_PASSWORD_HASH, password)
            await self.audit("auth.login", "failure", correlation_id, ip)
            raise Unauthorized(GENERIC_LOGIN_ERROR)
        if not verify_password(user.password_hash, password):
            if user is not None:
                user.failed_login_count += 1
                user.last_failed_login_at = datetime.now(UTC)
            await self.audit(
                "auth.login", "failure", correlation_id, ip, actor=user.id if user else None
            )
            raise Unauthorized(GENERIC_LOGIN_ERROR)
        if not user.is_active:
            await self.audit("auth.login", "failure", correlation_id, ip, actor=user.id)
            raise Unauthorized(GENERIC_LOGIN_ERROR)
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.last_login_at = datetime.now(UTC)
        await self.audit("auth.login", "success", correlation_id, ip, actor=user.id)
        return await self._new_session(user, user_agent)

    async def _new_session(self, user: User, user_agent: str) -> AuthResult:
        raw_refresh = generate_refresh_token()
        now = datetime.now(UTC)
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_refresh),
                family_id=uuid4(),
                expires_at=now + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
                user_agent_hash=hash_metadata(user_agent, self.settings.secret_key),
            )
        )
        access, expires = create_access_token(user.id, user.role, self.settings)
        return AuthResult(user, access, expires, raw_refresh)

    async def rotate(
        self, raw_token: str, correlation_id: str, ip: str, user_agent: str
    ) -> AuthResult:
        now = datetime.now(UTC)
        current = await self.tokens.by_hash_for_update(hash_refresh_token(raw_token))
        if current is None:
            await self.audit("auth.refresh", "failure", correlation_id, ip)
            raise Unauthorized("Invalid session")
        if current.revoked_at is not None:
            await self.tokens.revoke_family(current.family_id, now)
            await self.audit(
                "auth.refresh_reuse",
                "blocked",
                correlation_id,
                ip,
                actor=current.user_id,
                details={"family_revoked": True},
            )
            raise Unauthorized("Invalid session")
        if current.expires_at.replace(tzinfo=UTC) <= now:
            current.revoked_at = now
            await self.audit("auth.refresh", "failure", correlation_id, ip, actor=current.user_id)
            raise Unauthorized("Invalid session")
        user = await self.users.by_id(current.user_id)
        if user is None or not user.is_active:
            await self.tokens.revoke_family(current.family_id, now)
            raise Unauthorized("Invalid session")
        raw_refresh = generate_refresh_token()
        replacement = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=current.family_id,
            expires_at=now + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
            user_agent_hash=hash_metadata(user_agent, self.settings.secret_key),
        )
        self.session.add(replacement)
        await self.session.flush()
        current.revoked_at = now
        current.replaced_by_id = replacement.id
        access, expires = create_access_token(user.id, user.role, self.settings)
        await self.audit("auth.refresh", "success", correlation_id, ip, actor=user.id)
        return AuthResult(user, access, expires, raw_refresh)

    async def logout(self, raw_token: str, correlation_id: str, ip: str) -> None:
        current = await self.tokens.by_hash_for_update(hash_refresh_token(raw_token))
        if current is not None and current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
            await self.audit("auth.logout", "success", correlation_id, ip, actor=current.user_id)
        else:
            await self.audit("auth.logout", "success", correlation_id, ip)

    async def logout_all(self, user: User, correlation_id: str, ip: str) -> None:
        await self.tokens.revoke_all(user.id, datetime.now(UTC))
        await self.audit("auth.logout_all", "success", correlation_id, ip, actor=user.id)
