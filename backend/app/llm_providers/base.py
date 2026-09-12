"""
LLM provider abstraction. Every provider (Ollama, OpenAI, Anthropic) implements
this interface so the rest of the app never depends on a specific vendor SDK.
"""
from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text completion for a single-turn prompt."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Yield the response as text chunks, as they arrive (CLAUDE.md: SSE
        for LLM streaming). Each chunk is a fragment of the same raw text
        `complete()` would return in full — callers that need structured
        output (JSON) are responsible for incremental parsing themselves."""
        raise NotImplementedError
