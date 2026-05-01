import importlib
import logging
import sys
import types
import unittest
from types import SimpleNamespace


class FakeOpenAI:
    def __init__(self, api_key=None, base_url=None, timeout=None, max_retries=None):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.embeddings = SimpleNamespace(create=self._create)
        self.calls = []

    def _create(self, model=None, input=None):
        self.calls.append({"model": model, "input": input})
        return SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[0.1, 0.2, 0.3]),
                SimpleNamespace(embedding=[0.4, 0.5, 0.6]),
            ]
        )


def load_embedding_provider_module(testcase: unittest.TestCase, settings_obj, openai_cls=FakeOpenAI):
    stub_names = [
        "app.config",
        "openai",
        "app.memory.embedding_provider",
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
    config_module.settings = settings_obj
    sys.modules["app.config"] = config_module

    openai_module = types.ModuleType("openai")
    openai_module.OpenAI = openai_cls
    sys.modules["openai"] = openai_module

    sys.modules.pop("app.memory.embedding_provider", None)
    return importlib.import_module("app.memory.embedding_provider")


class EmbeddingProviderTests(unittest.TestCase):
    def test_mock_provider_returns_deterministic_vectors(self):
        settings_obj = SimpleNamespace(
            embedding_provider="mock",
            embedding_api_key=None,
            embedding_base_url=None,
            embedding_model=None,
        )
        module = load_embedding_provider_module(self, settings_obj)

        provider = module.build_embedding_provider()
        vectors = provider.embed_texts(["abc", "abc"])

        self.assertEqual(vectors[0], vectors[1])
        self.assertEqual(len(vectors[0]), 384)

    def test_openai_compatible_provider_requires_complete_config(self):
        settings_obj = SimpleNamespace(
            embedding_provider="openai-compatible",
            embedding_api_key=None,
            embedding_base_url="https://example.com/v1",
            embedding_model="text-embedding-3-small",
        )
        module = load_embedding_provider_module(self, settings_obj)

        with self.assertLogs("app.memory.embedding_provider", level="ERROR") as logs:
            with self.assertRaises(ValueError) as ctx:
                module.build_embedding_provider()

        self.assertIn("embedding provider config is incomplete", str(ctx.exception))
        self.assertTrue(
            any("embedding provider config is incomplete" in message for message in logs.output),
            logs.output,
        )

    def test_openai_compatible_provider_uses_openai_client(self):
        settings_obj = SimpleNamespace(
            embedding_provider="openai-compatible",
            embedding_api_key="emb-key",
            embedding_base_url="https://example.com/v1",
            embedding_model="text-embedding-3-small",
        )
        module = load_embedding_provider_module(self, settings_obj)

        provider = module.build_embedding_provider()
        vectors = provider.embed_texts(["first", "second"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        self.assertEqual(provider.client.api_key, "emb-key")
        self.assertEqual(provider.client.base_url, "https://example.com/v1")
        self.assertEqual(
            provider.client.calls,
            [{"model": "text-embedding-3-small", "input": ["first", "second"]}],
        )


if __name__ == "__main__":
    unittest.main()
