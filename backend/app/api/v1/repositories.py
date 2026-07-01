from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_container, get_current_user
from app.core.container import AppContainer
from app.core.exceptions import BadRequest
from app.core.middleware import get_correlation_id
from app.db.session import get_session
from app.models.domain import User
from app.repositories.domain import RepositoryFileRepository, RepositoryRepository
from app.schemas.domain import (
    AgentRunSchema,
    RepositoryCreateRequest,
    RepositoryCreateResponse,
    RepositoryFileListResponse,
    RepositoryFileSchema,
    RepositoryListResponse,
    RepositorySchema,
    RepositorySyncRequest,
)
from app.services.authorization import AuthorizationService
from app.services.ingestion import IngestionInputError, IngestionService
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enqueue_ingestion(repository_id: UUID, run_id: UUID) -> None:
    celery_app.send_task(
        "app.workers.tasks.ingest_repository",
        args=[str(repository_id), str(run_id)],
    )


@router.post(
    "",
    response_model=RepositoryCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_repository(
    payload: RepositoryCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositoryCreateResponse:
    service = IngestionService(session, container.settings)
    try:
        repository, run = await service.create_repository(
            user.id,
            payload.clone_url,
            payload.ref,
            get_correlation_id(),
            _client_ip(request),
        )
    except IngestionInputError as exc:
        raise BadRequest(str(exc)) from exc
    await session.flush()
    await session.refresh(repository)
    payload_response = RepositoryCreateResponse(
        repository=RepositorySchema.model_validate(repository),
        run=None if run is None else AgentRunSchema.model_validate(run),
    )
    await session.commit()
    if run is not None:
        _enqueue_ingestion(repository.id, run.id)
    return payload_response


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositoryListResponse:
    repositories = await RepositoryRepository(session).list_for_owner(user.id)
    return RepositoryListResponse(
        repositories=[RepositorySchema.model_validate(repository) for repository in repositories]
    )


@router.get("/{repository_id}", response_model=RepositorySchema)
async def get_repository(
    repository_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositorySchema:
    repository = await AuthorizationService(session).require_repository(user.id, repository_id)
    return RepositorySchema.model_validate(repository)


@router.delete(
    "/{repository_id}",
    response_model=RepositorySchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_repository(
    repository_id: UUID,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositorySchema:
    service = IngestionService(session, container.settings)
    repository = await service.mark_deleting(
        user.id,
        repository_id,
        get_correlation_id(),
        _client_ip(request),
    )
    await session.flush()
    await session.refresh(repository)
    payload_response = RepositorySchema.model_validate(repository)
    await session.commit()
    celery_app.send_task(
        "app.workers.tasks.cleanup_repository_workspace",
        args=[str(repository.id)],
    )
    response.headers["Location"] = f"/api/v1/repositories/{repository.id}"
    return payload_response


@router.post(
    "/{repository_id}/sync",
    response_model=RepositoryCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_repository(
    repository_id: UUID,
    payload: RepositorySyncRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositoryCreateResponse:
    service = IngestionService(session, container.settings)
    try:
        repository, run = await service.sync_repository(
            user.id,
            repository_id,
            payload.ref,
            get_correlation_id(),
            _client_ip(request),
        )
    except IngestionInputError as exc:
        raise BadRequest(str(exc)) from exc
    await session.flush()
    await session.refresh(repository)
    payload_response = RepositoryCreateResponse(
        repository=RepositorySchema.model_validate(repository),
        run=AgentRunSchema.model_validate(run),
    )
    await session.commit()
    _enqueue_ingestion(repository.id, run.id)
    return payload_response


@router.get("/{repository_id}/files", response_model=RepositoryFileListResponse)
async def list_repository_files(
    repository_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> RepositoryFileListResponse:
    repository = await AuthorizationService(session).require_repository(user.id, repository_id)
    if repository.latest_revision_id is None:
        return RepositoryFileListResponse(files=[])
    files = await RepositoryFileRepository(session).for_revision(repository.latest_revision_id)
    return RepositoryFileListResponse(
        files=[RepositoryFileSchema.model_validate(file) for file in files]
    )
