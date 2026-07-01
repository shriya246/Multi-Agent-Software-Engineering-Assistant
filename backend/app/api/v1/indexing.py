from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_container,
    get_current_user,
    get_rate_limit_service,
)
from app.core.container import AppContainer
from app.core.middleware import get_correlation_id
from app.db.session import get_session
from app.models.domain import User
from app.schemas.indexing import (
    RepositoryIndexResponse,
    RepositoryIndexStatusSchema,
    RepositorySearchResponse,
    RepositorySymbolListResponse,
    SearchEvidenceSchema,
)
from app.services.authorization import AuthorizationService
from app.services.indexing import IndexingService
from app.services.rate_limit import RateLimitService
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/repositories", tags=["indexing"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enqueue_indexing(repository_id: UUID, run_id: UUID) -> None:
    celery_app.send_task(
        "app.workers.tasks.index_repository",
        args=[str(repository_id), str(run_id)],
    )


@router.post(
    "/{repository_id}/index",
    response_model=RepositoryIndexResponse,
    status_code=202,
)
async def index_repository(
    repository_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositoryIndexResponse:
    service = IndexingService(session, container.settings)
    repository, run, created = await service.create_index_run(
        user.id,
        repository_id,
        get_correlation_id(),
        _client_ip(request),
    )
    await session.flush()
    await session.commit()
    if created:
        _enqueue_indexing(repository.id, run.id)
    return RepositoryIndexResponse(run_id=run.id, repository_id=repository.id)


@router.get("/{repository_id}/index-status", response_model=RepositoryIndexStatusSchema)
async def index_status(
    repository_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> RepositoryIndexStatusSchema:
    payload = await IndexingService(session, container.settings).get_index_status(user.id, repository_id)
    return RepositoryIndexStatusSchema.model_validate(payload)


@router.get("/{repository_id}/symbols", response_model=RepositorySymbolListResponse)
async def list_symbols(
    repository_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    container: Annotated[AppContainer, Depends(get_container)],
    revision_id: UUID | None = None,
    symbol_type: str | None = Query(default=None, max_length=64),
    name: str | None = Query(default=None, max_length=512),
    path: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RepositorySymbolListResponse:
    service = IndexingService(session, container.settings)
    symbols = await service.list_symbols(
        user.id,
        repository_id,
        revision_id=revision_id,
        symbol_type=symbol_type,
        name_query=name,
        normalized_path=path,
        limit=limit,
        offset=offset,
    )
    return RepositorySymbolListResponse(symbols=symbols)  # type: ignore[arg-type]


@router.get("/{repository_id}/search", response_model=RepositorySearchResponse)
async def search_repository(
    repository_id: UUID,
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    rate_limits: Annotated[RateLimitService, Depends(get_rate_limit_service)],
    user: Annotated[User, Depends(get_current_user)],
    revision_id: UUID | None = None,
    path_prefix: str | None = Query(default=None, max_length=2048),
    language: str | None = Query(default=None, max_length=64),
    top_k: int = Query(default=10, ge=1, le=50),
    method: str = Query(default="hybrid", pattern="^(dense|lexical|hybrid)$"),
) -> RepositorySearchResponse:
    await rate_limits.enforce(
        "repository-search",
        f"{user.id}:{repository_id}",
        container.settings.indexing_search_rate_limit,
        fail_closed=False,
    )
    service = IndexingService(session, container.settings)
    evidence = await service.search(
        user.id,
        repository_id,
        q,
        revision_id=revision_id,
        path_prefix=path_prefix,
        language=language,
        top_k=top_k,
        method=method,
    )
    return RepositorySearchResponse(
        evidence=[SearchEvidenceSchema.model_validate(asdict(item)) for item in evidence]
    )
