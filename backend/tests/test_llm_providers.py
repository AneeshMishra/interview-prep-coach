import httpx
import pytest

from app.config import Settings
from app.llm_providers.factory import get_llm_provider
from app.llm_providers.ollama_provider import OllamaProvider
from app.llm_providers.openai_provider import OpenAIProvider


class FakeResponse:
    def __init__(self, json_body: dict, status_code: int = 200):
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_body


class TestOllamaProvider:
    def test_complete_posts_chat_messages_and_returns_content(self, monkeypatch):
        captured = {}

        def fake_post(url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse({"message": {"content": "Design a URL shortener."}})

        monkeypatch.setattr(httpx, "post", fake_post)

        provider = OllamaProvider(base_url="http://localhost:11434/", model="llama3")
        result = provider.complete(system_prompt="You extract questions.", user_prompt="Section text")

        assert result == "Design a URL shortener."
        assert captured["url"] == "http://localhost:11434/api/chat"
        assert captured["json"]["model"] == "llama3"
        assert captured["json"]["messages"] == [
            {"role": "system", "content": "You extract questions."},
            {"role": "user", "content": "Section text"},
        ]
        assert captured["json"]["stream"] is False

    def test_complete_raises_on_http_error(self, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse({}, status_code=500))

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3")
        with pytest.raises(httpx.HTTPStatusError):
            provider.complete(system_prompt="sys", user_prompt="user")


class TestOpenAIProvider:
    def test_complete_posts_chat_completions_and_returns_content(self, monkeypatch):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse({"choices": [{"message": {"content": "Design a rate limiter."}}]})

        monkeypatch.setattr(httpx, "post", fake_post)

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        result = provider.complete(system_prompt="You extract questions.", user_prompt="Section text")

        assert result == "Design a rate limiter."
        assert captured["url"] == "https://api.openai.com/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer sk-test"
        assert captured["json"]["model"] == "gpt-4o-mini"
        assert captured["json"]["messages"] == [
            {"role": "system", "content": "You extract questions."},
            {"role": "user", "content": "Section text"},
        ]

    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="IPC_OPENAI_API_KEY"):
            OpenAIProvider(api_key=None, model="gpt-4o-mini")

        with pytest.raises(ValueError, match="IPC_OPENAI_API_KEY"):
            OpenAIProvider(api_key="", model="gpt-4o-mini")

    def test_complete_raises_on_http_error(self, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse({}, status_code=401))

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        with pytest.raises(httpx.HTTPStatusError):
            provider.complete(system_prompt="sys", user_prompt="user")


class TestProviderFactory:
    def test_dispatches_to_ollama(self):
        settings = Settings(llm_provider="ollama", llm_model="llama3", ollama_base_url="http://x:1")
        provider = get_llm_provider(settings)
        assert isinstance(provider, OllamaProvider)
        assert provider.model == "llama3"

    def test_dispatches_to_openai(self):
        settings = Settings(llm_provider="openai", llm_model="gpt-4o-mini", openai_api_key="sk-test")
        provider = get_llm_provider(settings)
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o-mini"

    def test_anthropic_not_yet_implemented(self):
        settings = Settings(llm_provider="anthropic")
        with pytest.raises(NotImplementedError):
            get_llm_provider(settings)

    def test_unknown_provider_raises(self):
        settings = Settings(llm_provider="not-a-real-provider")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider(settings)
