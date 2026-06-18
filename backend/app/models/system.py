from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SystemMetadata(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_metadata"

    metadata_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    metadata_value: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
