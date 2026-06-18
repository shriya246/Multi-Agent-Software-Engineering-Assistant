from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.container import AppContainer
from app.schemas.pagination import PaginationParams
from app.services.database import DatabaseManager
from app.services.idempotency import IdempotencyService
from app.services.redis import RedisManager


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


def get_pagination_params(
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginationParams:
    return pagination
