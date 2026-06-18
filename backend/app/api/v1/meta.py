from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.common import VersionResponse

router = APIRouter(tags=["meta"])


@router.get("/version", response_model=VersionResponse)
async def version(request: Request) -> VersionResponse:
    settings = request.app.state.settings
    assert isinstance(settings, Settings)
    return VersionResponse(version=settings.app_version, environment=settings.environment)
