from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_session
from app.models.domain import User
from app.repositories.domain import AgentRunEventRepository
from app.schemas.domain import AgentRunEventListResponse, AgentRunEventSchema, AgentRunSchema
from app.services.authorization import AuthorizationService

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=AgentRunSchema)
async def get_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> AgentRunSchema:
    run = await AuthorizationService(session).require_run(user.id, run_id)
    return AgentRunSchema.model_validate(run)


@router.get("/{run_id}/events", response_model=AgentRunEventListResponse)
async def list_run_events(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> AgentRunEventListResponse:
    run = await AuthorizationService(session).require_run(user.id, run_id)
    events = await AgentRunEventRepository(session).for_run(run.id)
    return AgentRunEventListResponse(
        events=[AgentRunEventSchema.model_validate(event) for event in events]
    )
