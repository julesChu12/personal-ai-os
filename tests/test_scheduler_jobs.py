import importlib
import sys
import types
import unittest
from types import SimpleNamespace


class FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name

    def __ge__(self, other):
        return (self.name, ">=", other)

    def asc(self):
        return (self.name, "asc")


class FakeMessageModel:
    user_id = FakeColumn("user_id")
    project_id = FakeColumn("project_id")
    session_id = FakeColumn("session_id")
    created_at = FakeColumn("created_at")


class FakeMemoryModel:
    pass


class FakeSessionQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.distinct_called = False

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def distinct(self):
        self.distinct_called = True
        return self

    def all(self):
        return list(self.rows)


class FakeMessageQuery:
    def __init__(self, rows_by_session):
        self.rows_by_session = rows_by_session
        self.lookup = None
        self.ordering = []

    def filter_by(self, **kwargs):
        self.lookup = (kwargs["user_id"], kwargs["project_id"], kwargs["session_id"])
        return self

    def order_by(self, *args):
        self.ordering.extend(args)
        return self

    def all(self):
        return list(self.rows_by_session.get(self.lookup, []))


class FakeMemoryQuery:
    def __init__(self, existing_by_session):
        self.existing_by_session = existing_by_session
        self.lookup = None

    def filter_by(self, **kwargs):
        self.lookup = (
            kwargs["user_id"],
            kwargs["project_id"],
            kwargs["session_id"],
            kwargs["memory_type"],
        )
        return self

    def first(self):
        return self.existing_by_session.get(self.lookup)


class FakeDb:
    def __init__(self, session_rows, message_rows, existing_memories):
        self.session_rows = session_rows
        self.message_rows = message_rows
        self.existing_memories = existing_memories
        self.closed = False

    def query(self, *entities):
        if len(entities) == 3:
            return FakeSessionQuery(self.session_rows)
        if entities[0] is FakeMessageModel:
            return FakeMessageQuery(self.message_rows)
        if entities[0] is FakeMemoryModel:
            return FakeMemoryQuery(self.existing_memories)
        raise AssertionError(f"Unexpected query entities: {entities!r}")

    def close(self):
        self.closed = True


class FakePipeline:
    def __init__(self):
        self.extract_calls = []
        self.persist_calls = []

    def extract_candidates(self, messages):
        self.extract_calls.append(messages)
        return [
            SimpleNamespace(
                memory_type="learning",
                title="会话沉淀",
                content="系统总结",
                tags=["personal-ai-os"],
                importance=6,
            )
        ]

    def persist(self, db, user_id, project_id, session_id, candidates):
        self.persist_calls.append(
            {
                "db": db,
                "user_id": user_id,
                "project_id": project_id,
                "session_id": session_id,
                "candidates": candidates,
            }
        )
        return [SimpleNamespace(id=index + 1) for index, _ in enumerate(candidates)]


def load_jobs_module(testcase: unittest.TestCase):
    stub_names = [
        "app.db.database",
        "app.db.models",
        "app.memory.memory_pipeline",
        "app.scheduler.jobs",
    ]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    database_module = types.ModuleType("app.db.database")
    database_module.SessionLocal = lambda: None
    sys.modules["app.db.database"] = database_module

    models_module = types.ModuleType("app.db.models")
    models_module.Message = FakeMessageModel
    models_module.Memory = FakeMemoryModel
    sys.modules["app.db.models"] = models_module

    pipeline_module = types.ModuleType("app.memory.memory_pipeline")

    class PlaceholderPipeline:
        def extract_candidates(self, messages):
            raise AssertionError("测试不应实例化默认 MemoryPipeline")

        def persist(self, db, user_id, project_id, session_id, candidates):
            raise AssertionError("测试不应实例化默认 MemoryPipeline")

    pipeline_module.MemoryPipeline = PlaceholderPipeline
    sys.modules["app.memory.memory_pipeline"] = pipeline_module

    sys.modules.pop("app.scheduler.jobs", None)
    return importlib.import_module("app.scheduler.jobs")


class DailyMemoryJobTests(unittest.TestCase):
    def test_daily_memory_job_persists_summary_for_recent_session(self):
        jobs = load_jobs_module(self)
        db = FakeDb(
            session_rows=[("u1", "p1", "s1")],
            message_rows={
                ("u1", "p1", "s1"): [
                    SimpleNamespace(role="user", content="今天学习了 RAG"),
                    SimpleNamespace(role="assistant", content="整理了检索链路"),
                ]
            },
            existing_memories={},
        )
        pipeline = FakePipeline()

        result = jobs.daily_memory_job(db_factory=lambda: db, pipeline=pipeline, lookback_hours=24)

        self.assertEqual(
            result,
            {
                "sessions_considered": 1,
                "sessions_summarized": 1,
                "sessions_skipped": 0,
                "memories_saved": 1,
            },
        )
        self.assertEqual(
            pipeline.extract_calls,
            [[
                {"role": "user", "content": "今天学习了 RAG"},
                {"role": "assistant", "content": "整理了检索链路"},
            ]],
        )
        persisted = pipeline.persist_calls[0]["candidates"][0]
        self.assertEqual(persisted.memory_type, "session_summary")
        self.assertEqual(persisted.title, "定时汇总 s1")
        self.assertEqual(persisted.content, "系统总结")
        self.assertIn("scheduler", persisted.tags)
        self.assertTrue(db.closed)

    def test_daily_memory_job_skips_session_when_summary_memory_exists(self):
        jobs = load_jobs_module(self)
        db = FakeDb(
            session_rows=[("u1", "p1", "s1")],
            message_rows={
                ("u1", "p1", "s1"): [
                    SimpleNamespace(role="user", content="今天学习了 RAG"),
                    SimpleNamespace(role="assistant", content="整理了检索链路"),
                ]
            },
            existing_memories={("u1", "p1", "s1", "session_summary"): object()},
        )
        pipeline = FakePipeline()

        result = jobs.daily_memory_job(db_factory=lambda: db, pipeline=pipeline, lookback_hours=24)

        self.assertEqual(
            result,
            {
                "sessions_considered": 1,
                "sessions_summarized": 0,
                "sessions_skipped": 1,
                "memories_saved": 0,
            },
        )
        self.assertEqual(pipeline.extract_calls, [])
        self.assertEqual(pipeline.persist_calls, [])
        self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
