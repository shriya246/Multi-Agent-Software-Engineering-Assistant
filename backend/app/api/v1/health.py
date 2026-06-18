from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.common import HealthResponse, VersionResponse
from app.services.health import build_readiness_payload

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse)
async def ready(request: Request) -> HealthResponse:
    settings = cast(Settings, request.app.state.settings)
    payload = await build_readiness_payload(settings)
    return HealthResponse(status=payload.status, checks=payload.checks)


@router.get("/api/v1/version", response_model=VersionResponse)
async def version(request: Request) -> VersionResponse:
    settings = cast(Settings, request.app.state.settings)
    return VersionResponse(version=settings.app_version, environment=settings.environment)
