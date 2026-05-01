from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.memory.embedding_provider import build_embedding_provider
from app.memory.retrieval_quality import evaluate_retrieval_quality, load_retrieval_quality_cases


DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_quality_cases.json"


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Evaluate retrieval quality against a golden dataset.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Path to retrieval_quality_cases.json")
    parser.add_argument("--top-k", type=int, default=None, help="Override fixture top_k")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> None:
    args = parse_args().parse_args()
    provider = build_embedding_provider()
    cases = load_retrieval_quality_cases(args.fixture)
    report = evaluate_retrieval_quality(provider, cases, top_k=args.top_k)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(
        "retrieval quality: "
        f"hits={report['hits']}/{report['total_queries']} "
        f"hit_rate={report['hit_rate']:.2f} "
        f"top_k={report['top_k']}"
    )
    for query in report["queries"]:
        status = "hit" if query["hit"] else "miss"
        print(f"- {query['id']}: {status} expected={query['expected_ids']} top={query['top_ids']}")


if __name__ == "__main__":
    main()
