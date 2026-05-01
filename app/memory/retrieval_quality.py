import json
import math
from pathlib import Path
from typing import Any


def load_retrieval_quality_cases(path: str | Path) -> dict[str, Any]:
    """Load and validate retrieval quality fixture data."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("memories"):
        raise ValueError("retrieval quality fixture must include memories")
    if not data.get("queries"):
        raise ValueError("retrieval quality fixture must include queries")
    return data


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two vectors with the same dimension."""
    if len(left) != len(right):
        raise ValueError(f"vector dimension mismatch: left={len(left)} right={len(right)}")

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    return dot_product / (left_norm * right_norm)


def rank_memories(provider: Any, memories: list[dict[str, Any]], query: str, top_k: int) -> list[dict[str, Any]]:
    """Rank memories by embedding similarity for a single query."""
    texts = [memory["content"] for memory in memories]
    memory_vectors = provider.embed_texts(texts)
    query_vector = provider.embed_texts([query])[0]

    ranked = []
    for memory, vector in zip(memories, memory_vectors):
        ranked.append(
            {
                "id": memory["id"],
                "score": cosine_similarity(query_vector, vector),
                "content": memory["content"],
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]


def evaluate_retrieval_quality(provider: Any, cases: dict[str, Any], top_k: int | None = None) -> dict[str, Any]:
    """Evaluate top-k retrieval hit rate for a fixture and embedding provider."""
    effective_top_k = top_k or int(cases.get("top_k", 3))
    query_reports = []
    hits = 0

    for query in cases["queries"]:
        ranked = rank_memories(provider, cases["memories"], query["query"], effective_top_k)
        top_ids = [item["id"] for item in ranked]
        expected_ids = list(query["expected_ids"])
        hit = bool(set(expected_ids).intersection(top_ids))
        if hit:
            hits += 1
        query_reports.append(
            {
                "id": query["id"],
                "query": query["query"],
                "expected_ids": expected_ids,
                "top_ids": top_ids,
                "hit": hit,
                "ranked": ranked,
            }
        )

    total = len(cases["queries"])
    return {
        "top_k": effective_top_k,
        "total_queries": total,
        "hits": hits,
        "hit_rate": hits / total if total else 0.0,
        "queries": query_reports,
    }
