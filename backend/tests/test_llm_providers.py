import json

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


class FakeStreamResponse:
    """Fakes the context manager httpx.stream() returns, for testing each
    provider's stream() against canned raw lines (NDJSON or SSE)."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def iter_lines(self):
        return iter(self._lines)


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

    def test_stream_yields_content_fragments_from_ndjson(self, monkeypatch):
        captured = {}
        lines = [
            json.dumps({"message": {"content": "Design "}, "done": False}),
            "",  # NDJSON streams can include blank keep-alive lines
            json.dumps({"message": {"content": "a URL "}, "done": False}),
            json.dumps({"message": {"content": "shortener."}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]

        def fake_stream(method, url, json, timeout):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = json
            return FakeStreamResponse(lines)

        monkeypatch.setattr(httpx, "stream", fake_stream)

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3")
        chunks = list(provider.stream(system_prompt="sys", user_prompt="user"))

        assert chunks == ["Design ", "a URL ", "shortener."]
        assert captured["method"] == "POST"
        assert captured["url"] == "http://localhost:11434/api/chat"
        assert captured["json"]["stream"] is True

    def test_stream_raises_on_http_error(self, monkeypatch):
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStreamResponse([], status_code=500))

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3")
        with pytest.raises(httpx.HTTPStatusError):
            list(provider.stream(system_prompt="sys", user_prompt="user"))


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

    def test_stream_yields_content_deltas_from_sse(self, monkeypatch):
        captured = {}
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"role": "assistant"}}]}),
            "",
            "data: " + json.dumps({"choices": [{"delta": {"content": "Design "}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "a rate limiter."}}]}),
            "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ]

        def fake_stream(method, url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeStreamResponse(lines)

        monkeypatch.setattr(httpx, "stream", fake_stream)

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        chunks = list(provider.stream(system_prompt="sys", user_prompt="user"))

        assert chunks == ["Design ", "a rate limiter."]
        assert captured["url"] == "https://api.openai.com/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer sk-test"
        assert captured["json"]["stream"] is True

    def test_stream_raises_on_http_error(self, monkeypatch):
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStreamResponse([], status_code=401))

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        with pytest.raises(httpx.HTTPStatusError):
            list(provider.stream(system_prompt="sys", user_prompt="user"))


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

    def test_stream_yields_text_deltas_only_from_content_block_delta_events(self, monkeypatch):
        captured = {}
        lines = [
            "data: " + json.dumps({"type": "message_start"}),
            "data: " + json.dumps({"type": "content_block_start"}),
            "",
            "data: " + json.dumps(
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Design "}}
            ),
            "data: " + json.dumps(
                {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "a rate limiter."}}
            ),
            "data: " + json.dumps({"type": "content_block_stop"}),
            "data: " + json.dumps({"type": "message_delta"}),
            "data: " + json.dumps({"type": "message_stop"}),
        ]

        def fake_stream(method, url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeStreamResponse(lines)

        monkeypatch.setattr(httpx, "stream", fake_stream)

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        chunks = list(provider.stream(system_prompt="sys", user_prompt="user"))

        assert chunks == ["Design ", "a rate limiter."]
        assert captured["url"] == "https://api.anthropic.com/v1/messages"
        assert captured["headers"]["x-api-key"] == "sk-ant-test"
        assert captured["json"]["stream"] is True

    def test_stream_raises_on_http_error(self, monkeypatch):
        monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStreamResponse([], status_code=401))

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        with pytest.raises(httpx.HTTPStatusError):
            list(provider.stream(system_prompt="sys", user_prompt="user"))


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
