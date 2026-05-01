import importlib
import sys
import types
import unittest
from types import SimpleNamespace


class FakeMessage:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


class RecordingMemoryPipeline:
    instances = []

    def __init__(self) -> None:
        self.extract_calls = []
        self.persist_calls = []
        RecordingMemoryPipeline.instances.append(self)

    def extract_candidates(self, messages):
        self.extract_calls.append(messages)
        return ["candidate"]

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
        return [SimpleNamespace(id=1)]


def load_chat_persistence_module(testcase: unittest.TestCase, pipeline_cls=RecordingMemoryPipeline):
    stub_names = [
        "app.db.models",
        "app.memory.memory_pipeline",
        "app.core.chat_persistence",
    ]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    models_module = types.ModuleType("app.db.models")
    models_module.Message = FakeMessage
    sys.modules["app.db.models"] = models_module

    memory_pipeline_module = types.ModuleType("app.memory.memory_pipeline")
    memory_pipeline_module.MemoryPipeline = pipeline_cls
    sys.modules["app.memory.memory_pipeline"] = memory_pipeline_module

    sys.modules.pop("app.core.chat_persistence", None)
    return importlib.import_module("app.core.chat_persistence")


class ChatPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        RecordingMemoryPipeline.instances.clear()

    def test_persist_chat_exchange_writes_messages_and_memory(self):
        module = load_chat_persistence_module(self)
        db = FakeDb()

        module.persist_chat_exchange(
            db=db,
            user_id="u1",
            project_id="p1",
            session_id="s1",
            user_message="你好",
            assistant_message="世界",
        )

        self.assertEqual(len(db.added), 2)
        self.assertEqual(db.added[0].role, "user")
        self.assertEqual(db.added[0].content, "你好")
        self.assertEqual(db.added[1].role, "assistant")
        self.assertEqual(db.added[1].content, "世界")
        self.assertEqual(db.commits, 2)
        self.assertEqual(len(RecordingMemoryPipeline.instances), 1)
        self.assertEqual(
            RecordingMemoryPipeline.instances[0].extract_calls,
            [[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "世界"},
            ]],
        )
        self.assertEqual(
            RecordingMemoryPipeline.instances[0].persist_calls,
            [
                {
                    "db": db,
                    "user_id": "u1",
                    "project_id": "p1",
                    "session_id": "s1",
                    "candidates": ["candidate"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
