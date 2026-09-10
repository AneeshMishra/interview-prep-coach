from app.config import Settings
from app.llm_providers.base import LLMProvider
from app.llm_providers.ollama_provider import OllamaProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.llm_model)
    if settings.llm_provider == "openai":
        raise NotImplementedError("OpenAI provider adapter is a Phase 1 follow-up.")
    if settings.llm_provider == "anthropic":
        raise NotImplementedError("Anthropic provider adapter is a Phase 1 follow-up.")
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
