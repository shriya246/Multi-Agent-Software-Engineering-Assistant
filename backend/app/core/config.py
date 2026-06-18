from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CODEPILOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CodePilot"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    secret_key: str = "development-only-secret"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    database_url: str = "postgresql+asyncpg://codepilot:codepilot@postgres:5432/codepilot"
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "qwen2.5-coder:3b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_model_required: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("cors_origins must be a string or list of strings")

    def validate_production_requirements(self) -> None:
        if self.environment != "production":
            return
        required = {
            "secret_key": self.secret_key,
            "database_url": self.database_url,
            "redis_url": self.redis_url,
            "qdrant_url": self.qdrant_url,
            "ollama_base_url": self.ollama_base_url,
        }
        missing = [
            name for name, value in required.items() if not value or value.startswith("change-me")
        ]
        if missing:
            joined = ", ".join(sorted(missing))
            raise RuntimeError(f"Missing production settings: {joined}")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            CommaSeparatedEnvSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )


class CommaSeparatedEnvSettingsSource(EnvSettingsSource):
    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: object,
        value_is_complex: bool,
    ) -> object:
        if field_name == "cors_origins" and isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_requirements()
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()


def build_settings_from_env(**overrides: str) -> Settings:
    values = {
        "CODEPILOT_APP_NAME": "CodePilot",
        "CODEPILOT_APP_VERSION": "0.1.0",
        **{f"CODEPILOT_{key.upper()}": value for key, value in overrides.items()},
    }
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        return Settings()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def settings_from_payload(payload: dict[str, object]) -> Settings:
    try:
        return Settings.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - thin wrapper
        raise exc
