from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import AppContainer
from app.core.exceptions import Forbidden, Unauthorized
from app.db.session import get_session
from app.models.domain import User
from app.repositories.domain import UserRepository
from app.schemas.pagination import PaginationParams
from app.security.tokens import decode_access_token
from app.services.database import DatabaseManager
from app.services.idempotency import IdempotencyService
from app.services.rate_limit import RateLimitService
from app.services.redis import RedisManager

bearer_scheme = HTTPBearer(auto_error=False)


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def get_database_manager(
    container: Annotated[AppContainer, Depends(get_container)],
) -> DatabaseManager:
    return container.database


def get_redis_manager(
    container: Annotated[AppContainer, Depends(get_container)],
) -> RedisManager:
    return container.redis


def get_idempotency_service(
    container: Annotated[AppContainer, Depends(get_container)],
) -> IdempotencyService:
    return IdempotencyService(container.redis, container.settings)


def get_rate_limit_service(
    container: Annotated[AppContainer, Depends(get_container)],
) -> RateLimitService:
    return RateLimitService(container.redis, container.settings)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    rate_limits: Annotated[RateLimitService, Depends(get_rate_limit_service)],
) -> User:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise Unauthorized("Authentication required")
    claims = decode_access_token(credentials.credentials, container.settings)
    if claims is None:
        raise Unauthorized("Authentication required")
    user = await UserRepository(session).by_id(claims.user_id)
    if user is None:
        raise Unauthorized("Authentication required")
    if not user.is_active:
        raise Forbidden("Account is disabled")
    await rate_limits.enforce(
        "authenticated",
        str(user.id),
        container.settings.authenticated_api_rate_limit,
        fail_closed=False,
    )
    return user


def require_role(*roles: str):  # type: ignore[no-untyped-def]
    async def role_dependency(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in roles:
            raise Forbidden("Insufficient permissions")
        return user

    return role_dependency


def get_pagination_params(
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginationParams:
    return pagination
