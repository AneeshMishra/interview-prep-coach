"""
Integration tests for the Qdrant adapter (P1-012), which previously had no
coverage at all — every other test exercises a FakeVectorStore instead.

Runs against qdrant-client's embedded in-memory engine (no server, no
Docker, no network) with a deterministic fake embedding provider, so these
exercise the real Qdrant collection/upsert/search/filter logic without
needing a live Qdrant instance or downloading a sentence-transformers model.
"""
import pytest
from qdrant_client import QdrantClient

from app.config import Settings
from app.embeddings.base import EmbeddingProvider
from app.retrieval.vector_store import VectorStore


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]

    @property
    def dimension(self) -> int:
        return 4


VECTORS = {
    "Design a URL shortener.": [1.0, 0.0, 0.0, 0.0],
    "How would you design a rate limiter?": [0.9, 0.1, 0.0, 0.0],
    "Tell me about a time you disagreed with your manager.": [0.0, 1.0, 0.0, 0.0],
    "url shortener design": [1.0, 0.0, 0.0, 0.0],
}

# Qdrant requires point ids to be an unsigned int or a UUID (both the real
# server and this in-memory engine enforce it) — matching production, where
# InterviewQuestion.id is always a uuid4 string.
Q_URL = "312f6697-8ab9-5175-be46-109c8596b2b9"
Q_RATE_LIMIT = "b8746aec-6e8e-5d2d-9594-b9343d07ab9d"
Q_BEHAVIORAL = "c350dd36-92af-5014-8c3c-2862412c000d"


@pytest.fixture
def settings():
    return Settings(qdrant_collection="test_questions")


@pytest.fixture
def store(settings):
    client = QdrantClient(location=":memory:")
    return VectorStore(settings, embedding_provider=FakeEmbeddingProvider(VECTORS), client=client)


def test_ensure_collection_creates_with_embedder_dimension(store, settings):
    info = store.client.get_collection(settings.qdrant_collection)
    assert info.config.params.vectors.size == 4


def test_ensure_collection_is_idempotent(settings):
    client = QdrantClient(location=":memory:")
    embedder = FakeEmbeddingProvider(VECTORS)

    VectorStore(settings, embedding_provider=embedder, client=client)
    # Constructing a second VectorStore against the same client/collection
    # must not raise (e.g. "collection already exists").
    VectorStore(settings, embedding_provider=embedder, client=client)

    collections = [c.name for c in client.get_collections().collections]
    assert collections.count(settings.qdrant_collection) == 1


def test_upsert_and_search_ranks_by_similarity(store):
    store.upsert_question(
        Q_URL, "Design a URL shortener.", {"company": "Amazon", "role": "Backend", "round_type": "system_design"}
    )
    store.upsert_question(
        Q_RATE_LIMIT,
        "How would you design a rate limiter?",
        {"company": "Google", "role": "SRE", "round_type": "system_design"},
    )
    store.upsert_question(
        Q_BEHAVIORAL,
        "Tell me about a time you disagreed with your manager.",
        {"company": "Amazon", "role": "Backend", "round_type": "behavioral"},
    )

    results = store.search("url shortener design", limit=10)

    assert [r.question_id for r in results] == [Q_URL, Q_RATE_LIMIT, Q_BEHAVIORAL]
    # Identical vector to the query should score highest (cosine similarity 1.0).
    assert results[0].score == pytest.approx(1.0, abs=1e-4)
    assert results[0].score > results[1].score > results[2].score


def test_search_applies_metadata_filters(store):
    store.upsert_question(
        Q_URL, "Design a URL shortener.", {"company": "Amazon", "role": "Backend", "round_type": "system_design"}
    )
    store.upsert_question(
        Q_RATE_LIMIT,
        "How would you design a rate limiter?",
        {"company": "Google", "role": "SRE", "round_type": "system_design"},
    )

    results = store.search("url shortener design", company="Google", limit=10)

    assert [r.question_id for r in results] == [Q_RATE_LIMIT]
