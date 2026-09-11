import httpx
import pytest

from app.config import Settings
from app.llm_providers.anthropic_provider import AnthropicProvider
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


class TestAnthropicProvider:
    def test_complete_posts_messages_request_and_returns_content(self, monkeypatch):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse({"content": [{"type": "text", "text": "Design a rate limiter."}]})

        monkeypatch.setattr(httpx, "post", fake_post)

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        result = provider.complete(system_prompt="You extract questions.", user_prompt="Section text")

        assert result == "Design a rate limiter."
        assert captured["url"] == "https://api.anthropic.com/v1/messages"
        assert captured["headers"]["x-api-key"] == "sk-ant-test"
        assert captured["headers"]["anthropic-version"]
        assert captured["json"]["model"] == "claude-sonnet-4-5"
        # System prompt is a top-level field in the Messages API, not a
        # "system" message — unlike OpenAI/Ollama's chat message array.
        assert captured["json"]["system"] == "You extract questions."
        assert captured["json"]["messages"] == [{"role": "user", "content": "Section text"}]

    def test_concatenates_multiple_text_blocks(self, monkeypatch):
        monkeypatch.setattr(
            httpx,
            "post",
            lambda *a, **k: FakeResponse(
                {"content": [{"type": "text", "text": "["}, {"type": "text", "text": "]"}]}
            ),
        )
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        assert provider.complete(system_prompt="sys", user_prompt="user") == "[]"

    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="IPC_ANTHROPIC_API_KEY"):
            AnthropicProvider(api_key=None, model="claude-sonnet-4-5")

        with pytest.raises(ValueError, match="IPC_ANTHROPIC_API_KEY"):
            AnthropicProvider(api_key="", model="claude-sonnet-4-5")

    def test_complete_raises_on_http_error(self, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse({}, status_code=401))

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
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

    def test_dispatches_to_anthropic(self):
        settings = Settings(
            llm_provider="anthropic", llm_model="claude-sonnet-4-5", anthropic_api_key="sk-ant-test"
        )
        provider = get_llm_provider(settings)
        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-sonnet-4-5"

    def test_unknown_provider_raises(self):
        settings = Settings(llm_provider="not-a-real-provider")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider(settings)
