from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import SystemMetadata
from app.repositories.base import Repository


class SystemMetadataRepository(Repository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, metadata_key: str) -> SystemMetadata | None:
        result = await self.session.execute(
            select(SystemMetadata).where(SystemMetadata.metadata_key == metadata_key)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        metadata_key: str,
        metadata_value: dict[str, object],
    ) -> SystemMetadata:
        record = await self.get(metadata_key)
        if record is None:
            record = SystemMetadata(metadata_key=metadata_key, metadata_value=metadata_value)
            self.session.add(record)
        else:
            record.metadata_value = metadata_value
        await self.session.flush()
        return record
