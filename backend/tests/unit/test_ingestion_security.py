from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import InvalidState
from app.models.domain import Repository
from app.services.ingestion import (
    CloneFailureError,
    IngestionInputError,
    IngestionService,
    build_clone_commands,
    scan_repository,
    validate_git_ref,
    validate_github_url,
)


def test_github_url_normalization_accepts_https_repo() -> None:
    normalized = validate_github_url("https://github.com/Owner/repo.git")
    assert normalized.clone_url == "https://github.com/Owner/repo"
    assert normalized.owner == "Owner"
    assert normalized.name == "repo"


@pytest.mark.parametrize(
    "url",
    [
        "ssh://github.com/owner/repo",
        "git://github.com/owner/repo",
        "file:///tmp/repo",
        "https://user:pass@github.com/owner/repo",
        "https://github.com:444/owner/repo",
        "https://example.com/owner/repo",
        "C:/repo",
    ],
)
def test_github_url_rejects_unsafe_inputs(url: str) -> None:
    with pytest.raises(IngestionInputError):
        validate_github_url(url)


@pytest.mark.parametrize("ref", ["-main", "feature..bad", "bad ref", "main.lock", "bad\x00ref"])
def test_git_ref_rejects_unsafe_inputs(ref: str) -> None:
    with pytest.raises(IngestionInputError):
        validate_git_ref(ref)


def test_clone_command_uses_argument_list_and_no_shell() -> None:
    destination = Path("workspace/repo")
    commands = build_clone_commands("https://github.com/owner/repo", "main", destination)
    assert commands[0].command[:6] == [
        "git",
        "clone",
        "--depth",
        "1",
        "--no-tags",
        "--single-branch",
    ]
    assert "--" in commands[0].command
    assert "https://github.com/owner/repo" in commands[0].command
    assert not any(isinstance(command.command, str) for command in commands)


def test_scanner_excludes_binary_secret_and_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "image.png").write_bytes(b"\x89PNG\x00")
    (repo / ".env").write_text("SECRET=value", encoding="utf-8")
    (repo / "outside.txt").write_text("outside", encoding="utf-8")
    try:
        (repo / "link").symlink_to(tmp_path / "outside.txt")
    except OSError:
        pass

    result = scan_repository(repo, Settings())
    by_path = {item.normalized_path: item for item in result.files}
    assert by_path["src.py"].indexing_status == "accepted"
    assert by_path["image.png"].excluded_reason == "binary_extension"
    assert by_path[".env"].excluded_reason == "secret_like"
    if "link" in by_path:
        assert by_path["link"].excluded_reason == "symlink"


def test_scanner_enforces_file_count_limit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("a", encoding="utf-8")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    with pytest.raises(CloneFailureError, match="too many files"):
        scan_repository(repo, Settings(ingestion_max_files=1))


@pytest.mark.asyncio
async def test_state_transition_enforcement() -> None:
    repository = Repository(
        owner_id=uuid4(),
        name="repo",
        normalized_clone_url="https://github.com/owner/repo",
        status="queued",
        indexing_config={},
    )
    service = IngestionService(None, Settings())  # type: ignore[arg-type]
    await service.transition(repository, "cloning")
    with pytest.raises(InvalidState):
        await service.transition(repository, "ready")
