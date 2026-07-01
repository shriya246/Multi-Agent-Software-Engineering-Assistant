"""phase 5 parsing, symbols, and indexing

Revision ID: 20260701_0002
Revises: 7a0021405758
Create Date: 2026-07-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260701_0002"
down_revision = "7a0021405758"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.add_column(sa.Column("latest_indexed_revision_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_repositories_latest_indexed_revision_id_repository_revisions"),
            "repository_revisions",
            ["latest_indexed_revision_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("repository_files") as batch_op:
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=True))

    op.create_table(
        "repository_index_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding_config", sa.JSON(), nullable=False),
        sa.Column("statistics", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_summary", sa.String(length=1000), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["revision_id"], ["repository_revisions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_index_snapshots")),
        sa.UniqueConstraint(
            "repository_id",
            "revision_id",
            "embedding_model",
            "embedding_dimensions",
            name="uq_repository_index_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_repository_index_snapshots_repository_status",
        "repository_index_snapshots",
        ["repository_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_repository_index_snapshots_owner_repository",
        "repository_index_snapshots",
        ["owner_id", "repository_id"],
        unique=False,
    )
    op.create_index(
        "ix_repository_index_snapshots_revision",
        "repository_index_snapshots",
        ["revision_id"],
        unique=False,
    )

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("normalized_path", sa.String(length=2048), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("symbol_name", sa.String(length=512), nullable=True),
        sa.Column("qualified_name", sa.String(length=2048), nullable=True),
        sa.Column("symbol_type", sa.String(length=64), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("part_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("exact_content", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("dense_embedding", sa.JSON(), nullable=True),
        sa.Column("chunk_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["repository_index_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["repository_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["repository_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_chunks")),
    )
    op.create_index("ix_code_chunks_snapshot_path", "code_chunks", ["snapshot_id", "normalized_path"], unique=False)
    op.create_index(
        "ix_code_chunks_repository_revision",
        "code_chunks",
        ["repository_id", "revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_code_chunks_owner_repository",
        "code_chunks",
        ["owner_id", "repository_id"],
        unique=False,
    )
    op.create_index("ix_code_chunks_language", "code_chunks", ["language"], unique=False)
    op.create_index("ix_code_chunks_symbol_type", "code_chunks", ["symbol_type"], unique=False)
    op.create_index("ix_code_chunks_content_hash", "code_chunks", ["content_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_code_chunks_content_hash", table_name="code_chunks")
    op.drop_index("ix_code_chunks_symbol_type", table_name="code_chunks")
    op.drop_index("ix_code_chunks_language", table_name="code_chunks")
    op.drop_index("ix_code_chunks_owner_repository", table_name="code_chunks")
    op.drop_index("ix_code_chunks_repository_revision", table_name="code_chunks")
    op.drop_index("ix_code_chunks_snapshot_path", table_name="code_chunks")
    op.drop_table("code_chunks")

    op.drop_index("ix_repository_index_snapshots_revision", table_name="repository_index_snapshots")
    op.drop_index(
        "ix_repository_index_snapshots_owner_repository",
        table_name="repository_index_snapshots",
    )
    op.drop_index(
        "ix_repository_index_snapshots_repository_status",
        table_name="repository_index_snapshots",
    )
    op.drop_table("repository_index_snapshots")

    with op.batch_alter_table("repository_files") as batch_op:
        batch_op.drop_column("content")

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_repositories_latest_indexed_revision_id_repository_revisions"),
            type_="foreignkey",
        )
        batch_op.drop_column("latest_indexed_revision_id")
