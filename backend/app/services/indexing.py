from __future__ import annotations

import asyncio
import hashlib
import math
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import Conflict, NotFound
from app.models.domain import (
    AgentRun,
    AgentRunEvent,
    CodeChunk,
    CodeSymbol,
    Repository,
    RepositoryFile,
    RepositoryIndexSnapshot,
    RepositoryRevision,
)
from app.parsing.index import ParsedFile, ParsedSymbol, ParserRegistry
from app.repositories.domain import (
    AgentRunEventRepository,
    AgentRunRepository,
    CodeChunkRepository,
    CodeSymbolRepository,
    RepositoryFileRepository,
    RepositoryIndexSnapshotRepository,
    RepositoryRepository,
    RepositoryRevisionRepository,
)
from app.services.ingestion import IngestionService

RUN_TYPE_INDEXING = "repository_indexing"


@dataclass(slots=True)
class EmbeddingConfig:
    base_url: str
    model: str
    batch_size: int
    timeout_seconds: float
    dimensions: int


@dataclass(slots=True)
class IndexStatistics:
    files_seen: int = 0
    files_accepted: int = 0
    files_excluded: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    parse_successes: int = 0
    parse_failures: int = 0
    symbols_extracted: int = 0
    chunks_produced: int = 0
    embedding_batches: int = 0
    embedding_vectors: int = 0
    reused_vectors: int = 0
    lexical_terms: int = 0
    qdrant_write_duration_ms: int = 0
    indexing_duration_ms: int = 0
    parser_names: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_seen": self.files_seen,
            "files_accepted": self.files_accepted,
            "files_excluded": self.files_excluded,
            "files_changed": self.files_changed,
            "files_unchanged": self.files_unchanged,
            "files_deleted": self.files_deleted,
            "parse_successes": self.parse_successes,
            "parse_failures": self.parse_failures,
            "symbols_extracted": self.symbols_extracted,
            "chunks_produced": self.chunks_produced,
            "embedding_batches": self.embedding_batches,
            "embedding_vectors": self.embedding_vectors,
            "reused_vectors": self.reused_vectors,
            "lexical_terms": self.lexical_terms,
            "qdrant_write_duration_ms": self.qdrant_write_duration_ms,
            "indexing_duration_ms": self.indexing_duration_ms,
            "parser_names": self.parser_names,
            "failure_reasons": self.failure_reasons,
        }


@dataclass(slots=True)
class SearchEvidence:
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


@dataclass(slots=True)
class IndexedChunkDraft:
    chunk_id: uuid.UUID
    snapshot_id: uuid.UUID
    owner_id: uuid.UUID
    repository_id: uuid.UUID
    revision_id: uuid.UUID
    file_id: uuid.UUID
    commit_sha: str
    normalized_path: str
    language: str | None
    symbol_name: str | None
    qualified_name: str | None
    symbol_type: str
    start_line: int
    end_line: int
    part_number: int
    part_count: int
    content_hash: str
    exact_content: str
    search_text: str
    dense_embedding: list[float] | None
    chunk_metadata: dict[str, Any]


