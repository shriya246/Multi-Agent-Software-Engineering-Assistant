from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import Conflict, InvalidState, NotFound
from app.models.domain import (
    AgentRun,
    AgentRunEvent,
    AuditLog,
    Repository,
    RepositoryRevision,
)
from app.repositories.domain import (
    AgentRunEventRepository,
    AgentRunRepository,
    AuditLogRepository,
    RepositoryFileRepository,
    RepositoryRepository,
    RepositoryRevisionRepository,
)
from app.security.tokens import hash_metadata

RepositoryState = Literal[
    "queued",
    "cloning",
    "scanning",
    "ready_for_indexing",
    "indexing",
    "ready",
    "failed",
    "deleting",
    "deleted",
]

RUN_TYPE_INGESTION = "repository_ingestion"
RUN_STATUS_ACTIVE = {"queued", "running"}
REVISION_TERMINAL_STATES = {"ready_for_indexing", "ready", "failed", "deleted"}
ALLOWED_STATE_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"cloning", "failed", "deleting"},
    "cloning": {"scanning", "failed", "deleting"},
    "scanning": {"ready_for_indexing", "failed", "deleting"},
    "ready_for_indexing": {"indexing", "ready", "deleting"},
    "indexing": {"ready", "failed", "deleting"},
    "ready": {"queued", "indexing", "deleting"},
    "failed": {"queued", "deleting"},
    "deleting": {"deleted", "failed"},
    "deleted": set(),
}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    "target",
}
MEDIA_EXTENSIONS = {
    ".7z",
    ".a",
    ".avi",
    ".bmp",
    ".bz2",
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".onnx",
    ".otf",
    ".pdf",
    ".png",
    ".pt",
    ".pyc",
    ".rar",
    ".so",
    ".tar",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}
SECRET_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".netrc",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "credentials.json",
    "secrets.json",
}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
LANGUAGE_BY_EXTENSION = {
    ".c": "C",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".md": "Markdown",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".swift": "Swift",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".yaml": "YAML",
    ".yml": "YAML",
}


@dataclass(frozen=True, slots=True)
class NormalizedRepositoryUrl:
    owner: str
    name: str
    clone_url: str


@dataclass(frozen=True, slots=True)
class CloneCommand:
    command: list[str]
    cwd: Path | None = None


@dataclass(frozen=True, slots=True)
class CloneResult:
    commit_sha: str
    workspace: Path
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class ScannedFile:
    normalized_path: str
    language: str | None
    size: int
    content_hash: str
    line_count: int
    indexing_status: str
    excluded_reason: str | None
    content: str | None


@dataclass(frozen=True, slots=True)
class ScanResult:
    files: list[ScannedFile]
    accepted_file_count: int
    total_bytes: int


class IngestionInputError(ValueError):
    pass


class CloneFailureError(RuntimeError):
    def __init__(self, code: str, summary: str) -> None:
        super().__init__(summary)
        self.code = code
        self.summary = summary


def validate_github_url(raw_url: str) -> NormalizedRepositoryUrl:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme != "https":
        raise IngestionInputError("Only public GitHub HTTPS repository URLs are supported")
    if parsed.hostname != "github.com":
        raise IngestionInputError("Only github.com repository URLs are supported")
    if parsed.port is not None:
        raise IngestionInputError("GitHub repository URLs must not include a port")
    if parsed.username or parsed.password:
        raise IngestionInputError("Repository URLs must not include credentials")
    if parsed.query or parsed.fragment:
        raise IngestionInputError("Repository URLs must not include query strings or fragments")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise IngestionInputError("Repository URL must look like https://github.com/owner/repo")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _safe_github_component(owner) or not _safe_github_component(repo):
        raise IngestionInputError("Repository owner or name contains unsupported characters")
    return NormalizedRepositoryUrl(
        owner=owner,
        name=repo,
        clone_url=f"https://github.com/{owner}/{repo}",
    )


