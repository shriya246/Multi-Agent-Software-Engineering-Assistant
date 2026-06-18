from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import reset_settings_cache


@pytest.mark.integration
def test_alembic_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "alembic.db"
    monkeypatch.setenv("CODEPILOT_DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    reset_settings_cache()

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        tables = inspect(engine).get_table_names()
        assert "system_metadata" in tables
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        tables = inspect(engine).get_table_names()
        assert "system_metadata" not in tables
    finally:
        engine.dispose()
