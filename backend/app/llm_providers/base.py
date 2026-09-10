"""
LLM provider abstraction. Every provider (Ollama, OpenAI, Anthropic) implements
this interface so the rest of the app never depends on a specific vendor SDK.
"""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text completion for a single-turn prompt."""
        raise NotImplementedError
