"""
GET  /auth/{provider}/login    — redirect to the provider's consent screen.
GET  /auth/{provider}/callback — exchange the auth code, sign the user in.
GET  /auth/me                  — the signed-in user's profile.
POST /auth/logout              — clear the session cookies.
POST /auth/refresh             — mint a new access token from the refresh cookie.

Sign-in is always via an external OAuth/SSO provider (app/auth/oauth) —
there's no local password. Sessions are stateless signed JWTs in httpOnly
cookies (app/auth/jwt_tokens.py), not a server-side session store, per
CLAUDE.md's "Redis is deferred" and "never use an in-memory dict as the
session store" rules.
"""
import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, get_current_user
from app.auth.jwt_tokens import InvalidTokenError, TokenType, create_access_token, create_refresh_token, decode_token
from app.auth.oauth.factory import ProviderNotConfiguredError, UnsupportedProviderError, get_oauth_provider
from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import OAuthAccount, User

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "oauth_state"
STATE_COOKIE_MAX_AGE_SECONDS = 10 * 60


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }


def _set_session_cookies(response: Response, user_id: str, settings: Settings) -> None:
    access_token = create_access_token(user_id, settings)
    refresh_token = create_refresh_token(user_id, settings)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def _find_or_create_user(db: Session, provider: str, info) -> User:
    account = (
        db.query(OAuthAccount)
        .filter(OAuthAccount.provider == provider, OAuthAccount.provider_account_id == info.provider_account_id)
        .first()
    )
    if account is not None:
        return account.user

    # Same email via a different provider — link rather than duplicate.
    user = db.query(User).filter(User.email == info.email).first()
    if user is None:
        user = User(email=info.email, display_name=info.display_name, avatar_url=info.avatar_url)
        db.add(user)
        db.flush()

    db.add(OAuthAccount(user_id=user.id, provider=provider, provider_account_id=info.provider_account_id))
    db.commit()
    db.refresh(user)
    return user


@router.get("/{provider}/login")
def login(provider: str, settings: Settings = Depends(get_settings)):
    try:
        oauth_provider = get_oauth_provider(provider, settings)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    state = secrets.token_urlsafe(32)
    response = RedirectResponse(url=oauth_provider.authorization_url(state))
    response.set_cookie(
        STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=STATE_COOKIE_MAX_AGE_SECONDS,
    )
    return response


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    oauth_state: str | None = Cookie(default=None, alias=STATE_COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not code or not state or not oauth_state or state != oauth_state:
        raise HTTPException(status_code=400, detail="Invalid or expired sign-in attempt. Please try again.")

    try:
        oauth_provider = get_oauth_provider(provider, settings)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        info = await oauth_provider.fetch_user_info(code)
    except Exception as exc:  # noqa: BLE001 - provider unreachable or rejected the code
        raise HTTPException(status_code=401, detail="Could not complete sign-in with this provider.") from exc

    user = _find_or_create_user(db, provider, info)

    response = RedirectResponse(url=settings.frontend_base_url)
    response.delete_cookie(STATE_COOKIE)
    _set_session_cookies(response, user.id, settings)
    return response


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _serialize_user(current_user)


@router.post("/logout")
def logout():
    response = Response(status_code=204)
    response.delete_cookie(ACCESS_TOKEN_COOKIE)
    response.delete_cookie(REFRESH_TOKEN_COOKIE)
    return response


@router.post("/refresh")
def refresh(
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    try:
        user_id = decode_token(refresh_token, TokenType.REFRESH, settings)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")

    response = Response(status_code=204)
    _set_session_cookies(response, user.id, settings)
    return response
