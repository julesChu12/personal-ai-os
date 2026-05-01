import importlib
import asyncio
import sys
import types
import unittest
from types import SimpleNamespace


class FakeEmbeddingOpenAI:
    def __init__(self, api_key=None, base_url=None, timeout=None, max_retries=None):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.embeddings = SimpleNamespace(create=self._create)
        self.calls = 0

    def _create(self, model=None, input=None):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary embedding outage")
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class FailingEmbeddingOpenAI(FakeEmbeddingOpenAI):
    def _create(self, model=None, input=None):
        self.calls += 1
        raise RuntimeError("provider exploded with emb-key")


class FakeChatOpenAI:
    def __init__(self, api_key=None, base_url=None, timeout=None, max_retries=None):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.calls = []

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="model answer"))])


class FailingChatOpenAI(FakeChatOpenAI):
    def _create(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("chat provider leaked chat-key")


class FailingStreamResponse:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        raise RuntimeError("stream provider leaked chat-key")

    async def aiter_lines(self):
        yield ""


class FakeAsyncClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, *args, **kwargs):
        return FailingStreamResponse()


def load_embedding_provider_module(testcase: unittest.TestCase, settings_obj, openai_cls):
    stub_names = ["app.config", "openai", "app.core.provider_errors", "app.memory.embedding_provider"]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    config_module = types.ModuleType("app.config")
    config_module.settings = settings_obj
    sys.modules["app.config"] = config_module

    openai_module = types.ModuleType("openai")
    openai_module.OpenAI = openai_cls
    sys.modules["openai"] = openai_module

    sys.modules.pop("app.core.provider_errors", None)
    sys.modules.pop("app.memory.embedding_provider", None)
    return importlib.import_module("app.memory.embedding_provider")


def load_model_router_module(testcase: unittest.TestCase, settings_obj, openai_cls):
    stub_names = ["app.config", "openai", "app.core.provider_errors", "app.core.model_router"]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    config_module = types.ModuleType("app.config")
    config_module.settings = settings_obj
    sys.modules["app.config"] = config_module

    openai_module = types.ModuleType("openai")
    openai_module.OpenAI = openai_cls
    sys.modules["openai"] = openai_module

    sys.modules.pop("app.core.provider_errors", None)
    sys.modules.pop("app.core.model_router", None)
    return importlib.import_module("app.core.model_router")


def provider_settings(**overrides):
    defaults = {
        "openai_api_key": None,
        "openai_base_url": "https://api.openai.com/v1",
        "openai_model": "gpt-test",
        "minimax_api_key": None,
        "minimax_base_url": None,
        "minimax_model": None,
        "embedding_provider": "openai-compatible",
        "embedding_api_key": "emb-key",
        "embedding_base_url": "https://emb.example/v1",
        "embedding_model": "text-embedding-test",
        "provider_timeout_seconds": 12.5,
        "provider_retry_attempts": 2,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ProviderReliabilityTests(unittest.TestCase):
    def test_embedding_provider_applies_timeout_and_retries_transient_failure(self):
        module = load_embedding_provider_module(self, provider_settings(), FakeEmbeddingOpenAI)

        provider = module.build_embedding_provider()
        vectors = provider.embed_texts(["hello"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3]])
        self.assertEqual(provider.client.timeout, 12.5)
        self.assertEqual(provider.client.max_retries, 0)
        self.assertEqual(provider.client.calls, 2)

    def test_embedding_provider_wraps_failures_without_leaking_secret(self):
        module = load_embedding_provider_module(self, provider_settings(), FailingEmbeddingOpenAI)

        provider = module.build_embedding_provider()
        with self.assertRaises(module.ProviderRequestError) as ctx:
            provider.embed_texts(["hello"])

        self.assertIn("embedding provider request failed", str(ctx.exception))
        self.assertNotIn("emb-key", str(ctx.exception))

    def test_model_router_applies_timeout_and_retry_config_to_openai_client(self):
        module = load_model_router_module(
            self,
            provider_settings(openai_api_key="chat-key", provider_retry_attempts=3),
            FakeChatOpenAI,
        )

        router = module.ModelRouter()
        answer = router.chat([{"role": "user", "content": "hello"}])

        self.assertEqual(answer, "model answer")
        self.assertEqual(router._client.timeout, 12.5)
        self.assertEqual(router._client.max_retries, 0)
        self.assertEqual(router._client.calls[0]["model"], "gpt-test")

    def test_model_router_wraps_provider_failures_without_leaking_secret(self):
        module = load_model_router_module(
            self,
            provider_settings(openai_api_key="chat-key", provider_retry_attempts=1),
            FailingChatOpenAI,
        )

        router = module.ModelRouter()
        with self.assertRaises(module.ProviderRequestError) as ctx:
            router.chat([{"role": "user", "content": "hello"}])

        self.assertIn("model provider request failed", str(ctx.exception))
        self.assertNotIn("chat-key", str(ctx.exception))

    def test_minimax_stream_wraps_status_failures_without_leaking_secret(self):
        module = load_model_router_module(
            self,
            provider_settings(
                openai_api_key="chat-key",
                openai_base_url="https://api.minimax.example",
                provider_retry_attempts=1,
            ),
            FakeChatOpenAI,
        )
        module.httpx.AsyncClient = FakeAsyncClient

        router = module.ModelRouter()

        async def consume_stream():
            return [chunk async for chunk in router.chat_stream([{"role": "user", "content": "hello"}])]

        with self.assertRaises(module.ProviderRequestError) as ctx:
            asyncio.run(consume_stream())

        self.assertIn("model provider request failed", str(ctx.exception))
        self.assertNotIn("chat-key", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
