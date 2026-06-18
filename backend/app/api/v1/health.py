from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.common import HealthResponse
from app.services.health import build_readiness_payload

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    container = request.app.state.container
    return await build_readiness_payload(container.settings, container.database, container.redis)
