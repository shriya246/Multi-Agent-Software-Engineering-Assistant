from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import AppContainer


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container = request.app.state.container
    assert isinstance(container, AppContainer)
    async with container.database.session() as session:
        yield session
