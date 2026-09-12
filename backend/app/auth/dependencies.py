"""FastAPI dependencies that resolve the signed-in user from the access-token
httpOnly cookie set by app/api/routers/auth.py."""
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.jwt_tokens import InvalidTokenError, TokenType, decode_token
from app.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import User

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def get_current_user(
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    try:
        user_id = decode_token(access_token, TokenType.ACCESS, settings)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")
    return user
