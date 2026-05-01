import unittest
from types import SimpleNamespace

from app.memory import vector_store as vector_store_module
from app.memory.vector_store import VectorStore


class FakeRouter:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            points=[
                SimpleNamespace(score=0.9, payload={"user_id": "u1", "project_id": "p1", "title": "会话沉淀"}),
                SimpleNamespace(score=0.8, payload={"user_id": "u1", "project_id": "p1", "title": "第二条"}),
            ]
        )


class VectorStoreSearchTests(unittest.TestCase):
    def set_embedding_dimension(self, dimension: int) -> None:
        original_dimension = vector_store_module.settings.embedding_dimension
        vector_store_module.settings.embedding_dimension = dimension
        self.addCleanup(setattr, vector_store_module.settings, "embedding_dimension", original_dimension)

    def test_ensure_collection_uses_configured_embedding_dimension(self):
        self.set_embedding_dimension(3)

        class CollectionClient:
            def __init__(self) -> None:
                self.created = []

            def get_collections(self):
                return SimpleNamespace(collections=[])

            def create_collection(self, **kwargs):
                self.created.append(kwargs)

        client = CollectionClient()
        store = VectorStore.__new__(VectorStore)
        store.client = client
        store.collection = "memories"

        store.ensure_collection()

        self.assertEqual(len(client.created), 1)
        self.assertEqual(client.created[0]["collection_name"], "memories")
        self.assertEqual(client.created[0]["vectors_config"].size, 3)

    def test_search_uses_query_points_with_user_and_project_filters(self):
        self.set_embedding_dimension(3)
        store = VectorStore.__new__(VectorStore)
        store.client = FakeClient()
        store.collection = "memories"
        store.embedding_provider = FakeRouter()

        results = store.search(query="RAG", user_id="u1", project_id="p1", top_k=2)

        self.assertEqual(
            results,
            [
                {"score": 0.9, "payload": {"user_id": "u1", "project_id": "p1", "title": "会话沉淀"}},
                {"score": 0.8, "payload": {"user_id": "u1", "project_id": "p1", "title": "第二条"}},
            ],
        )

        self.assertEqual(len(store.client.calls), 1)
        call = store.client.calls[0]
        self.assertEqual(call["collection_name"], "memories")
        self.assertEqual(call["query"], [0.1, 0.2, 0.3])
        self.assertEqual(call["limit"], 2)
        self.assertIsNotNone(call["query_filter"])
        self.assertEqual(
            call["query_filter"].model_dump(),
            {
                "should": None,
                "min_should": None,
                "must": [
                    {
                        "key": "user_id",
                        "match": {"value": "u1"},
                        "range": None,
                        "geo_bounding_box": None,
                        "geo_radius": None,
                        "geo_polygon": None,
                        "values_count": None,
                        "is_empty": None,
                        "is_null": None,
                    },
                    {
                        "key": "project_id",
                        "match": {"value": "p1"},
                        "range": None,
                        "geo_bounding_box": None,
                        "geo_radius": None,
                        "geo_polygon": None,
                        "values_count": None,
                        "is_empty": None,
                        "is_null": None,
                    },
                ],
                "must_not": None,
            },
        )

    def test_upsert_memory_uses_embedding_provider_vectors(self):
        self.set_embedding_dimension(3)
        upsert_calls = []

        class UpsertClient:
            def upsert(self, **kwargs):
                upsert_calls.append(kwargs)

        store = VectorStore.__new__(VectorStore)
        store.client = UpsertClient()
        store.collection = "memories"
        store.embedding_provider = FakeRouter()

        point_id = store.upsert_memory("hello", {"user_id": "u1"})

        self.assertIsInstance(point_id, str)
        self.assertEqual(len(upsert_calls), 1)
        self.assertEqual(upsert_calls[0]["collection_name"], "memories")
        self.assertEqual(upsert_calls[0]["points"][0].vector, [0.1, 0.2, 0.3])

    def test_upsert_memory_accepts_explicit_point_id(self):
        self.set_embedding_dimension(3)
        upsert_calls = []

        class UpsertClient:
            def upsert(self, **kwargs):
                upsert_calls.append(kwargs)

        store = VectorStore.__new__(VectorStore)
        store.client = UpsertClient()
        store.collection = "memories"
        store.embedding_provider = FakeRouter()

        point_id = store.upsert_memory("hello", {"user_id": "u1"}, point_id="fixed-point")

        self.assertEqual(point_id, "fixed-point")
        self.assertEqual(upsert_calls[0]["points"][0].id, "fixed-point")

    def test_upsert_memory_rejects_embedding_dimension_mismatch_before_qdrant_write(self):
        self.set_embedding_dimension(4)

        class RecordingClient:
            def __init__(self) -> None:
                self.upsert_called = False

            def upsert(self, **kwargs):
                self.upsert_called = True

        client = RecordingClient()
        store = VectorStore.__new__(VectorStore)
        store.client = client
        store.collection = "memories"
        store.embedding_provider = FakeRouter()

        with self.assertRaisesRegex(ValueError, "embedding dimension mismatch"):
            store.upsert_memory("hello", {"user_id": "u1"})

        self.assertFalse(client.upsert_called)

    def test_search_rejects_embedding_dimension_mismatch_before_qdrant_query(self):
        self.set_embedding_dimension(4)

        store = VectorStore.__new__(VectorStore)
        store.client = FakeClient()
        store.collection = "memories"
        store.embedding_provider = FakeRouter()

        with self.assertRaisesRegex(ValueError, "embedding dimension mismatch"):
            store.search(query="RAG", user_id="u1", project_id="p1", top_k=2)

        self.assertEqual(store.client.calls, [])


if __name__ == "__main__":
    unittest.main()