def validate_git_ref(ref: str | None) -> str | None:
    if ref is None:
        return None
    cleaned = ref.strip()
    if not cleaned:
        return None
    if len(cleaned) > 255 or cleaned.startswith("-"):
        raise IngestionInputError("Git ref is not supported")
    blocked = ["\x00", "\\", "..", "@{", "//", " ", "~", "^", ":", "?", "*", "["]
    if any(item in cleaned for item in blocked):
        raise IngestionInputError("Git ref is not supported")
    if any(ord(char) < 32 or ord(char) == 127 for char in cleaned):
        raise IngestionInputError("Git ref is not supported")
    if cleaned.endswith("/") or cleaned.endswith(".") or cleaned.endswith(".lock"):
        raise IngestionInputError("Git ref is not supported")
    if any(part in {"", ".", ".."} or part.endswith(".lock") for part in cleaned.split("/")):
        raise IngestionInputError("Git ref is not supported")
    return cleaned


def build_clone_commands(url: str, ref: str | None, destination: Path) -> list[CloneCommand]:
    base = [
        "git",
        "clone",
        "--depth",
        "1",
        "--no-tags",
        "--single-branch",
        "--config",
        "credential.helper=",
    ]
    if ref and not _looks_like_commit_sha(ref):
        base.extend(["--branch", ref])
    base.extend(["--", url, str(destination)])
    commands = [CloneCommand(base)]
    if ref and _looks_like_commit_sha(ref):
        commands.extend(
            [
                CloneCommand(["git", "fetch", "--depth", "1", "origin", ref], cwd=destination),
                CloneCommand(["git", "checkout", "--detach", ref], cwd=destination),
            ]
        )
    return commands


def clone_repository(
    url: str,
    ref: str | None,
    workspace_parent: Path,
    settings: Settings,
) -> CloneResult:
    workspace_parent.mkdir(parents=True, exist_ok=True)
    workspace = workspace_parent / f"repo-{uuid4().hex}"
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    try:
        for command in build_clone_commands(url, ref, workspace):
            completed = subprocess.run(
                command.command,
                cwd=str(command.cwd) if command.cwd else None,
                env=_git_env(),
                capture_output=True,
                text=True,
                timeout=settings.ingestion_clone_timeout_seconds,
                shell=False,
                check=False,
            )
            stdout_parts.append(
                _bound_output(completed.stdout, settings.ingestion_process_output_bytes)
            )
            stderr_parts.append(
                _bound_output(completed.stderr, settings.ingestion_process_output_bytes)
            )
            if completed.returncode != 0:
                raise CloneFailureError("clone_failed", "Repository could not be cloned")
        commit_sha = _resolve_commit_sha(workspace, settings)
        return CloneResult(
            commit_sha=commit_sha,
            workspace=workspace,
            stdout="\n".join(stdout_parts),
            stderr="\n".join(stderr_parts),
        )
    except subprocess.TimeoutExpired as exc:
        _safe_rmtree(workspace)
        raise CloneFailureError("clone_timeout", "Repository clone timed out") from exc
    except CloneFailureError:
        _safe_rmtree(workspace)
        raise
    except OSError as exc:
        _safe_rmtree(workspace)
        raise CloneFailureError("git_unavailable", "Git is not available") from exc


