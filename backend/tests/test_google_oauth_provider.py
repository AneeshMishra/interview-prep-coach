import httpx
import pytest

from app.auth.oauth.google_provider import GoogleOAuthProvider


def provider():
    return GoogleOAuthProvider(
        client_id="client-id", client_secret="client-secret", redirect_uri="http://localhost:8000/callback"
    )


def test_authorization_url_includes_client_id_state_and_redirect_uri():
    url = provider().authorization_url("state-123")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-id" in url
    assert "state=state-123" in url
    assert "redirect_uri=http" in url


@pytest.mark.asyncio
async def test_fetch_user_info_exchanges_code_and_returns_profile(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            assert "code=auth-code" in request.content.decode()
            return httpx.Response(200, json={"access_token": "access-123"})
        if request.url.path == "/v1/userinfo":
            assert request.headers["authorization"] == "Bearer access-123"
            return httpx.Response(
                200,
                json={
                    "sub": "google-user-1",
                    "email": "person@example.com",
                    "name": "Person Example",
                    "picture": "https://example.com/avatar.png",
                },
            )
        raise AssertionError(f"Unexpected request to {request.url}")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_async_client(transport=transport))

    info = await provider().fetch_user_info("auth-code")

    assert info.provider_account_id == "google-user-1"
    assert info.email == "person@example.com"
    assert info.display_name == "Person Example"
    assert info.avatar_url == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_fetch_user_info_raises_on_token_exchange_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_async_client(transport=transport))

    with pytest.raises(httpx.HTTPStatusError):
        await provider().fetch_user_info("bad-code")
