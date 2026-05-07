import importlib
import sys
import types
import unittest
from types import SimpleNamespace


class FakeDb:
    def __init__(self, existing_memory=None) -> None:
        self.added = []
        self.commits = 0
        if existing_memory is None:
            self.existing_memories = []
        elif isinstance(existing_memory, list):
            self.existing_memories = existing_memory
        else:
            self.existing_memories = [existing_memory]
        self.filters = []

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1

    def query(self, model):
        return FakeQuery(self)

    def find_memory(self, filters: dict):
        for memory in self.existing_memories:
            if all(getattr(memory, key, None) == value for key, value in filters.items()):
                return memory
        return None


class FakeQuery:
    def __init__(self, db: FakeDb) -> None:
        self.db = db
        self.filter_kwargs = {}

    def filter_by(self, **kwargs):
        self.filter_kwargs.update(kwargs)
        self.db.filters.append(kwargs)
        return self

    def first(self):
        return self.db.find_memory(self.filter_kwargs)


class FakeVectorStoreSuccess:
    calls = []

    def upsert_memory(self, text: str, payload: dict, point_id: str | None = None) -> str:
        FakeVectorStoreSuccess.calls.append({"text": text, "payload": payload, "point_id": point_id})
        return point_id or "point-1"


class FakeVectorStoreFailure:
    def upsert_memory(self, text: str, payload: dict, point_id: str | None = None) -> str:
        raise RuntimeError("vector write failed")


class CountingVectorStore:
    calls = 0

    def upsert_memory(self, text: str, payload: dict, point_id: str | None = None) -> str:
        CountingVectorStore.calls += 1
        return point_id or "point-counting"


class FakeObsidianWriter:
    def write_memory(self, user_id: str, project_id: str, session_id: str, candidate) -> str:
        return f"/vault/{project_id}/{session_id}.md"


class FakeMemoryRow:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def load_memory_pipeline_module(testcase: unittest.TestCase, vector_store_cls):
    stub_names = [
        "app.core.model_router",
        "app.db.models",
        "app.memory.obsidian_writer",
        "app.memory.vector_store",
        "app.memory.memory_pipeline",
    ]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    model_router_module = types.ModuleType("app.core.model_router")

    class FakeModelRouter:
        def chat(self, prompt):
            return "summary"

    model_router_module.ModelRouter = FakeModelRouter
    sys.modules["app.core.model_router"] = model_router_module

    db_models_module = types.ModuleType("app.db.models")
    db_models_module.Memory = FakeMemoryRow
    sys.modules["app.db.models"] = db_models_module

    obsidian_module = types.ModuleType("app.memory.obsidian_writer")
    obsidian_module.ObsidianWriter = FakeObsidianWriter
    sys.modules["app.memory.obsidian_writer"] = obsidian_module

    vector_store_module = types.ModuleType("app.memory.vector_store")
    vector_store_module.VectorStore = vector_store_cls
    sys.modules["app.memory.vector_store"] = vector_store_module

    sys.modules.pop("app.memory.memory_pipeline", None)
    return importlib.import_module("app.memory.memory_pipeline")


class MemoryPipelinePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        CountingVectorStore.calls = 0
        FakeVectorStoreSuccess.calls = []

    def test_persist_keeps_database_record_when_vector_write_fails(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreFailure)
        pipeline = module.MemoryPipeline()
        db = FakeDb()
        candidate = SimpleNamespace(
            memory_type="learning",
            title="会话沉淀",
            content="summary",
            tags=["memory"],
            importance=6,
        )

        with self.assertLogs("app.memory.memory_pipeline", level="ERROR") as logs:
            saved = pipeline.persist(db, "u1", "p1", "s1", [candidate])

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].qdrant_point_id, None)
        self.assertEqual(saved[0].obsidian_path, "/vault/p1/s1.md")
        self.assertEqual(db.commits, 1)
        self.assertTrue(
            any("Vector persistence failed" in message and "vector write failed" in message for message in logs.output),
            logs.output,
        )

    def test_persist_sets_qdrant_point_id_when_vector_write_succeeds(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreSuccess)
        pipeline = module.MemoryPipeline()
        db = FakeDb()
        candidate = SimpleNamespace(
            memory_type="learning",
            title="会话沉淀",
            content="summary",
            tags=["memory"],
            importance=6,
        )

        saved = pipeline.persist(db, "u1", "p1", "s1", [candidate])

        self.assertEqual(saved[0].qdrant_point_id, "point-1")
        self.assertEqual(db.commits, 1)

    def test_persist_skips_exact_duplicate_memory_without_vector_write(self):
        module = load_memory_pipeline_module(self, CountingVectorStore)
        pipeline = module.MemoryPipeline()
        existing = SimpleNamespace(
            id=1,
            user_id="u1",
            project_id="p1",
            session_id="s1",
            memory_type="learning",
            title="会话沉淀",
            content="summary",
        )
        db = FakeDb(existing_memory=existing)
        candidate = SimpleNamespace(
            memory_type="learning",
            title="会话沉淀",
            content="summary",
            tags=["memory"],
            importance=6,
        )

        saved = pipeline.persist(db, "u1", "p1", "s1", [candidate])

        self.assertEqual(saved, [existing])
        self.assertEqual(db.added, [])
        self.assertEqual(db.commits, 0)
        self.assertEqual(CountingVectorStore.calls, 0)

    def test_persist_updates_existing_memory_with_same_identity_and_reuses_point_id(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreSuccess)
        pipeline = module.MemoryPipeline()
        existing = SimpleNamespace(
            id=1,
            user_id="u1",
            project_id="p1",
            session_id="old-session",
            memory_type="learning",
            title="会话沉淀",
            content="old summary",
            tags=["old"],
            importance=3,
            obsidian_path="/vault/p1/old-session.md",
            qdrant_point_id="existing-point",
        )
        db = FakeDb(existing_memory=existing)
        candidate = SimpleNamespace(
            memory_type="learning",
            title="会话沉淀",
            content="new summary",
            tags=["memory", "updated"],
            importance=7,
        )

        saved = pipeline.persist(db, "u1", "p1", "new-session", [candidate])

        self.assertEqual(saved, [existing])
        self.assertEqual(db.added, [])
        self.assertEqual(db.commits, 1)
        self.assertEqual(existing.session_id, "new-session")
        self.assertEqual(existing.content, "new summary")
        self.assertEqual(existing.tags, ["memory", "updated"])
        self.assertEqual(existing.importance, 7)
        self.assertEqual(existing.obsidian_path, "/vault/p1/new-session.md")
        self.assertEqual(existing.qdrant_point_id, "existing-point")
        self.assertEqual(
            FakeVectorStoreSuccess.calls,
            [
                {
                    "text": "new summary",
                    "payload": {
                        "user_id": "u1",
                        "project_id": "p1",
                        "session_id": "new-session",
                        "memory_type": "learning",
                        "title": "会话沉淀",
                        "tags": ["memory", "updated"],
                        "obsidian_path": "/vault/p1/new-session.md",
                        "source": "chat",
                        "governance_version": "memory-governance-v1",
                        "quality_score": 0.7,
                    },
                    "point_id": "existing-point",
                }
            ],
        )

    def test_persist_keeps_existing_memory_unchanged_when_update_vector_write_fails(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreFailure)
        pipeline = module.MemoryPipeline()
        existing = SimpleNamespace(
            id=1,
            user_id="u1",
            project_id="p1",
            session_id="old-session",
            memory_type="learning",
            title="会话沉淀",
            content="old summary",
            tags=["old"],
            importance=3,
            obsidian_path="/vault/p1/old-session.md",
            qdrant_point_id="existing-point",
        )
        db = FakeDb(existing_memory=existing)
        candidate = SimpleNamespace(
            memory_type="learning",
            title="会话沉淀",
            content="new summary",
            tags=["memory", "updated"],
            importance=7,
        )

        with self.assertLogs("app.memory.memory_pipeline", level="ERROR") as logs:
            saved = pipeline.persist(db, "u1", "p1", "new-session", [candidate])

        self.assertEqual(saved, [existing])
        self.assertEqual(db.commits, 0)
        self.assertEqual(existing.session_id, "old-session")
        self.assertEqual(existing.content, "old summary")
        self.assertEqual(existing.tags, ["old"])
        self.assertEqual(existing.importance, 3)
        self.assertEqual(existing.obsidian_path, "/vault/p1/old-session.md")
        self.assertEqual(existing.qdrant_point_id, "existing-point")
        self.assertTrue(any("Vector persistence failed" in message for message in logs.output), logs.output)

    def test_persist_normalizes_memory_identity_for_lookup_and_storage(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreSuccess)
        pipeline = module.MemoryPipeline()
        existing = SimpleNamespace(
            id=1,
            user_id="u1",
            project_id="p1",
            session_id="old-session",
            memory_type="learning",
            title="会话沉淀",
            content="old summary",
            tags=["old"],
            importance=3,
            obsidian_path="/vault/p1/old-session.md",
            qdrant_point_id="existing-point",
        )
        db = FakeDb(existing_memory=existing)
        candidate = SimpleNamespace(
            memory_type=" Learning ",
            title=" 会话沉淀 ",
            content="new summary",
            tags=["memory"],
            importance=6,
        )

        saved = pipeline.persist(db, "u1", "p1", "s1", [candidate])

        self.assertEqual(saved, [existing])
        self.assertEqual(db.added, [])
        self.assertEqual(existing.memory_type, "learning")
        self.assertEqual(existing.title, "会话沉淀")
        self.assertEqual(FakeVectorStoreSuccess.calls[0]["payload"]["memory_type"], "learning")
        self.assertEqual(FakeVectorStoreSuccess.calls[0]["payload"]["title"], "会话沉淀")

    def test_persist_adds_governance_metadata_to_vector_payload(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreSuccess)
        pipeline = module.MemoryPipeline()
        db = FakeDb()
        candidate = SimpleNamespace(
            memory_type="agent_result",
            title="Agent result",
            content="summary",
            tags=["agent"],
            importance=9,
        )

        pipeline.persist(db, "u1", "p1", "s1", [candidate])

        payload = FakeVectorStoreSuccess.calls[0]["payload"]
        self.assertEqual(payload["source"], "agent")
        self.assertEqual(payload["governance_version"], "memory-governance-v1")
        self.assertEqual(payload["quality_score"], 0.9)

    def test_persist_does_not_update_same_title_from_different_project(self):
        module = load_memory_pipeline_module(self, FakeVectorStoreSuccess)
        pipeline = module.MemoryPipeline()
        existing = SimpleNamespace(
            id=1,
            user_id="u1",
            project_id="other-project",
            session_id="s1",
            memory_type="learning",
            title="会话沉淀",
            content="other project summary",
        )
        db = FakeDb(existing_memory=existing)
        candidate = SimpleNamespace(
            memory_type="learning",
            title="会话沉淀",
            content="project p1 summary",
            tags=["memory"],
            importance=6,
        )

        saved = pipeline.persist(db, "u1", "p1", "s1", [candidate])

        self.assertNotEqual(saved, [existing])
        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.added[0].project_id, "p1")
        self.assertEqual(existing.content, "other project summary")


if __name__ == "__main__":
    unittest.main()
