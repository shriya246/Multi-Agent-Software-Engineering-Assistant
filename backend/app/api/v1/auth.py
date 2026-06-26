from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_container, get_current_user, get_rate_limit_service
from app.core.container import AppContainer
from app.core.exceptions import AppError, Conflict, Unauthorized
from app.core.middleware import get_correlation_id
from app.db.session import get_session
from app.models.domain import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    SessionResponse,
    UserResponse,
)
from app.security.tokens import generate_csrf_token, hash_metadata
from app.services.auth import AuthResult, AuthService
from app.services.rate_limit import RateLimitService

router = APIRouter(prefix="/auth", tags=["authentication"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "unknown")[:1000]


def _rate_identity(request: Request, container: AppContainer) -> str:
    return hash_metadata(_client_ip(request), container.settings.secret_key).hex()


def _set_session_cookies(response: Response, result: AuthResult, container: AppContainer) -> None:
    settings = container.settings
    response.set_cookie(
        settings.refresh_cookie_name,
        result.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/api/v1/auth",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        generate_csrf_token(),
        max_age=settings.refresh_token_ttl_seconds,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response, container: AppContainer) -> None:
    settings = container.settings
    response.delete_cookie(
        settings.refresh_cookie_name,
        path="/api/v1/auth",
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.delete_cookie(
        settings.csrf_cookie_name, path="/", secure=settings.cookie_secure, samesite="lax"
    )


def _validate_csrf(request: Request, container: AppContainer, csrf_header: str | None) -> None:
    cookie = request.cookies.get(container.settings.csrf_cookie_name)
    if not cookie or not csrf_header or not secrets.compare_digest(cookie, csrf_header):
        raise Unauthorized("CSRF validation failed")


async def _commit_auth_operation(
    session: AsyncSession, operation: Callable[[], Awaitable[AuthResult]]
) -> AuthResult:
    try:
        result = await operation()
        await session.commit()
        return result
    except AppError:
        # Authentication failures and replay detection write durable audit/security state.
        await session.commit()
        raise
    except Exception:
        await session.rollback()
        raise


@router.post("/register", response_model=SessionResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    rate_limits: Annotated[RateLimitService, Depends(get_rate_limit_service)],
) -> SessionResponse:
    await rate_limits.enforce(
        "register",
        _rate_identity(request, container),
        container.settings.registration_rate_limit,
        fail_closed=container.settings.auth_rate_limit_fail_closed,
    )
    service = AuthService(session, container.settings)
    try:
        result = await _commit_auth_operation(
            session,
            lambda: service.register(
                str(payload.email),
                payload.password,
                payload.display_name,
                get_correlation_id(),
                _client_ip(request),
                _user_agent(request),
            ),
        )
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("An account with this email already exists") from exc
    _set_session_cookies(response, result, container)
    return SessionResponse(
        access_token=result.access_token,
        expires_at=result.access_expires_at,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    rate_limits: Annotated[RateLimitService, Depends(get_rate_limit_service)],
) -> SessionResponse:
    identity = _rate_identity(request, container)
    fail_closed = container.settings.auth_rate_limit_fail_closed
    await rate_limits.enforce(
        "login", identity, container.settings.login_rate_limit, fail_closed=fail_closed
    )
    await rate_limits.enforce(
        "password-verify",
        identity,
        container.settings.password_verify_rate_limit,
        fail_closed=fail_closed,
    )
    service = AuthService(session, container.settings)
    result = await _commit_auth_operation(
        session,
        lambda: service.login(
            str(payload.email),
            payload.password,
            get_correlation_id(),
            _client_ip(request),
            _user_agent(request),
        ),
    )
    _set_session_cookies(response, result, container)
    return SessionResponse(
        access_token=result.access_token,
        expires_at=result.access_expires_at,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    rate_limits: Annotated[RateLimitService, Depends(get_rate_limit_service)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> SessionResponse:
    _validate_csrf(request, container, csrf_header)
    await rate_limits.enforce(
        "refresh",
        _rate_identity(request, container),
        container.settings.refresh_rate_limit,
        fail_closed=container.settings.auth_rate_limit_fail_closed,
    )
    raw_token = request.cookies.get(container.settings.refresh_cookie_name)
    if not raw_token:
        raise Unauthorized("Invalid session")
    service = AuthService(session, container.settings)
    result = await _commit_auth_operation(
        session,
        lambda: service.rotate(
            raw_token, get_correlation_id(), _client_ip(request), _user_agent(request)
        ),
    )
    _set_session_cookies(response, result, container)
    return SessionResponse(
        access_token=result.access_token,
        expires_at=result.access_expires_at,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> LogoutResponse:
    _validate_csrf(request, container, csrf_header)
    raw_token = request.cookies.get(container.settings.refresh_cookie_name)
    if raw_token:
        service = AuthService(session, container.settings)
        await service.logout(raw_token, get_correlation_id(), _client_ip(request))
        await session.commit()
    _clear_session_cookies(response, container)
    return LogoutResponse()


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> LogoutResponse:
    _validate_csrf(request, container, csrf_header)
    await AuthService(session, container.settings).logout_all(
        user, get_correlation_id(), _client_ip(request)
    )
    await session.commit()
    _clear_session_cookies(response, container)
    return LogoutResponse()


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
