from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from app.config import settings
from app.memory.embedding_provider import build_embedding_provider, validate_embedding_dimension
import uuid


class VectorStore:
    """Qdrant 向量存储适配器，负责记忆向量写入和范围内检索。"""

    def __init__(self) -> None:
        if settings.qdrant_url == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(url=settings.qdrant_url)
        self.collection = settings.qdrant_collection
        self.embedding_provider = build_embedding_provider()
        self.ensure_collection()

    def ensure_collection(self) -> None:
        """确保 collection 存在，并使用当前 embedding 维度创建新 collection。"""
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=settings.embedding_dimension, distance=Distance.COSINE),
            )

    def upsert_memory(self, text: str, payload: dict, point_id: str | None = None) -> str:
        """写入一条记忆向量，并返回可回填到数据库的 Qdrant point id。"""
        vector = self.embedding_provider.embed_texts([text])[0]
        validate_embedding_dimension(vector, settings.embedding_dimension)
        point_id = point_id or str(uuid.uuid4())
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return point_id

    def search(self, query: str, user_id: str, project_id: str, top_k: int = 5) -> list[dict]:
        """在指定用户和项目范围内检索记忆，避免跨范围召回。"""
        vector = self.embedding_provider.embed_texts([query])[0]
        validate_embedding_dimension(vector, settings.embedding_dimension)
        results = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="project_id", match=MatchValue(value=project_id)),
                ]
            ),
            limit=top_k,
        )
        return [{"score": r.score, "payload": r.payload} for r in results.points]
