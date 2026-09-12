"""Shared test helpers for authenticated requests. Every Document,
ChatSession and InterviewSession now belongs to a user, and every
protected endpoint requires the access-token cookie set by
app/api/routers/auth.py — these helpers create a test user and set that
cookie directly, without going through a real OAuth round trip."""
from sqlalchemy.orm import Session

from app.auth.jwt_tokens import create_access_token
from app.config import get_settings
from app.db.models import User


def create_user(db: Session, email: str = "test@example.com", display_name: str = "Test User") -> User:
    user = User(email=email, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(client, user_id: str) -> None:
    client.cookies.set("access_token", create_access_token(user_id, get_settings()))