def scan_repository(root: Path, settings: Settings) -> ScanResult:
    root = root.resolve()
    ignore_patterns = _load_codepilotignore(root)
    files: list[ScannedFile] = []
    accepted_count = 0
    total_bytes = 0
    total_files = 0
    symlinks = 0

    for current_root, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current_root)
        _assert_inside(root, current_path)
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in EXCLUDED_DIRS
            and not _ignored_by_codepilotignore(
                _relative_posix(root, current_path / directory), ignore_patterns
            )
        ]
        for filename in filenames:
            path = current_path / filename
            relative = _relative_posix(root, path)
            if len(relative) > settings.ingestion_max_path_length:
                raise CloneFailureError(
                    "path_too_long", "Repository contains a path that exceeds limits"
                )
            if len(Path(relative).parts) > settings.ingestion_max_nesting_depth:
                raise CloneFailureError(
                    "path_too_deep", "Repository contains a path nested too deeply"
                )
            _assert_inside(root, path)
            total_files += 1
            if total_files > settings.ingestion_max_files:
                raise CloneFailureError("file_count_limit", "Repository contains too many files")

            try:
                stat = path.lstat()
            except OSError:
                files.append(_excluded(relative, "unreadable"))
                continue
            size = stat.st_size
            total_bytes += size
            if total_bytes > settings.ingestion_max_total_bytes:
                raise CloneFailureError("repository_too_large", "Repository exceeds size limits")

            reason = _exclusion_reason(path, relative, settings, ignore_patterns)
            if path.is_symlink():
                symlinks += 1
                if symlinks > settings.ingestion_max_symlinks:
                    raise CloneFailureError(
                        "symlink_limit", "Repository contains too many symlinks"
                    )
                reason = "symlink"
            if reason:
                files.append(_excluded(relative, reason, size=size))
                continue
            accepted = _scan_file(path, relative, settings)
            files.append(accepted)
            accepted_count += 1

    return ScanResult(files=files, accepted_file_count=accepted_count, total_bytes=total_bytes)


class IngestionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repositories = RepositoryRepository(session)
        self.revisions = RepositoryRevisionRepository(session)
        self.files = RepositoryFileRepository(session)
        self.runs = AgentRunRepository(session)
        self.events = AgentRunEventRepository(session)
        self.audit_logs = AuditLogRepository(session)

    async def create_repository(
        self,
        owner_id: UUID,
        raw_url: str,
        ref: str | None,
        correlation_id: str,
        ip: str,
    ) -> tuple[Repository, AgentRun | None]:
        normalized = validate_github_url(raw_url)
        safe_ref = validate_git_ref(ref)
        existing = await self.repositories.by_owner_url(owner_id, normalized.clone_url)
        if existing:
            active_run = await self.runs.active_for_repository(
                existing.id, run_type=RUN_TYPE_INGESTION
            )
            if active_run:
                return existing, None
            if existing.status != "deleted":
                return existing, None

        repository = Repository(
            owner_id=owner_id,
            name=normalized.name,
            normalized_clone_url=normalized.clone_url,
            default_branch=None,
            status="queued",
            indexing_config={"requested_ref": safe_ref},
        )
        self.session.add(repository)
        await self.session.flush()
        run = await self._create_run(owner_id, repository, safe_ref)
        await self.audit(
            "repository.create", "success", correlation_id, ip, owner_id, repository.id
        )
        return repository, run

    async def sync_repository(
        self,
        owner_id: UUID,
        repository_id: UUID,
        ref: str | None,
        correlation_id: str,
        ip: str,
    ) -> tuple[Repository, AgentRun]:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        if await self.runs.active_for_repository(repository.id, run_type=RUN_TYPE_INGESTION):
            raise Conflict("Repository ingestion is already running")
        safe_ref = validate_git_ref(ref) or repository.indexing_config.get("requested_ref")
        await self.transition(repository, "queued")
        repository.indexing_config = {**repository.indexing_config, "requested_ref": safe_ref}
        run = await self._create_run(owner_id, repository, str(safe_ref) if safe_ref else None)
        await self.audit("repository.sync", "success", correlation_id, ip, owner_id, repository.id)
        return repository, run

    async def mark_deleting(
        self,
        owner_id: UUID,
        repository_id: UUID,
        correlation_id: str,
        ip: str,
    ) -> Repository:
        repository = await self.repositories.owned_by_id(owner_id, repository_id)
        if repository is None:
            raise NotFound()
        await self.transition(repository, "deleting")
        repository.deleted_at = datetime.now(UTC)
        repository.deleted_by_id = owner_id
        await self.audit(
            "repository.delete", "success", correlation_id, ip, owner_id, repository.id
        )
        return repository

    async def transition(self, repository: Repository, target: RepositoryState) -> None:
        if target not in ALLOWED_STATE_TRANSITIONS.get(repository.status, set()):
            raise InvalidState(f"Cannot transition repository from {repository.status} to {target}")
        repository.status = target

    async def ingest(self, repository_id: UUID, run_id: UUID) -> None:
        repository = await self.session.get(Repository, repository_id)
        run = await self.session.get(AgentRun, run_id)
        if repository is None or run is None:
            raise NotFound()
        requested_ref = repository.indexing_config.get("requested_ref")
        ref = str(requested_ref) if requested_ref else None
        now = datetime.now(UTC)
        run.status = "running"
        run.started_at = now
        await self.add_event(run.id, "started", "Repository ingestion started")
        await self.transition(repository, "cloning")
        await self.session.flush()

        workspace_parent = Path(self.settings.ingestion_workspace_root)
        workspace: Path | None = None
        revision: RepositoryRevision | None = None
        try:
            clone = clone_repository(
                repository.normalized_clone_url, ref, workspace_parent, self.settings
            )
            workspace = clone.workspace
            await self.transition(repository, "scanning")
            revision = await self._upsert_revision(repository, clone.commit_sha, ref)
            revision.cloned_at = datetime.now(UTC)
            revision.status = "scanning"
            await self.add_event(run.id, "cloned", "Repository clone completed")
            scan = scan_repository(workspace, self.settings)
            await self.files.replace_for_revision(revision.id, scan.files)
            revision.status = "ready_for_indexing"
            revision.indexed_at = datetime.now(UTC)
            revision.file_count = scan.accepted_file_count
            revision.total_bytes = scan.total_bytes
            revision.error_code = None
            revision.error_summary = None
            repository.latest_revision_id = revision.id
            await self.transition(repository, "ready_for_indexing")
            run.revision_id = revision.id
            run.status = "succeeded"
            run.completed_at = datetime.now(UTC)
            run.input_units = scan.accepted_file_count
            run.output_units = scan.total_bytes
            await self.add_event(run.id, "completed", "Repository is ready for indexing")
        except CloneFailureError as exc:
            await self._fail(repository, run, revision, exc.code, exc.summary)
        finally:
            if workspace is not None:
                _safe_rmtree(workspace)

    async def delete_workspace_and_mark_deleted(self, repository_id: UUID) -> None:
        repository = await self.session.get(Repository, repository_id)
        if repository is None:
            return
        if repository.status == "deleting":
            repository.status = "deleted"
            repository.deleted_at = repository.deleted_at or datetime.now(UTC)

    async def add_event(self, run_id: UUID, event_type: str, message: str) -> AgentRunEvent:
        sequence = await self.events.next_sequence(run_id)
        return await self.events.add(
            AgentRunEvent(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                public_message=message,
                private_metadata={},
            )
        )

    async def audit(
        self,
        action: str,
        result: str,
        correlation_id: str,
        ip: str,
        actor: UUID,
        resource_id: UUID,
    ) -> None:
        await self.audit_logs.add(
            AuditLog(
                actor_user_id=actor,
                action=action,
                resource_type="repository",
                resource_id=resource_id,
                result=result,
                correlation_id=correlation_id[:128],
                ip_hash=hash_metadata(ip, self.settings.secret_key),
                details={},
            )
        )

    async def _create_run(
        self, owner_id: UUID, repository: Repository, ref: str | None
    ) -> AgentRun:
        run = AgentRun(
            owner_id=owner_id,
            repository_id=repository.id,
            revision_id=None,
            run_type=RUN_TYPE_INGESTION,
            status="queued",
            input_summary=f"Ingest {repository.normalized_clone_url}",
            model_provider="local",
            model_identifier="none",
            prompt_version="phase-4-ingestion",
            cancellation_metadata=None,
            error_code=None,
            error_message=None,
            input_units=None,
            output_units=None,
        )
        run.cancellation_metadata = {"requested_ref": ref} if ref else {}
        self.session.add(run)
        await self.session.flush()
        await self.add_event(run.id, "queued", "Repository ingestion queued")
        return run

    async def _upsert_revision(
        self, repository: Repository, commit_sha: str, ref: str | None
    ) -> RepositoryRevision:
        existing = await self.revisions.by_repository_commit(repository.id, commit_sha)
        if existing:
            return existing
        revision = RepositoryRevision(
            repository_id=repository.id,
            commit_sha=commit_sha,
            ref=ref,
            status="cloning",
            file_count=0,
            total_bytes=0,
        )
        self.session.add(revision)
        await self.session.flush()
        return revision

    async def _fail(
        self,
        repository: Repository,
        run: AgentRun,
        revision: RepositoryRevision | None,
        code: str,
        summary: str,
    ) -> None:
        repository.status = "failed"
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.error_code = code
        run.error_message = summary
        if revision:
            revision.status = "failed"
            revision.error_code = code
            revision.error_summary = summary
        await self.add_event(run.id, "failed", summary)


