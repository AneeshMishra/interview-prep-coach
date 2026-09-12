import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers.auth import STATE_COOKIE
from app.auth.dependencies import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE
from app.auth.oauth.base import OAuthUserInfo
from app.config import Settings, get_settings
from app.db.base import Base, get_db
from app.db.models import OAuthAccount, User
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        auth_cookie_secure=False,
    )

    test_client = TestClient(app)
    yield test_client, TestingSession
    app.dependency_overrides.clear()


def test_login_redirects_to_googles_consent_screen_and_sets_state_cookie(client):
    test_client, _ = client
    response = test_client.get("/api/v1/auth/google/login", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert STATE_COOKIE in response.cookies


def test_login_for_unconfigured_provider_returns_503(client):
    test_client, _ = client
    app.dependency_overrides[get_settings] = lambda: Settings()  # no google credentials
    response = test_client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code == 503


def test_login_for_unimplemented_provider_returns_404(client):
    test_client, _ = client
    response = test_client.get("/api/v1/auth/facebook/login", follow_redirects=False)
    assert response.status_code == 404


def test_callback_without_matching_state_is_rejected(client):
    test_client, _ = client
    test_client.cookies.set(STATE_COOKIE, "expected-state")
    response = test_client.get(
        "/api/v1/auth/google/callback", params={"code": "abc", "state": "wrong-state"}
    )
    assert response.status_code == 400


def test_callback_creates_a_new_user_and_sets_session_cookies(client, monkeypatch):
    test_client, TestingSession = client
    test_client.cookies.set(STATE_COOKIE, "matching-state")

    async def fake_fetch_user_info(self, code):
        assert code == "auth-code-123"
        return OAuthUserInfo(
            provider_account_id="google-42",
            email="new.user@example.com",
            display_name="New User",
            avatar_url="https://example.com/a.png",
        )

    monkeypatch.setattr(
        "app.auth.oauth.google_provider.GoogleOAuthProvider.fetch_user_info", fake_fetch_user_info
    )

    response = test_client.get(
        "/api/v1/auth/google/callback",
        params={"code": "auth-code-123", "state": "matching-state"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert ACCESS_TOKEN_COOKIE in response.cookies
    assert REFRESH_TOKEN_COOKIE in response.cookies

    db = TestingSession()
    user = db.query(User).filter(User.email == "new.user@example.com").first()
    assert user is not None
    assert user.display_name == "New User"
    account = db.query(OAuthAccount).filter(OAuthAccount.user_id == user.id).first()
    assert account.provider == "google"
    assert account.provider_account_id == "google-42"
    db.close()


def test_callback_reuses_existing_user_on_repeat_login(client, monkeypatch):
    test_client, TestingSession = client

    async def fake_fetch_user_info(self, code):
        return OAuthUserInfo(
            provider_account_id="google-99",
            email="repeat@example.com",
            display_name="Repeat User",
            avatar_url=None,
        )

    monkeypatch.setattr(
        "app.auth.oauth.google_provider.GoogleOAuthProvider.fetch_user_info", fake_fetch_user_info
    )

    test_client.cookies.set(STATE_COOKIE, "state-1")
    test_client.get(
        "/api/v1/auth/google/callback", params={"code": "code-1", "state": "state-1"}, follow_redirects=False
    )
    test_client.cookies.set(STATE_COOKIE, "state-2")
    test_client.get(
        "/api/v1/auth/google/callback", params={"code": "code-2", "state": "state-2"}, follow_redirects=False
    )

    db = TestingSession()
    users = db.query(User).filter(User.email == "repeat@example.com").all()
    assert len(users) == 1
    accounts = db.query(OAuthAccount).filter(OAuthAccount.provider_account_id == "google-99").all()
    assert len(accounts) == 1
    db.close()


def test_me_requires_a_valid_session(client):
    test_client, _ = client
    response = test_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_profile_after_login(client, monkeypatch):
    test_client, _ = client

    async def fake_fetch_user_info(self, code):
        return OAuthUserInfo(
            provider_account_id="google-1",
            email="me@example.com",
            display_name="Me",
            avatar_url=None,
        )

    monkeypatch.setattr(
        "app.auth.oauth.google_provider.GoogleOAuthProvider.fetch_user_info", fake_fetch_user_info
    )
    test_client.cookies.set(STATE_COOKIE, "s")
    test_client.get("/api/v1/auth/google/callback", params={"code": "c", "state": "s"}, follow_redirects=False)

    response = test_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_logout_clears_session_cookies(client, monkeypatch):
    test_client, _ = client

    async def fake_fetch_user_info(self, code):
        return OAuthUserInfo(
            provider_account_id="google-2", email="logout@example.com", display_name=None, avatar_url=None
        )

    monkeypatch.setattr(
        "app.auth.oauth.google_provider.GoogleOAuthProvider.fetch_user_info", fake_fetch_user_info
    )
    test_client.cookies.set(STATE_COOKIE, "s")
    test_client.get("/api/v1/auth/google/callback", params={"code": "c", "state": "s"}, follow_redirects=False)
    assert test_client.get("/api/v1/auth/me").status_code == 200

    logout_response = test_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    assert test_client.get("/api/v1/auth/me").status_code == 401


def test_refresh_without_cookie_returns_401(client):
    test_client, _ = client
    response = test_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_issues_a_new_access_token(client, monkeypatch):
    test_client, _ = client

    async def fake_fetch_user_info(self, code):
        return OAuthUserInfo(
            provider_account_id="google-3", email="refresh@example.com", display_name=None, avatar_url=None
        )

    monkeypatch.setattr(
        "app.auth.oauth.google_provider.GoogleOAuthProvider.fetch_user_info", fake_fetch_user_info
    )
    test_client.cookies.set(STATE_COOKIE, "s")
    test_client.get("/api/v1/auth/google/callback", params={"code": "c", "state": "s"}, follow_redirects=False)

    # Drop the access token, keep the refresh token — the browser flow when
    # the short-lived access token has expired but the session should live on.
    del test_client.cookies[ACCESS_TOKEN_COOKIE]
    assert test_client.get("/api/v1/auth/me").status_code == 401

    refresh_response = test_client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 204
    assert ACCESS_TOKEN_COOKIE in refresh_response.cookies

    assert test_client.get("/api/v1/auth/me").status_code == 200
