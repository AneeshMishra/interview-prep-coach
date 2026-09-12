"""
Application configuration.
Loaded from environment variables / .env file via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="IPC_")

    # Database
    database_url: str = "sqlite:///./interview_prep.db"

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "interview_questions"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # LLM provider: "ollama" | "openai" | "anthropic"
    llm_provider: str = "ollama"
    llm_model: str = "llama3"
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # App
    app_env: str = "local"

    # CORS — the React frontend (Vite dev server or the Docker Compose nginx
    # build) runs on a different origin than the API, so the browser needs
    # these allowed explicitly. Comma-separated so it's easy to set via .env.
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Uploads
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # Extraction quality — see docs/architecture.md P1-007: records below
    # this confidence are flagged for human review rather than trusted outright.
    low_confidence_threshold: float = 0.75

    # Auth — sign-in is always via an external OAuth/SSO provider (see
    # app/auth/oauth); there is no local password. jwt_secret_key MUST be
    # overridden (via IPC_JWT_SECRET_KEY) outside local dev.
    jwt_secret_key: str = "dev-insecure-secret-change-me-in-production-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    # Where the browser is redirected back to after an OAuth callback.
    frontend_base_url: str = "http://localhost:5173"
    # False only for local http:// dev; a real deployment behind https must
    # keep this True so the session cookies aren't sent in the clear.
    auth_cookie_secure: bool = False

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
