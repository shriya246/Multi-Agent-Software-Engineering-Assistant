from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepositoryIndexSnapshotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    revision_id: UUID
    commit_sha: str
    status: str
    embedding_model: str
    embedding_dimensions: int
    statistics: dict[str, Any]
    indexed_at: datetime | None
    error_code: str | None
    error_summary: str | None


class RepositoryIndexStatusSchema(BaseModel):
    repository_id: UUID
    latest_revision_id: UUID | None
    latest_indexed_revision_id: UUID | None
    status: str
    snapshot: RepositoryIndexSnapshotSchema | None
    ready_snapshot_id: UUID | None


class RepositoryIndexResponse(BaseModel):
    run_id: UUID
    repository_id: UUID


class RepositorySymbolSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    revision_id: UUID
    normalized_path: str
    language: str | None
    symbol_type: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    signature: str | None
    parent_symbol_id: UUID | None
    symbol_metadata: dict[str, Any]


class RepositorySymbolListResponse(BaseModel):
    symbols: list[RepositorySymbolSchema]


class SearchEvidenceSchema(BaseModel):
    path: str
    language: str | None
    start_line: int
    end_line: int
    symbol: str | None
    score: float
    retrieval_method: str
    exact_content: str
    revision_id: str
    commit_sha: str
    symbol_type: str
    qualified_name: str | None
    chunk_id: str


class RepositorySearchResponse(BaseModel):
    evidence: list[SearchEvidenceSchema]

