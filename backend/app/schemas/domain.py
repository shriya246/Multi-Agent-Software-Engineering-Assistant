from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DomainSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class RepositorySchema(DomainSchema):
    owner_id: UUID
    name: str
    normalized_clone_url: str
    default_branch: str | None
    status: str
    latest_revision_id: UUID | None
    indexing_config: dict[str, Any]
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RepositoryRevisionSchema(DomainSchema):
    repository_id: UUID
    commit_sha: str
    ref: str | None
    status: str
    cloned_at: datetime | None
    indexed_at: datetime | None
    file_count: int
    total_bytes: int
    error_code: str | None
    error_summary: str | None


class RepositoryFileSchema(DomainSchema):
    revision_id: UUID
    normalized_path: str
    language: str | None
    size: int
    content_hash: str
    line_count: int
    indexing_status: str
    excluded_reason: str | None


class CodeSymbolSchema(DomainSchema):
    file_id: UUID
    symbol_type: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    signature: str | None
    parent_symbol_id: UUID | None
    symbol_metadata: dict[str, Any]


class AgentRunSchema(DomainSchema):
    owner_id: UUID
    repository_id: UUID
    revision_id: UUID | None
    run_type: str
    status: str
    input_summary: str
    model_provider: str
    model_identifier: str
    prompt_version: str
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None
    input_units: int | None
    output_units: int | None


class AgentRunEventSchema(DomainSchema):
    run_id: UUID
    sequence: int
    event_type: str
    public_message: str
    created_at: datetime


class ArtifactSchema(DomainSchema):
    run_id: UUID
    artifact_type: str
    storage_path: str | None
    content_reference: str | None
    media_type: str
    size: int
    checksum: str
    artifact_metadata: dict[str, Any]


class PatchSchema(DomainSchema):
    run_id: UUID
    status: str
    base_commit_sha: str
    unified_diff: str
    diff_checksum: str
    affected_file_count: int
    approval_metadata: dict[str, Any] | None
    validation_metadata: dict[str, Any] | None
    applied_at: datetime | None
    reverted_at: datetime | None


class TestExecutionSchema(DomainSchema):
    run_id: UUID
    patch_id: UUID | None
    status: str
    command_identifier: str
    exit_code: int | None
    duration_ms: int | None
    stdout: str | None
    stderr: str | None
    resource_summary: dict[str, Any] | None


class AuditLogSchema(DomainSchema):
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    result: str
    correlation_id: str
    details: dict[str, Any]
    created_at: datetime
