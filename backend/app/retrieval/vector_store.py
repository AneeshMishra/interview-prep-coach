"""
Vector store abstraction over Qdrant. Qdrant is a retrieval index only —
never the source of truth (that's the relational DB, see app/db/models.py).
"""
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams, Filter, FieldCondition, MatchValue

from app.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider


@dataclass
class RetrievedQuestion:
    question_id: str
    score: float


class VectorStore:
    def __init__(
        self,
        settings: Settings,
        embedding_provider: EmbeddingProvider | None = None,
        client: QdrantClient | None = None,
    ):
        self.client = client or QdrantClient(url=settings.qdrant_url)
        self.collection = settings.qdrant_collection
        self.embedder = embedding_provider or get_embedding_provider(settings)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.embedder.dimension, distance=Distance.COSINE),
            )

    def clear(self):
        """Delete and recreate the collection. Used before a full rebuild
        from the relational DB (app/ingestion/reindex.py) so points for
        questions that no longer exist there don't linger forever — Qdrant
        must reflect the relational DB exactly, not just be a superset of it."""
        self.client.delete_collection(collection_name=self.collection)
        self._ensure_collection()

    def upsert_question(self, question_id: str, text: str, metadata: dict):
        vector = self.embedder.embed([text])[0]
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=question_id, vector=vector, payload=metadata)],
        )

    def search(
        self,
        query: str,
        company: str | None = None,
        role: str | None = None,
        round_type: str | None = None,
        limit: int = 20,
    ) -> list[RetrievedQuestion]:
        conditions = []
        if company:
            conditions.append(FieldCondition(key="company", match=MatchValue(value=company)))
        if role:
            conditions.append(FieldCondition(key="role", match=MatchValue(value=role)))
        if round_type:
            conditions.append(FieldCondition(key="round_type", match=MatchValue(value=round_type)))

        query_filter = Filter(must=conditions) if conditions else None
        vector = self.embedder.embed([query])[0]

        # QdrantClient.search() was removed in newer qdrant-client releases
        # in favor of query_points(); this was never caught before because
        # every other test exercised a FakeVectorStore instead of a real
        # QdrantClient (see tests/test_vector_store.py).
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=query_filter,
            limit=limit,
        )
        return [RetrievedQuestion(question_id=str(p.id), score=p.score) for p in response.points]


@lru_cache
def get_vector_store() -> VectorStore:
    """Process-wide singleton so the embedding model loads once."""
    return VectorStore(get_settings())
