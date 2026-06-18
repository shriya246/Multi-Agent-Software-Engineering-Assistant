from __future__ import annotations

import pytest

from app.core.config import Settings


def test_production_settings_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEPILOT_ENVIRONMENT", "production")
    monkeypatch.setenv("CODEPILOT_SECRET_KEY", "change-me")
    monkeypatch.setenv("CODEPILOT_DATABASE_URL", "change-me")
    monkeypatch.setenv("CODEPILOT_REDIS_URL", "change-me")
    monkeypatch.setenv("CODEPILOT_QDRANT_URL", "change-me")
    monkeypatch.setenv("CODEPILOT_OLLAMA_BASE_URL", "change-me")
    settings = Settings()
    with pytest.raises(RuntimeError, match="Missing production settings"):
        settings.validate_production_requirements()


def test_settings_parse_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEPILOT_CORS_ORIGINS", "http://localhost:5173, https://example.com")
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:5173", "https://example.com"]
