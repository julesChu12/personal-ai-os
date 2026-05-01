import importlib
import sys
import types
import unittest


def load_retriever_module(testcase: unittest.TestCase, vector_store_cls):
    stub_names = [
        "app.memory.vector_store",
        "app.memory.retriever",
    ]
    originals = {name: sys.modules.get(name) for name in stub_names}

    def restore_modules():
        for name, module in originals.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    testcase.addCleanup(restore_modules)

    vector_store_module = types.ModuleType("app.memory.vector_store")
    vector_store_module.VectorStore = vector_store_cls
    sys.modules["app.memory.vector_store"] = vector_store_module
    sys.modules.pop("app.memory.retriever", None)

    return importlib.import_module("app.memory.retriever")


class WorkingVectorStore:
    def search(self, query: str, user_id: str, project_id: str, top_k: int = 5) -> list[dict]:
        return [
            {
                "score": 0.9,
                "payload": {
                    "query": query,
                    "user_id": user_id,
                    "project_id": project_id,
                    "top_k": top_k,
                },
            }
        ]


class BrokenVectorStore:
    def search(self, query: str, user_id: str, project_id: str, top_k: int = 5) -> list[dict]:
        raise RuntimeError("qdrant unavailable")


class RetrieverTests(unittest.TestCase):
    def test_search_returns_vector_store_results_when_available(self):
        retriever_module = load_retriever_module(self, WorkingVectorStore)
        retriever = retriever_module.Retriever()

        results = retriever.search("u1", "p1", "RAG", top_k=3)

        self.assertEqual(
            results,
            [
                {
                    "score": 0.9,
                    "payload": {
                        "query": "RAG",
                        "user_id": "u1",
                        "project_id": "p1",
                        "top_k": 3,
                    },
                }
            ],
        )

    def test_search_returns_empty_list_when_vector_store_is_unavailable(self):
        retriever_module = load_retriever_module(self, BrokenVectorStore)
        retriever = retriever_module.Retriever()

        with self.assertLogs("app.memory.retriever", level="WARNING") as logs:
            results = retriever.search("u1", "p1", "RAG", top_k=3)

        self.assertEqual(results, [])
        self.assertTrue(
            any("Vector search unavailable" in message and "qdrant unavailable" in message for message in logs.output),
            logs.output,
        )


if __name__ == "__main__":
    unittest.main()
