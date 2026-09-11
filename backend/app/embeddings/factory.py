from app.config import Settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.sentence_transformer_provider import SentenceTransformerEmbeddingProvider


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    # Only a local sentence-transformers model is supported today; the
    # abstraction exists so an API-based embedding provider can be added
    # later without VectorStore or its callers changing at all.
    return SentenceTransformerEmbeddingProvider(settings.embedding_model)
