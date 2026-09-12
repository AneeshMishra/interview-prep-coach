from sentence_transformers import SentenceTransformer

from app.embeddings.base import EmbeddingProvider


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local, free, no-API-cost default (CLAUDE.md's V1 embedding choice)."""

    def __init__(self, model_name: str):
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()
