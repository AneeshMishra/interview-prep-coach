"""
Embedding provider abstraction. VectorStore depends on this interface, never
on a specific embedding model or vendor, so the local sentence-transformers
default can later be swapped for an API-based provider (CLAUDE.md: "Embeddings
must have a provider abstraction").

Synchronous rather than the `async def embed(...)` sketched in CLAUDE.md's
architecture notes, to match the precedent already set by LLMProvider.complete
(also sync in this codebase despite the doc's `async def generate` sketch) —
a local sentence-transformers model call is CPU-bound anyway, so async
without an executor wouldn't actually free the event loop.
"""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector size this provider produces — needed to size the Qdrant collection."""
        raise NotImplementedError
