import json
from pathlib import Path
import subprocess
import sys
import unittest

from app.memory.retrieval_quality import (
    cosine_similarity,
    evaluate_retrieval_quality,
    load_retrieval_quality_cases,
    rank_memories,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_quality_cases.json"
EVALUATE_SCRIPT = ROOT / "scripts" / "evaluate_retrieval_quality.py"


class StaticEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]


class RetrievalQualityTests(unittest.TestCase):
    def test_fixture_shape_is_valid(self):
        cases = load_retrieval_quality_cases(FIXTURE)

        self.assertEqual(cases["top_k"], 2)
        self.assertEqual(len(cases["memories"]), 3)
        self.assertEqual(len(cases["queries"]), 3)
        self.assertTrue(all(memory["id"] for memory in cases["memories"]))
        self.assertTrue(all(query["expected_ids"] for query in cases["queries"]))

    def test_cosine_similarity_rejects_dimension_mismatch(self):
        with self.assertRaisesRegex(ValueError, "vector dimension mismatch"):
            cosine_similarity([1.0, 0.0], [1.0])

    def test_rank_memories_orders_by_similarity(self):
        memories = [
            {"id": "a", "content": "alpha"},
            {"id": "b", "content": "beta"},
        ]
        provider = StaticEmbeddingProvider(
            {
                "alpha": [1.0, 0.0],
                "beta": [0.0, 1.0],
                "query": [0.9, 0.1],
            }
        )

        ranked = rank_memories(provider, memories, "query", top_k=2)

        self.assertEqual([item["id"] for item in ranked], ["a", "b"])
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])

    def test_evaluate_retrieval_quality_reports_hit_rate(self):
        cases = {
            "top_k": 1,
            "memories": [
                {"id": "rag", "content": "rag memory"},
                {"id": "webui", "content": "webui memory"},
            ],
            "queries": [
                {"id": "q-rag", "query": "rag query", "expected_ids": ["rag"]},
                {"id": "q-webui", "query": "webui query", "expected_ids": ["webui"]},
            ],
        }
        provider = StaticEmbeddingProvider(
            {
                "rag memory": [1.0, 0.0],
                "webui memory": [0.0, 1.0],
                "rag query": [0.8, 0.2],
                "webui query": [0.1, 0.9],
            }
        )

        report = evaluate_retrieval_quality(provider, cases)

        self.assertEqual(report["total_queries"], 2)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["hits"], 2)
        self.assertEqual(report["misses"], 0)
        self.assertEqual(report["hit_rate"], 1.0)
        self.assertEqual(report["queries"][0]["top_ids"], ["rag"])

    def test_evaluate_retrieval_quality_honors_top_k_override(self):
        cases = {
            "top_k": 1,
            "memories": [
                {"id": "wrong", "content": "wrong memory"},
                {"id": "right", "content": "right memory"},
            ],
            "queries": [
                {"id": "q", "query": "ambiguous query", "expected_ids": ["right"]},
            ],
        }
        provider = StaticEmbeddingProvider(
            {
                "wrong memory": [1.0, 0.0],
                "right memory": [0.8, 0.2],
                "ambiguous query": [1.0, 0.0],
            }
        )

        top_1_report = evaluate_retrieval_quality(provider, cases, top_k=1)
        top_2_report = evaluate_retrieval_quality(provider, cases, top_k=2)

        self.assertFalse(top_1_report["queries"][0]["hit"])
        self.assertTrue(top_2_report["queries"][0]["hit"])


def test_fixture_is_json_serializable():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["memories"]
    assert payload["queries"]


def test_evaluate_retrieval_quality_script_accepts_min_hit_rate():
    result = subprocess.run(
        [
            sys.executable,
            str(EVALUATE_SCRIPT),
            "--fixture",
            str(FIXTURE),
            "--min-hit-rate",
            "1.0",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "hit_rate=1.00" in result.stdout
    assert "min_hit_rate=1.00" in result.stdout


def test_evaluate_retrieval_quality_script_fails_when_min_hit_rate_not_met():
    result = subprocess.run(
        [
            sys.executable,
            str(EVALUATE_SCRIPT),
            "--fixture",
            str(FIXTURE),
            "--min-hit-rate",
            "1.01",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "hit_rate 1.00 is below min_hit_rate 1.01" in result.stderr


def test_evaluate_retrieval_quality_json_report_has_stable_summary_schema():
    result = subprocess.run(
        [sys.executable, str(EVALUATE_SCRIPT), "--fixture", str(FIXTURE), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    for key in ["hit_rate", "total", "hits", "misses", "top_k"]:
        assert key in payload


class FakeVectorStore:
    def __init__(self) -> None:
        self.memories: list[dict] = []

    def upsert_memory(self, content: str, payload: dict, point_id: str | None = None) -> None:
        self.memories.append({"content": content, "payload": payload, "point_id": point_id})

    def search(self, query: str, user_id: str, project_id: str, top_k: int) -> list[dict]:
        expected_id = query.replace("find ", "")
        ordered = sorted(
            self.memories,
            key=lambda item: item["payload"]["id"] != expected_id,
        )
        return [{"payload": item["payload"]} for item in ordered[:top_k]]


def test_qdrant_retrieval_quality_report_has_stable_summary_schema():
    from scripts.evaluate_qdrant_retrieval_quality import evaluate_qdrant_retrieval_quality

    cases = {
        "top_k": 1,
        "memories": [
            {"id": "rag", "content": "rag memory"},
            {"id": "webui", "content": "webui memory"},
        ],
        "queries": [
            {"id": "q-rag", "query": "find rag", "expected_ids": ["rag"]},
            {"id": "q-webui", "query": "find webui", "expected_ids": ["webui"]},
        ],
    }

    report = evaluate_qdrant_retrieval_quality(FakeVectorStore(), cases, "u", "p")

    assert report["total"] == 2
    assert report["hits"] == 2
    assert report["misses"] == 0
    assert report["hit_rate"] == 1.0
    assert report["top_k"] == 1
