"""
Stateless session tokens. There is no server-side session table (Redis is
deferred per CLAUDE.md, and a DB-backed session table was the alternative
we didn't pick) — a short-lived access token authorizes each request and a
longer-lived refresh token, both signed JWTs, lets the browser silently
get a new access token without forcing a re-login.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt

from app.config import Settings


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    pass


def _create_token(user_id: str, token_type: TokenType, expires_delta: timedelta, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, settings: Settings) -> str:
    return _create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes), settings
    )


def create_refresh_token(user_id: str, settings: Settings) -> str:
    return _create_token(
        user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days), settings
    )


def decode_token(token: str, expected_type: TokenType, settings: Settings) -> str:
    """Return the user_id encoded in the token, or raise InvalidTokenError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"Expected a {expected_type.value} token.")

    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Token has no subject.")
    return user_id
