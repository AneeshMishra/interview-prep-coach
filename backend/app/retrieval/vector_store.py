"""
Vector store abstraction over Qdrant. Qdrant is a retrieval index only —
never the source of truth (that's the relational DB, see app/db/models.py).
"""
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from app.config import Settings


@dataclass
class RetrievedQuestion:
    question_id: str
    score: float


class VectorStore:
    def __init__(self, settings: Settings):
        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection = settings.qdrant_collection
        self.embedder = SentenceTransformer(settings.embedding_model)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            vector_size = self.embedder.get_sentence_embedding_dimension()
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def upsert_question(self, question_id: str, text: str, metadata: dict):
        vector = self.embedder.encode(text).tolist()
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
        vector = self.embedder.encode(query).tolist()

        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=limit,
        )
        return [RetrievedQuestion(question_id=str(r.id), score=r.score) for r in results]