class EmbeddingProvider(Protocol):
    provider_name: str
    model_identifier: str
    dimensions: int

    async def validate_model_available(self) -> None: ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicEmbeddingProvider:
    provider_name = "deterministic"

    def __init__(self, *, model_identifier: str = "deterministic-hash", dimensions: int = 64) -> None:
        self.model_identifier = model_identifier
        self.dimensions = dimensions
        self.batch_sizes: list[int] = []

    async def validate_model_available(self) -> None:
        return None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, len(digest), 2):
                index = int.from_bytes(digest[offset : offset + 2], "big") % self.dimensions
                vector[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude > 0:
            vector = [value / magnitude for value in vector]
        return vector


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self.model_identifier = config.model
        self.dimensions = config.dimensions

    async def validate_model_available(self) -> None:
        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=timeout) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models", []) if isinstance(payload, dict) else []
            names = {
                item.get("name")
                for item in models
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            if self.config.model not in names:
                raise RuntimeError(f"Ollama embedding model {self.config.model} is not available")

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        batches = [
            texts[index : index + self.config.batch_size]
            for index in range(0, len(texts), self.config.batch_size)
        ]
        embeddings: list[list[float]] = []
        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=timeout) as client:
            for batch in batches:
                embeddings.extend(await self._embed_batch(client, batch))
        return embeddings

    async def _embed_batch(
        self, client: httpx.AsyncClient, batch: list[str]
    ) -> list[list[float]]:
        delay = 0.25
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                return await self._post_embeddings(client, batch)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {400, 401, 403, 404, 422}:
                    raise RuntimeError("Ollama returned a permanent embedding error") from exc
                last_error = exc
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
            await asyncio.sleep(delay)
            delay *= 2
        assert last_error is not None
        raise RuntimeError("Unable to obtain embeddings from Ollama") from last_error

    async def _post_embeddings(
        self, client: httpx.AsyncClient, batch: list[str]
    ) -> list[list[float]]:
        payload = {"model": self.config.model, "input": batch}
        response = await client.post("/api/embed", json=payload)
        if response.status_code == 404:
            return await self._post_legacy_embeddings(client, batch)
        response.raise_for_status()
        data = response.json()
        embeddings: list[list[float]] = []
        if isinstance(data, dict) and isinstance(data.get("embeddings"), list):
            for item in data["embeddings"]:
                embeddings.append([float(value) for value in item])
        elif isinstance(data, dict) and isinstance(data.get("embedding"), list):
            embeddings.append([float(value) for value in data["embedding"]])
        elif isinstance(data, dict) and isinstance(data.get("embeddings"), list) is False:
            embedding = data.get("embedding")
            if isinstance(embedding, list):
                embeddings.append([float(value) for value in embedding])
        if not embeddings:
            raise RuntimeError("Unexpected Ollama embedding response")
        if len(embeddings) == 1 and len(batch) > 1:
            embeddings = [embeddings[0] for _ in batch]
        if any(len(vector) != self.config.dimensions for vector in embeddings):
            raise RuntimeError("Ollama embedding dimensionality does not match configuration")
        return embeddings

    async def _post_legacy_embeddings(
        self, client: httpx.AsyncClient, batch: list[str]
    ) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for prompt in batch:
            response = await client.post(
                "/api/embeddings",
                json={"model": self.config.model, "prompt": prompt},
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding") if isinstance(data, dict) else None
            if not isinstance(embedding, list):
                raise RuntimeError("Unexpected Ollama embedding response")
            vector = [float(value) for value in embedding]
            if len(vector) != self.config.dimensions:
                raise RuntimeError(
                    "Ollama embedding dimensionality does not match configuration"
                )
            embeddings.append(vector)
        return embeddings


class IndexingService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        parser_registry: ParserRegistry | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.ingestion = IngestionService(session, settings)
        self.repositories = RepositoryRepository(session)
        self.revisions = RepositoryRevisionRepository(session)
        self.files = RepositoryFileRepository(session)
        self.runs = AgentRunRepository(session)
        self.events = AgentRunEventRepository(session)
        self.snapshots = RepositoryIndexSnapshotRepository(session)
        self.chunks = CodeChunkRepository(session)
        self.symbols = CodeSymbolRepository(session)
        self.parsers = parser_registry or ParserRegistry()
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider(
            dimensions=settings.indexing_embedding_dimensions
        )

    async def create_index_run(
        self,
        owner_id: uuid.UUID,
        repository_id: uuid.UUID,
        correlation_id: str,
        ip: str,
    ) -> tuple[Repository, AgentRun, bool]:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        if repository.latest_revision_id is None:
            raise Conflict("Repository has no revision to index")
        active = await self.runs.active_for_repository(repository.id, run_type=RUN_TYPE_INDEXING)
        if active is not None:
            return repository, active, False
        run = AgentRun(
            owner_id=owner_id,
            repository_id=repository.id,
            revision_id=repository.latest_revision_id,
            run_type=RUN_TYPE_INDEXING,
            status="queued",
            input_summary=f"Index {repository.normalized_clone_url}",
            model_provider=self.embedding_provider.provider_name,
            model_identifier=self.embedding_provider.model_identifier,
            prompt_version="phase-5-indexing",
            started_at=None,
            completed_at=None,
            cancellation_metadata={
                "requested_revision_id": str(repository.latest_revision_id),
                "correlation_id": correlation_id[:128],
                "ip_hash_hint": ip,
            },
            error_code=None,
            error_message=None,
            input_units=None,
            output_units=None,
        )
        self.session.add(run)
        await self.session.flush()
        await self._add_event(run.id, "queued", "Repository indexing queued")
        return repository, run, True

    async def index_repository(self, repository_id: uuid.UUID, run_id: uuid.UUID) -> RepositoryIndexSnapshot:
        repository = await self.session.get(Repository, repository_id)
        run = await self.session.get(AgentRun, run_id)
        if repository is None or run is None:
            raise NotFound()
        if repository.latest_revision_id is None:
            raise Conflict("Repository has no revision to index")
        revision = await self.session.get(RepositoryRevision, repository.latest_revision_id)
        if revision is None:
            raise NotFound()
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await self._add_event(run.id, "started", "Repository indexing started")
        existing = await self.snapshots.by_revision(repository.id, revision.id)
        if existing is not None and existing.status == "ready":
            run.status = "succeeded"
            run.completed_at = datetime.now(UTC)
            run.revision_id = revision.id
            repository.latest_indexed_revision_id = revision.id
            repository.status = "ready"
            revision.status = "ready"
            revision.indexed_at = existing.indexed_at
            return existing

        await self.embedding_provider.validate_model_available()
        await self.ingestion.transition(repository, "indexing")
        revision.status = "indexing"
        snapshot = RepositoryIndexSnapshot(
            owner_id=repository.owner_id,
            repository_id=repository.id,
            revision_id=revision.id,
            commit_sha=revision.commit_sha,
            status="indexing",
            parser_name="parser-registry",
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_identifier,
            embedding_dimensions=self.embedding_provider.dimensions,
            embedding_config={
                "batch_size": self.settings.indexing_embedding_batch_size,
                "timeout_seconds": self.settings.indexing_embedding_timeout_seconds,
                "chunk_max_chars": self.settings.indexing_chunk_max_chars,
                "chunk_max_lines": self.settings.indexing_chunk_max_lines,
                "chunk_overlap_lines": self.settings.indexing_chunk_overlap_lines,
            },
            statistics={},
            error_code=None,
            error_summary=None,
            indexed_at=None,
        )
        self.session.add(snapshot)
        await self.session.flush()
        statistics = IndexStatistics()
        started_at = time.monotonic()
        previous_snapshot = await self.snapshots.latest_ready_for_repository(repository.id)
        previous_chunks = (
            await self.chunks.for_snapshot(previous_snapshot.id) if previous_snapshot else []
        )
        previous_chunk_embeddings = {_embedding_key(chunk): chunk for chunk in previous_chunks}
        files = await self.files.accepted_for_revision(revision.id)
        file_map = {file.normalized_path: file for file in files}
        all_files = await self.files.for_revision(revision.id)
        statistics.files_seen = len(all_files)
        statistics.files_accepted = len(files)
        all_files = await self.files.for_revision(revision.id)
        statistics.files_excluded = max(len(all_files) - len(files), 0)
        if previous_snapshot:
            previous_files = await self.files.for_revision(previous_snapshot.revision_id)
            previous_file_map = {
                file.normalized_path: file
                for file in previous_files
                if file.indexing_status == "accepted"
            }
            statistics.files_deleted = max(
                len(set(previous_file_map).difference(file_map)),
                0,
            )
        else:
            previous_file_map = {}

        current_chunk_drafts: list[IndexedChunkDraft] = []
        current_symbols: list[CodeSymbol] = []
        for file in files:
            previous_file = previous_file_map.get(file.normalized_path)
            if previous_file is None:
                statistics.files_changed += 1
            elif previous_file.content_hash == file.content_hash:
                statistics.files_unchanged += 1
            else:
                statistics.files_changed += 1
            parsed = self.parsers.parse(Path(file.normalized_path), file.content or "")
            if parsed.fallback_used:
                statistics.parse_failures += 1
                statistics.failure_reasons.extend(error.code for error in parsed.errors)
            else:
                statistics.parse_successes += 1
            statistics.parser_names.append(parsed.language or "unknown")
            symbol_rows, chunk_drafts = _materialize_file(
                snapshot_id=snapshot.id,
                owner_id=repository.owner_id,
                repository_id=repository.id,
                revision_id=revision.id,
                commit_sha=revision.commit_sha,
                file=file,
                parsed=parsed,
                settings=self.settings,
            )
            current_symbols.extend(symbol_rows)
            current_chunk_drafts.extend(chunk_drafts)
            statistics.symbols_extracted += len(symbol_rows)
            statistics.chunks_produced += len(chunk_drafts)
            statistics.lexical_terms += sum(len(_tokenize(draft.search_text)) for draft in chunk_drafts)

        if current_symbols:
            self.session.add_all(current_symbols)
            await self.session.flush()
            _apply_symbol_parent_links(current_symbols)
            await self.session.flush()

        embeddings_to_compute: list[str] = []
        drafts_to_embed: list[IndexedChunkDraft] = []
        for draft in current_chunk_drafts:
            previous = previous_chunk_embeddings.get(_embedding_key_from_draft(draft))
            if previous is not None and isinstance(previous.dense_embedding, list):
                draft.dense_embedding = [float(value) for value in previous.dense_embedding]
                statistics.reused_vectors += 1
                continue
            embeddings_to_compute.append(draft.search_text)
            drafts_to_embed.append(draft)

        if embeddings_to_compute:
            batches = _batch_texts(embeddings_to_compute, self.settings.indexing_embedding_batch_size)
            cursor = 0
            for batch in batches:
                vectors = await self.embedding_provider.embed_texts(batch)
                statistics.embedding_batches += 1
                statistics.embedding_vectors += len(vectors)
                for vector in vectors:
                    draft = drafts_to_embed[cursor]
                    draft.dense_embedding = vector
                    cursor += 1

        for draft in current_chunk_drafts:
            if draft.dense_embedding is None and self.embedding_provider.dimensions > 0:
                draft.dense_embedding = [0.0] * self.embedding_provider.dimensions
        chunk_models = [
            CodeChunk(
                id=draft.chunk_id,
                snapshot_id=draft.snapshot_id,
                owner_id=draft.owner_id,
                repository_id=draft.repository_id,
                revision_id=draft.revision_id,
                file_id=draft.file_id,
                commit_sha=draft.commit_sha,
                normalized_path=draft.normalized_path,
                language=draft.language,
                symbol_name=draft.symbol_name,
                qualified_name=draft.qualified_name,
                symbol_type=draft.symbol_type,
                start_line=draft.start_line,
                end_line=draft.end_line,
                part_number=draft.part_number,
                part_count=draft.part_count,
                content_hash=draft.content_hash,
                exact_content=draft.exact_content,
                search_text=draft.search_text,
                dense_embedding=draft.dense_embedding,
                chunk_metadata=draft.chunk_metadata,
            )
            for draft in current_chunk_drafts
        ]
        write_started = time.monotonic()
        await self.chunks.add_all(chunk_models)
        statistics.qdrant_write_duration_ms = int((time.monotonic() - write_started) * 1000)
        statistics.indexing_duration_ms = int((time.monotonic() - started_at) * 1000)
        snapshot.status = "ready"
        snapshot.statistics = statistics.to_dict()
        snapshot.indexed_at = datetime.now(UTC)
        repository.latest_indexed_revision_id = revision.id
        repository.status = "ready"
        revision.status = "ready"
        revision.indexed_at = snapshot.indexed_at
        run.status = "succeeded"
        run.revision_id = revision.id
        run.completed_at = snapshot.indexed_at
        run.input_units = statistics.files_seen
        run.output_units = statistics.chunks_produced
        await self._add_event(run.id, "completed", "Repository indexing completed")
        return snapshot

    async def get_index_status(self, owner_id: uuid.UUID, repository_id: uuid.UUID) -> dict[str, Any]:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        latest_snapshot = await self.snapshots.latest_for_repository(repository.id)
        ready_snapshot = await self.snapshots.latest_ready_for_repository(repository.id)
        return {
            "repository_id": str(repository.id),
            "latest_revision_id": str(repository.latest_revision_id) if repository.latest_revision_id else None,
            "latest_indexed_revision_id": str(repository.latest_indexed_revision_id)
            if repository.latest_indexed_revision_id
            else None,
            "status": repository.status,
            "snapshot": None
            if latest_snapshot is None
            else {
                "id": str(latest_snapshot.id),
                "revision_id": str(latest_snapshot.revision_id),
                "commit_sha": latest_snapshot.commit_sha,
                "status": latest_snapshot.status,
                "embedding_model": latest_snapshot.embedding_model,
                "embedding_dimensions": latest_snapshot.embedding_dimensions,
                "statistics": latest_snapshot.statistics,
                "indexed_at": latest_snapshot.indexed_at,
                "error_code": latest_snapshot.error_code,
                "error_summary": latest_snapshot.error_summary,
            },
            "ready_snapshot_id": None if ready_snapshot is None else str(ready_snapshot.id),
        }

    async def list_symbols(
        self,
        owner_id: uuid.UUID,
        repository_id: uuid.UUID,
        *,
        revision_id: uuid.UUID | None = None,
        symbol_type: str | None = None,
        name_query: str | None = None,
        normalized_path: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        target_revision_id = revision_id or repository.latest_indexed_revision_id
        if target_revision_id is None:
            return []
        rows = await self.symbols.for_repository_revision(
            repository.id,
            target_revision_id,
            symbol_type=symbol_type,
            name_query=name_query,
            normalized_path=normalized_path,
            limit=limit,
            offset=offset,
        )
        results: list[dict[str, Any]] = []
        for symbol, file in rows:
            results.append(
                {
                    "id": str(symbol.id),
                    "file_id": str(symbol.file_id),
                    "revision_id": str(file.revision_id),
                    "normalized_path": file.normalized_path,
                    "language": file.language,
                    "symbol_type": symbol.symbol_type,
                    "name": symbol.name,
                    "qualified_name": symbol.qualified_name,
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                    "signature": symbol.signature,
                    "parent_symbol_id": str(symbol.parent_symbol_id)
                    if symbol.parent_symbol_id
                    else None,
                    "symbol_metadata": symbol.symbol_metadata,
                }
            )
        return results

    async def search(
        self,
        owner_id: uuid.UUID,
        repository_id: uuid.UUID,
        query: str,
        *,
        revision_id: uuid.UUID | None = None,
        path_prefix: str | None = None,
        language: str | None = None,
        top_k: int | None = None,
        method: str = "hybrid",
    ) -> list[SearchEvidence]:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        target_revision_id = revision_id or repository.latest_indexed_revision_id
        if target_revision_id is None:
            return []
        limit = top_k or self.settings.indexing_top_k
        chunks = await self.chunks.for_repository_revision(
            repository.id,
            target_revision_id,
            path_prefix=path_prefix,
            language=language,
        )
        if not chunks:
            return []
        query_vector = (await self.embedding_provider.embed_texts([query]))[0]
        dense_ranked = sorted(
            (
                (chunk, _cosine_similarity(query_vector, chunk.dense_embedding or []))
                for chunk in chunks
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        lexical_ranked = sorted(
            (
                (chunk, _lexical_score(query, chunk.search_text, chunk.symbol_name, chunk.qualified_name))
                for chunk in chunks
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if method == "dense":
            ordered = dense_ranked
        elif method == "lexical":
            ordered = lexical_ranked
        else:
            ordered_map: dict[uuid.UUID, float] = {}
            for rank, (chunk, _) in enumerate(dense_ranked, start=1):
                ordered_map[chunk.id] = ordered_map.get(chunk.id, 0.0) + 1.0 / (60 + rank)
            for rank, (chunk, _) in enumerate(lexical_ranked, start=1):
                ordered_map[chunk.id] = ordered_map.get(chunk.id, 0.0) + 1.0 / (60 + rank)
            ordered = sorted(
                ((chunk, ordered_map[chunk.id]) for chunk in chunks if chunk.id in ordered_map),
                key=lambda item: item[1],
                reverse=True,
            )
        evidence: list[SearchEvidence] = []
        seen_paths: set[str] = set()
        for chunk, score in ordered:
            if chunk.normalized_path in seen_paths:
                continue
            seen_paths.add(chunk.normalized_path)
            evidence.append(
                SearchEvidence(
                    path=chunk.normalized_path,
                    language=chunk.language,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    symbol=chunk.symbol_name,
                    score=float(score),
                    retrieval_method=method,
                    exact_content=chunk.exact_content,
                    revision_id=str(chunk.revision_id),
                    commit_sha=chunk.commit_sha,
                    symbol_type=chunk.symbol_type,
                    qualified_name=chunk.qualified_name,
                    chunk_id=str(chunk.id),
                )
            )
            if len(evidence) >= limit:
                break
        return evidence

    async def cleanup_repository(self, repository_id: uuid.UUID) -> None:
        await self.chunks.delete_for_repository(repository_id)
        revision_ids = select(RepositoryRevision.id).where(
            RepositoryRevision.repository_id == repository_id
        )
        file_ids = select(RepositoryFile.id).where(RepositoryFile.revision_id.in_(revision_ids))
        await self.session.execute(delete(CodeSymbol).where(CodeSymbol.file_id.in_(file_ids)))
        await self.session.execute(
            delete(RepositoryIndexSnapshot).where(RepositoryIndexSnapshot.repository_id == repository_id)
        )

    async def _add_event(self, run_id: uuid.UUID, event_type: str, message: str) -> None:
        sequence = await self.events.next_sequence(run_id)
        await self.events.add(
            AgentRunEvent(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                public_message=message,
                private_metadata={},
            )
        )


def _materialize_file(
    *,
    snapshot_id: uuid.UUID,
    owner_id: uuid.UUID,
    repository_id: uuid.UUID,
    revision_id: uuid.UUID,
    commit_sha: str,
    file: RepositoryFile,
    parsed: ParsedFile,
    settings: Settings,
) -> tuple[list[CodeSymbol], list[IndexedChunkDraft]]:
    text = file.content or ""
    lines = text.splitlines()
    symbols: list[CodeSymbol] = []
    chunks: list[IndexedChunkDraft] = []
    for symbol in parsed.symbols:
        code_symbol = CodeSymbol(
            file_id=file.id,
            symbol_type=symbol.symbol_type,
            name=symbol.name,
            qualified_name=symbol.qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            signature=symbol.signature,
            parent_symbol_id=None,
            symbol_metadata={
                **symbol.metadata,
                "docstring": symbol.docstring,
                "calls": list(symbol.calls),
                "references": list(symbol.references),
                "imports": list(parsed.imports),
                "module_name": parsed.module_name,
                "package_name": parsed.package_name,
                "parent_qualified_name": symbol.parent_qualified_name,
            },
        )
        symbols.append(code_symbol)

        source_text = _line_slice(text, symbol.start_line, symbol.end_line)
        if not source_text.strip():
            source_text = text
        parts = _split_chunk_text(
            source_text,
            max_chars=settings.indexing_chunk_max_chars,
            max_lines=settings.indexing_chunk_max_lines,
            overlap_lines=settings.indexing_chunk_overlap_lines,
        )
        part_count = len(parts)
        for index, (part_text, part_start, part_end) in enumerate(parts, start=1):
            content_hash = hashlib.sha256(part_text.encode("utf-8")).hexdigest()
            search_text = "\n".join(
                filter(
                    None,
                    [
                        file.normalized_path,
                        symbol.qualified_name,
                        symbol.signature,
                        symbol.docstring,
                        " ".join(parsed.imports),
                        part_text,
                    ],
                )
            )
            chunk_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                "|".join(
                    [
                        str(revision_id),
                        file.normalized_path,
                        content_hash,
                        str(part_start),
                        str(part_end),
                        str(index),
                    ]
                ),
            )
            chunks.append(
                IndexedChunkDraft(
                    chunk_id=chunk_id,
                    snapshot_id=snapshot_id,
                    owner_id=owner_id,
                    repository_id=repository_id,
                    revision_id=revision_id,
                    file_id=file.id,
                    commit_sha=commit_sha,
                    normalized_path=file.normalized_path,
                    language=file.language,
                    symbol_name=symbol.name,
                    qualified_name=symbol.qualified_name,
                    symbol_type=symbol.symbol_type,
                    start_line=part_start,
                    end_line=part_end,
                    part_number=index,
                    part_count=part_count,
                    content_hash=content_hash,
                    exact_content=part_text,
                    search_text=search_text,
                    dense_embedding=None,
                    chunk_metadata={
                        "docstring": symbol.docstring,
                        "calls": list(symbol.calls),
                        "references": list(symbol.references),
                        "fallback": parsed.fallback_used,
                        "module_name": parsed.module_name,
                        "package_name": parsed.package_name,
                    },
                )
            )
    if not symbols:
        part_text = text or ""
        content_hash = hashlib.sha256(part_text.encode("utf-8")).hexdigest()
        chunk_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "|".join([str(revision_id), file.normalized_path, content_hash, "1", "1", "1"]),
        )
        chunks.append(
            IndexedChunkDraft(
                chunk_id=chunk_id,
                snapshot_id=snapshot_id,
                owner_id=owner_id,
                repository_id=repository_id,
                revision_id=revision_id,
                file_id=file.id,
                commit_sha=commit_sha,
                normalized_path=file.normalized_path,
                language=file.language,
                symbol_name=None,
                qualified_name=None,
                symbol_type="text_chunk",
                start_line=1,
                end_line=max(len(lines), 1),
                part_number=1,
                part_count=1,
                content_hash=content_hash,
                exact_content=part_text,
                search_text="\n".join(filter(None, [file.normalized_path, parsed.module_name, part_text])),
                dense_embedding=None,
                chunk_metadata={"fallback": True, "module_name": parsed.module_name},
            )
        )
    return symbols, chunks


def _apply_symbol_parent_links(symbols: list[CodeSymbol]) -> None:
    by_qualified = {symbol.qualified_name: symbol for symbol in symbols}
    for symbol in symbols:
        parent_name = symbol.symbol_metadata.get("parent_qualified_name")
        if isinstance(parent_name, str) and parent_name in by_qualified:
            symbol.parent_symbol_id = by_qualified[parent_name].id


def _split_chunk_text(
    text: str,
    *,
    max_chars: int,
    max_lines: int,
    overlap_lines: int,
) -> list[tuple[str, int, int]]:
    lines = text.splitlines() or [text]
    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        part_lines = lines[start:end]
        part_text = "\n".join(part_lines)
        if len(part_text) > max_chars and len(part_lines) > 1:
            end = start + max(1, len(part_lines) // 2)
            part_lines = lines[start:end]
            part_text = "\n".join(part_lines)
        chunks.append((part_text, start + 1, end))
        if end >= len(lines):
            break
        start = max(end - overlap_lines, start + 1)
    return chunks


def _batch_texts(texts: list[str], batch_size: int) -> list[list[str]]:
    return [texts[index : index + batch_size] for index in range(0, len(texts), batch_size)]


def _embedding_key(chunk: CodeChunk) -> str:
    return _chunk_key_parts(
        chunk.normalized_path,
        chunk.content_hash,
        chunk.start_line,
        chunk.end_line,
        chunk.part_number,
        chunk.part_count,
        chunk.symbol_type,
        chunk.qualified_name,
    )


def _embedding_key_from_draft(chunk: IndexedChunkDraft) -> str:
    return _chunk_key_parts(
        chunk.normalized_path,
        chunk.content_hash,
        chunk.start_line,
        chunk.end_line,
        chunk.part_number,
        chunk.part_count,
        chunk.symbol_type,
        chunk.qualified_name,
    )


def _chunk_key_parts(
    path: str,
    content_hash: str,
    start_line: int,
    end_line: int,
    part_number: int,
    part_count: int,
    symbol_type: str,
    qualified_name: str | None,
) -> str:
    return "|".join(
        [
            path,
            content_hash,
            str(start_line),
            str(end_line),
            str(part_number),
            str(part_count),
            symbol_type,
            qualified_name or "",
        ]
    )


def _lexical_score(query: str, content: str, symbol_name: str | None, qualified_name: str | None) -> float:
    query_tokens = Counter(_tokenize(query))
    content_tokens = Counter(_tokenize(" ".join(filter(None, [symbol_name, qualified_name, content]))))
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = sum(min(query_tokens[token], content_tokens[token]) for token in query_tokens)
    return float(overlap) / max(sum(query_tokens.values()), 1)


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
    numerator = sum(left * right for left, right in zip(vector_a, vector_b))
    magnitude_a = math.sqrt(sum(value * value for value in vector_a))
    magnitude_b = math.sqrt(sum(value * value for value in vector_b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return numerator / (magnitude_a * magnitude_b)


def _tokenize(text: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", text)]


def _line_slice(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    start_index = max(start_line - 1, 0)
    end_index = min(end_line, len(lines))
    return "\n".join(lines[start_index:end_index])
