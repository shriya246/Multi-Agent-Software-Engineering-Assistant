from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.container import build_container
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.container = build_container(settings)
    logger.info("startup", extra={"environment": settings.environment})
    try:
        yield
    finally:
        await app.state.container.redis.close()
        await app.state.container.database.dispose()
        logger.info("shutdown")
