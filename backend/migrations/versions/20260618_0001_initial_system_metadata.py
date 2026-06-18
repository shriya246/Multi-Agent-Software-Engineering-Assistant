"""initial system metadata table

Revision ID: 20260618_0001
Revises:
Create Date: 2026-06-18 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260618_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_metadata",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("metadata_key", sa.String(length=255), nullable=False),
        sa.Column("metadata_value", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("metadata_key", name="uq_system_metadata_metadata_key"),
    )
    op.create_index(
        "ix_system_metadata_metadata_key",
        "system_metadata",
        ["metadata_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_system_metadata_metadata_key", table_name="system_metadata")
    op.drop_table("system_metadata")
