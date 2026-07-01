from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
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
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "api", "frontend"]
    )
    max_request_size_bytes: int = 1_048_576
    database_url: str = "postgresql+asyncpg://codepilot:codepilot@postgres:5432/codepilot"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    database_connect_timeout_seconds: int = 5
    database_statement_timeout_ms: int = 10_000
    database_health_timeout_seconds: float = 2.0
    redis_url: str = "redis://redis:6379/0"
    redis_socket_connect_timeout_seconds: float = 2.0
    redis_socket_timeout_seconds: float = 2.0
    redis_health_timeout_seconds: float = 2.0
    redis_health_check_interval_seconds: int = 30
    qdrant_url: str = "http://qdrant:6333"
    qdrant_health_timeout_seconds: float = 2.0
    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "qwen2.5-coder:3b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_health_timeout_seconds: float = 2.0
    ollama_model_required: bool = False
    celery_task_time_limit_seconds: int = 600
    celery_task_soft_time_limit_seconds: int = 540
    celery_result_expires_seconds: int = 3600
    celery_worker_prefetch_multiplier: int = 1
    idempotency_ttl_seconds: int = 86_400
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    access_token_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    refresh_cookie_name: str = "codepilot_refresh"
    csrf_cookie_name: str = "codepilot_csrf"
    cookie_secure: bool = False
    auth_rate_limit_window_seconds: int = 60
    registration_rate_limit: int = 5
    login_rate_limit: int = 10
    refresh_rate_limit: int = 30
    password_verify_rate_limit: int = 20
    authenticated_api_rate_limit: int = 300
    auth_rate_limit_fail_closed: bool = True
    ingestion_workspace_root: str = "./.codepilot-workspaces"
    ingestion_clone_timeout_seconds: int = 120
    ingestion_process_output_bytes: int = 4096
    ingestion_max_total_bytes: int = 100_000_000
    ingestion_max_files: int = 25_000
    ingestion_max_file_bytes: int = 1_000_000
    ingestion_max_path_length: int = 512
    ingestion_max_nesting_depth: int = 32
    ingestion_max_text_lines: int = 20_000
    ingestion_max_symlinks: int = 100
    ingestion_failed_workspace_ttl_seconds: int = 86_400

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_string_lists(cls, value: object) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("expected a comma-separated string or a list of strings")

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
        if not self.trusted_hosts:
            raise RuntimeError("Missing production settings: trusted_hosts")
        if self.secret_key == "development-only-secret" or len(self.secret_key) < 32:
            raise RuntimeError("CODEPILOT_SECRET_KEY must be a strong production secret")

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
        if field_name in {"cors_origins", "trusted_hosts"} and isinstance(value, str):
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
    return Settings.model_validate(payload)
