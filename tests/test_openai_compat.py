import importlib
import os
import sys
import types
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class RecordingOrchestrator:
    instances = []

    def __init__(self) -> None:
        self.calls = []
        self.stream_calls = []
        self.model = SimpleNamespace(chat_stream=self._model_chat_stream)
        RecordingOrchestrator.instances.append(self)

    def chat(self, user_id: str, project_id: str, session_id: str, message: str) -> dict:
        self.calls.append(
            {
                "user_id": user_id,
                "project_id": project_id,
                "session_id": session_id,
                "message": message,
            }
        )
        return {
            "answer": "兼容层回答",
            "memory_used": [{"payload": {"title": "记忆"}}],
            "agent_trace": [{"agent": "orchestrator", "action": "chat"}],
        }

    async def chat_stream(self, user_id: str, project_id: str, session_id: str, message: str, model=None):
        self.stream_calls.append(
            {
                "user_id": user_id,
                "project_id": project_id,
                "session_id": session_id,
                "message": message,
            }
        )
        yield (
            'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1,'
            '"model":"personal-ai-os-chat","choices":[{"index":0,"delta":{"role":"assistant"},'
            '"finish_reason":null}]}\n\n'
        )
        yield (
            'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1,'
            '"model":"personal-ai-os-chat","choices":[{"index":0,"delta":{"content":"流式回答"},'
            '"finish_reason":null}]}\n\n'
        )
        yield (
            'data: {"id":"chatcmpl-test","object":"chat.completion.chunk","created":1,'
            '"model":"personal-ai-os-chat","choices":[{"index":0,"delta":{},'
            '"finish_reason":"stop"}]}\n\n'
        )

    async def _model_chat_stream(self, messages, model=None):
        async for chunk in self.chat_stream("openwebui", "openwebui", "stream-session", messages[-1]["content"]):
            yield chunk


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


def load_openai_compat_module(
    testcase: unittest.TestCase,
    orchestrator_cls=RecordingOrchestrator,
    db=None,
    pipeline_cls=RecordingMemoryPipeline,
    compat_api_key="EMPTY",
    compat_api_keys=None,
):
    stub_names = [
        "app.config",
        "app.core.chat_persistence",
        "app.core.orchestrator",
        "app.db.database",
        "app.db.models",
        "app.memory.memory_pipeline",
        "app.api.routes_openai_compat",
    ]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    config_module = types.ModuleType("app.config")
    config_module.settings = SimpleNamespace(openai_compat_api_key=compat_api_key, openai_compat_api_keys=compat_api_keys)
    sys.modules["app.config"] = config_module

    orchestrator_module = types.ModuleType("app.core.orchestrator")
    orchestrator_module.Orchestrator = orchestrator_cls
    sys.modules["app.core.orchestrator"] = orchestrator_module

    fake_db = db or FakeDb()

    database_module = types.ModuleType("app.db.database")

    def get_db():
        yield fake_db

    database_module.get_db = get_db
    sys.modules["app.db.database"] = database_module

    models_module = types.ModuleType("app.db.models")
    models_module.Message = FakeMessage
    sys.modules["app.db.models"] = models_module

    memory_pipeline_module = types.ModuleType("app.memory.memory_pipeline")
    memory_pipeline_module.MemoryPipeline = pipeline_cls
    sys.modules["app.memory.memory_pipeline"] = memory_pipeline_module

    chat_persistence_module = types.ModuleType("app.core.chat_persistence")

    def persist_chat_exchange(db, user_id, project_id, session_id, user_message, assistant_message):
        db.add(FakeMessage(user_id=user_id, project_id=project_id, session_id=session_id, role="user", content=user_message))
        db.commit()
        db.add(
            FakeMessage(
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                role="assistant",
                content=assistant_message,
            )
        )
        db.commit()
        pipeline = pipeline_cls()
        candidates = pipeline.extract_candidates(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ]
        )
        pipeline.persist(db, user_id, project_id, session_id, candidates)

    chat_persistence_module.persist_chat_exchange = persist_chat_exchange
    sys.modules["app.core.chat_persistence"] = chat_persistence_module

    sys.modules.pop("app.api.routes_openai_compat", None)

    return importlib.import_module("app.api.routes_openai_compat")


