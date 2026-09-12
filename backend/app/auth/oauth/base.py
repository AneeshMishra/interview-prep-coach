"""
OAuth/SSO provider abstraction. Every provider (Google now; Facebook,
LinkedIn and Azure AD as the next increment — see factory.py) implements
this interface so the auth router and the rest of the app never depend on
a vendor SDK, matching the LLMProvider/EmbeddingProvider pattern elsewhere
in this codebase.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    provider_account_id: str
    email: str
    display_name: str | None
    avatar_url: str | None


class OAuthProvider(ABC):
    name: str

    @abstractmethod
    def authorization_url(self, state: str) -> str:
        """URL to redirect the browser to for the provider's consent screen."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_user_info(self, code: str) -> OAuthUserInfo:
        """Exchange an authorization code for the signed-in user's profile."""
        raise NotImplementedError
