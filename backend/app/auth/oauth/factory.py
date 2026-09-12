"""
Provider registry. Only Google is wired up so far (the recommended rollout:
prove the shared OAuthProvider abstraction end-to-end with one provider
before adding the others). Facebook, LinkedIn and Azure AD SSO are the next
increment — each is a thin OAuthProvider adapter following
google_provider.py, registered here once implemented.
"""
from app.auth.oauth.base import OAuthProvider
from app.auth.oauth.google_provider import GoogleOAuthProvider
from app.config import Settings

SUPPORTED_PROVIDERS = ("google",)


class UnsupportedProviderError(Exception):
    pass


class ProviderNotConfiguredError(Exception):
    pass


def get_oauth_provider(provider_name: str, settings: Settings) -> OAuthProvider:
    if provider_name == "google":
        if not settings.google_client_id or not settings.google_client_secret:
            raise ProviderNotConfiguredError(
                "Google sign-in is not configured (missing IPC_GOOGLE_CLIENT_ID/IPC_GOOGLE_CLIENT_SECRET)."
            )
        return GoogleOAuthProvider(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_oauth_redirect_uri,
        )
    if provider_name in ("facebook", "linkedin", "azure"):
        raise UnsupportedProviderError(
            f"{provider_name!r} sign-in is not implemented yet — Google is the only provider wired up so far."
        )
    raise UnsupportedProviderError(f"Unknown provider: {provider_name!r}")