def build_client(router_module) -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


class OpenAICompatRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        RecordingOrchestrator.instances.clear()
        RecordingMemoryPipeline.instances.clear()

    def test_models_endpoint_returns_virtual_model(self):
        router_module = load_openai_compat_module(self)
        client = build_client(router_module)

        response = client.get("/v1/models", headers={"Authorization": "Bearer EMPTY"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["object"], "list")
        self.assertEqual(payload["data"][0]["id"], "personal-ai-os-chat")
        self.assertEqual(payload["data"][0]["owned_by"], "personal-ai-os")

    def test_models_endpoint_requires_authorization_header(self):
        router_module = load_openai_compat_module(self)
        client = build_client(router_module)

        response = client.get("/v1/models")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "missing bearer token")

    def test_models_endpoint_rejects_invalid_token(self):
        router_module = load_openai_compat_module(self, compat_api_key="expected-key")
        client = build_client(router_module)

        response = client.get("/v1/models", headers={"Authorization": "Bearer wrong-key"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid bearer token")

    def test_chat_completions_persists_messages_and_memory(self):
        fake_db = FakeDb()
        router_module = load_openai_compat_module(self, db=fake_db)
        client = build_client(router_module)
        payload = {
            "model": "personal-ai-os-chat",
            "messages": [
                {"role": "system", "content": "系统指令"},
                {"role": "user", "content": "第一问"},
                {"role": "assistant", "content": "第一答"},
                {"role": "user", "content": "第二问"},
            ],
            "stream": False,
            "user": "alice",
        }

        response = client.post(
            "/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": "Bearer EMPTY",
                "X-Session-Id": "session-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(RecordingOrchestrator.instances), 1)
        self.assertEqual(
            RecordingOrchestrator.instances[0].calls,
            [
                {
                    "user_id": "alice",
                    "project_id": "openwebui",
                    "session_id": "session-1",
                    "message": (
                        "[Open WebUI Context]\n"
                        "system: 系统指令\n"
                        "user: 第一问\n"
                        "assistant: 第一答\n\n"
                        "[Current User Message]\n"
                        "第二问"
                    ),
                }
            ],
        )

        result = response.json()
        self.assertEqual(result["object"], "chat.completion")
        self.assertEqual(result["model"], "personal-ai-os-chat")
        self.assertEqual(result["choices"][0]["message"]["role"], "assistant")
        self.assertEqual(result["choices"][0]["message"]["content"], "兼容层回答")
        self.assertEqual(result["usage"]["total_tokens"], 0)
        self.assertEqual(len(fake_db.added), 2)
        self.assertEqual(fake_db.added[0].role, "user")
        self.assertEqual(fake_db.added[0].content, "第二问")
        self.assertEqual(fake_db.added[1].role, "assistant")
        self.assertEqual(fake_db.added[1].content, "兼容层回答")
        self.assertEqual(fake_db.commits, 2)
        self.assertEqual(len(RecordingMemoryPipeline.instances), 1)
        self.assertEqual(
            RecordingMemoryPipeline.instances[0].extract_calls,
            [[
                {"role": "user", "content": "第二问"},
                {"role": "assistant", "content": "兼容层回答"},
            ]],
        )
        self.assertEqual(
            RecordingMemoryPipeline.instances[0].persist_calls,
            [
                {
                    "db": fake_db,
                    "user_id": "alice",
                    "project_id": "openwebui",
                    "session_id": "session-1",
                    "candidates": ["candidate"],
                }
            ],
        )

    def test_chat_completions_uses_metadata_identity_when_provided(self):
        fake_db = FakeDb()
        router_module = load_openai_compat_module(self, db=fake_db)
        client = build_client(router_module)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "personal-ai-os-chat",
                "messages": [{"role": "user", "content": "项目内问题"}],
                "stream": False,
                "user": "openai-user-field",
                "metadata": {
                    "user_id": "alice",
                    "project_id": "project-a",
                    "session_id": "session-a",
                },
            },
            headers={"Authorization": "Bearer EMPTY"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            RecordingOrchestrator.instances[0].calls[0],
            {
                "user_id": "alice",
                "project_id": "project-a",
                "session_id": "session-a",
                "message": "项目内问题",
            },
        )
        self.assertEqual(
            RecordingMemoryPipeline.instances[0].persist_calls[0],
            {
                "db": fake_db,
                "user_id": "alice",
                "project_id": "project-a",
                "session_id": "session-a",
                "candidates": ["candidate"],
            },
        )

    def test_chat_completions_uses_key_bound_scope_when_metadata_is_absent(self):
        fake_db = FakeDb()
        router_module = load_openai_compat_module(
            self,
            db=fake_db,
            compat_api_keys='[{"key":"project-key","user_id":"alice","project_id":"project-a"}]',
        )
        client = build_client(router_module)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "personal-ai-os-chat",
                "messages": [{"role": "user", "content": "项目内问题"}],
                "stream": False,
            },
            headers={"Authorization": "Bearer project-key", "X-Session-Id": "session-a"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            RecordingOrchestrator.instances[0].calls[0],
            {
                "user_id": "alice",
                "project_id": "project-a",
                "session_id": "session-a",
                "message": "项目内问题",
            },
        )

    def test_chat_completions_rejects_metadata_scope_outside_key_binding(self):
        router_module = load_openai_compat_module(
            self,
            compat_api_keys='[{"key":"project-key","user_id":"alice","project_id":"project-a"}]',
        )
        client = build_client(router_module)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "personal-ai-os-chat",
                "messages": [{"role": "user", "content": "跨项目问题"}],
                "stream": False,
                "metadata": {"user_id": "bob", "project_id": "project-a"},
            },
            headers={"Authorization": "Bearer project-key"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "scope is outside API key binding")

    def test_chat_completions_rejects_empty_messages(self):
        router_module = load_openai_compat_module(self)
        client = build_client(router_module)

        response = client.post(
            "/v1/chat/completions",
            json={"model": "personal-ai-os-chat", "messages": [], "stream": False},
            headers={"Authorization": "Bearer EMPTY"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "messages must not be empty")

    def test_streaming_chat_persists_messages_and_memory_after_stream_finishes(self):
        fake_db = FakeDb()
        router_module = load_openai_compat_module(self, db=fake_db)
        client = build_client(router_module)

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "personal-ai-os-chat",
                "messages": [{"role": "user", "content": "你好"}],
                "stream": True,
                "user": "stream-user",
            },
            headers={
                "Authorization": "Bearer EMPTY",
                "X-Session-Id": "stream-session",
            },
        ) as response:
            body = "".join(response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertIn("流式回答", body)
        self.assertIn("[DONE]", body)
        self.assertEqual(len(fake_db.added), 2)
        self.assertEqual(fake_db.added[0].content, "你好")
        self.assertEqual(fake_db.added[1].content, "流式回答")
        self.assertEqual(fake_db.commits, 2)
        self.assertEqual(len(RecordingMemoryPipeline.instances), 1)
        self.assertEqual(
            RecordingMemoryPipeline.instances[0].extract_calls,
            [[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "流式回答"},
            ]],
        )


class OpenAICompatAppRegistrationTests(unittest.TestCase):
    def test_main_app_registers_openai_compat_routes(self):
        module_names = ["app.main", "app.db.database", "app.config"]
        originals = {name: sys.modules.get(name) for name in module_names}
        original_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"

        def restore_modules():
            for name, module in originals.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        def restore_env():
            if original_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original_database_url

        self.addCleanup(restore_modules)
        self.addCleanup(restore_env)

        for name in module_names:
            sys.modules.pop(name, None)

        main_module = importlib.import_module("app.main")
        paths = {route.path for route in main_module.app.routes}

        self.assertIn("/v1/models", paths)
        self.assertIn("/v1/chat/completions", paths)


if __name__ == "__main__":
    unittest.main()
