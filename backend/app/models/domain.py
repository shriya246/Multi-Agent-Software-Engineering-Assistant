from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.base import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
    user_agent_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))


class Repository(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("owner_id", "normalized_clone_url", name="uq_repositories_owner_url"),
        Index("ix_repositories_owner_status", "owner_id", "status"),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    normalized_clone_url: Mapped[str] = mapped_column(String(2048))
    default_branch: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    latest_revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("repository_revisions.id", ondelete="SET NULL", use_alter=True)
    )
    indexing_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class RepositoryRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repository_revisions"
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", name="uq_revision_repository_sha"),
        CheckConstraint("file_count >= 0", name="file_count_nonnegative"),
        CheckConstraint("total_bytes >= 0", name="total_bytes_nonnegative"),
    )

    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64))
    ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    cloned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(String(1000))


class RepositoryFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repository_files"
    __table_args__ = (
        UniqueConstraint("revision_id", "normalized_path", name="uq_file_revision_path"),
        CheckConstraint("size >= 0", name="size_nonnegative"),
        CheckConstraint("line_count >= 0", name="line_count_nonnegative"),
    )

    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_revisions.id", ondelete="CASCADE"), index=True
    )
    normalized_path: Mapped[str] = mapped_column(String(2048))
    language: Mapped[str | None] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(BigInteger)
    content_hash: Mapped[str] = mapped_column(String(128))
    line_count: Mapped[int] = mapped_column(Integer)
    indexing_status: Mapped[str] = mapped_column(String(32), index=True)
    excluded_reason: Mapped[str | None] = mapped_column(String(255))


class CodeSymbol(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "code_symbols"
    __table_args__ = (
        CheckConstraint("start_line > 0", name="start_line_positive"),
        CheckConstraint("end_line >= start_line", name="line_range_valid"),
        Index("ix_symbols_file_qualified_name", "file_id", "qualified_name"),
    )

    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), index=True
    )
    symbol_type: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    qualified_name: Mapped[str] = mapped_column(String(2048))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    signature: Mapped[str | None] = mapped_column(Text)
    parent_symbol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("code_symbols.id", ondelete="SET NULL")
    )
    symbol_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_owner_status", "owner_id", "status"),)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("repository_revisions.id", ondelete="SET NULL")
    )
    run_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_summary: Mapped[str] = mapped_column(Text)
    model_provider: Mapped[str] = mapped_column(String(64))
    model_identifier: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    input_units: Mapped[int | None] = mapped_column(BigInteger)
    output_units: Mapped[int | None] = mapped_column(BigInteger)


class AgentRunEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_run_event_sequence"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    public_message: Mapped[str] = mapped_column(String(2000))
    private_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class Artifact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str | None] = mapped_column(String(2048))
    content_reference: Mapped[str | None] = mapped_column(String(2048))
    media_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(128))
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Patch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patches"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    base_commit_sha: Mapped[str] = mapped_column(String(64))
    unified_diff: Mapped[str] = mapped_column(Text)
    diff_checksum: Mapped[str] = mapped_column(String(128), unique=True)
    affected_file_count: Mapped[int] = mapped_column(Integer)
    approval_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    validation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TestExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_executions"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    patch_id: Mapped[UUID | None] = mapped_column(ForeignKey("patches.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), index=True)
    command_identifier: Mapped[str] = mapped_column(String(255))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    resource_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    result: Mapped[str] = mapped_column(String(32))
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    ip_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
