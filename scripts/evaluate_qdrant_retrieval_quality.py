from argparse import ArgumentParser
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.memory.retrieval_quality import load_retrieval_quality_cases
from app.memory.vector_store import VectorStore


DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_quality_cases.json"
POINT_NAMESPACE = uuid.UUID("b95bd71e-0b86-43f7-a55a-5a4fdfef5876")


def evaluate_qdrant_retrieval_quality(
    store: VectorStore,
    cases: dict,
    user_id: str,
    project_id: str,
    top_k: int | None = None,
) -> dict:
    effective_top_k = top_k or int(cases.get("top_k", 3))

    for memory in cases["memories"]:
        point_id = str(uuid.uuid5(POINT_NAMESPACE, f"{user_id}:{project_id}:{memory['id']}"))
        payload = {
            "id": memory["id"],
            "user_id": user_id,
            "project_id": project_id,
            "session_id": "retrieval-quality",
            "memory_type": "quality_fixture",
            "title": memory["id"],
            "tags": ["retrieval-quality"],
        }
        store.upsert_memory(memory["content"], payload, point_id=point_id)

    query_reports = []
    hits = 0
    for query in cases["queries"]:
        results = store.search(query=query["query"], user_id=user_id, project_id=project_id, top_k=effective_top_k)
        top_ids = [result["payload"].get("id") for result in results]
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
                "results": results,
            }
        )

    total = len(cases["queries"])
    return {
        "top_k": effective_top_k,
        "user_id": user_id,
        "project_id": project_id,
        "total_queries": total,
        "hits": hits,
        "hit_rate": hits / total if total else 0.0,
        "queries": query_reports,
    }


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Evaluate retrieval quality through Qdrant VectorStore.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Path to retrieval_quality_cases.json")
    parser.add_argument("--top-k", type=int, default=None, help="Override fixture top_k")
    parser.add_argument("--user-id", default="retrieval-quality", help="Isolated user_id for evaluation points")
    parser.add_argument("--project-id", default="retrieval-quality", help="Isolated project_id for evaluation points")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> None:
    args = parse_args().parse_args()
    cases = load_retrieval_quality_cases(args.fixture)
    report = evaluate_qdrant_retrieval_quality(
        VectorStore(),
        cases,
        user_id=args.user_id,
        project_id=args.project_id,
        top_k=args.top_k,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(
        "qdrant retrieval quality: "
        f"hits={report['hits']}/{report['total_queries']} "
        f"hit_rate={report['hit_rate']:.2f} "
        f"top_k={report['top_k']}"
    )
    for query in report["queries"]:
        status = "hit" if query["hit"] else "miss"
        print(f"- {query['id']}: {status} expected={query['expected_ids']} top={query['top_ids']}")


if __name__ == "__main__":
    main()
