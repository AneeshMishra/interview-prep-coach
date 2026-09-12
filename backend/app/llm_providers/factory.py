from app.config import Settings
from app.llm_providers.anthropic_provider import AnthropicProvider
from app.llm_providers.base import LLMProvider
from app.llm_providers.ollama_provider import OllamaProvider
from app.llm_providers.openai_provider import OpenAIProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.llm_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.llm_model)
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.llm_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