def _safe_github_component(value: str) -> bool:
    if not value or value.startswith(".") or value.endswith("."):
        return False
    return all(char.isalnum() or char in {"-", "_", "."} for char in value)


def _looks_like_commit_sha(ref: str) -> bool:
    return 7 <= len(ref) <= 64 and all(char in "0123456789abcdefABCDEF" for char in ref)


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "echo",
            "GCM_INTERACTIVE": "Never",
        }
    )
    return env


def _resolve_commit_sha(workspace: Path, settings: Settings) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(workspace),
        env=_git_env(),
        capture_output=True,
        text=True,
        timeout=settings.ingestion_clone_timeout_seconds,
        shell=False,
        check=False,
    )
    if completed.returncode != 0:
        raise CloneFailureError(
            "commit_resolution_failed", "Repository revision could not be resolved"
        )
    commit = completed.stdout.strip()
    if len(commit) != 40 or not _looks_like_commit_sha(commit):
        raise CloneFailureError(
            "commit_resolution_failed", "Repository revision could not be resolved"
        )
    return commit.lower()


def _bound_output(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8", errors="replace")[:max_bytes]
    return encoded.decode("utf-8", errors="replace")


def _safe_rmtree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return


def _assert_inside(root: Path, path: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise CloneFailureError("path_escape", "Repository contains an unsafe path") from exc


def _relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _load_codepilotignore(root: Path) -> list[str]:
    ignore_file = root / ".codepilotignore"
    try:
        lines = ignore_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    patterns: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            patterns.append(stripped)
    return patterns


def _ignored_by_codepilotignore(relative: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(Path(relative).name, pattern)
        for pattern in patterns
    )


def _exclusion_reason(
    path: Path,
    relative: str,
    settings: Settings,
    ignore_patterns: list[str],
) -> str | None:
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if _ignored_by_codepilotignore(relative, ignore_patterns):
        return "codepilotignore"
    if name in SECRET_FILENAMES or suffix in SECRET_SUFFIXES:
        return "secret_like"
    if suffix in MEDIA_EXTENSIONS:
        return "binary_extension"
    try:
        size = path.stat().st_size
    except OSError:
        return "unreadable"
    if size > settings.ingestion_max_file_bytes:
        return "file_too_large"
    return None


def _scan_file(path: Path, relative: str, settings: Settings) -> ScannedFile:
    try:
        data = path.read_bytes()
    except OSError:
        return _excluded(relative, "unreadable")
    if _is_binary(data):
        return _excluded(relative, "binary", size=len(data))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _excluded(relative, "invalid_encoding", size=len(data))
    line_count = len(text.splitlines())
    if line_count > settings.ingestion_max_text_lines:
        return _excluded(relative, "too_many_lines", size=len(data))
    return ScannedFile(
        normalized_path=relative,
        language=_detect_language(path),
        size=len(data),
        content_hash=hashlib.sha256(data).hexdigest(),
        line_count=line_count,
        indexing_status="accepted",
        excluded_reason=None,
        content=text,
    )


def _excluded(relative: str, reason: str, *, size: int = 0) -> ScannedFile:
    return ScannedFile(
        normalized_path=relative,
        language=_detect_language(Path(relative)),
        size=size,
        content_hash=hashlib.sha256(b"").hexdigest(),
        line_count=0,
        indexing_status="excluded",
        excluded_reason=reason,
        content=None,
    )


def _is_binary(data: bytes) -> bool:
    sample = data[:4096]
    return b"\x00" in sample


def _detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_EXTENSION.get(path.suffix.casefold())
