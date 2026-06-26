from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    role: str
    expires_at: datetime


def create_access_token(user_id: UUID, role: str, settings: Settings) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.access_token_algorithm)
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.access_token_algorithm],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
        if payload.get("type") != "access":
            return None
        return AccessTokenClaims(
            user_id=UUID(str(payload["sub"])),
            role=str(payload.get("role", "user")),
            expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=UTC),
        )
    except (InvalidTokenError, ValueError, TypeError):
        return None


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def hash_metadata(value: str, secret_key: str) -> bytes:
    return hashlib.sha256(f"{secret_key}:{value}".encode()).digest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
