from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config_validation import validate_runtime_config


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Validate Personal AI OS runtime configuration.")
    parser.add_argument("--strict", action="store_true", help="Treat local-only defaults as errors")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> int:
    args = parse_args().parse_args()
    report = validate_runtime_config(strict=True if args.strict else None)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        strict_label = "strict" if report["strict"] else "non-strict"
        print(f"runtime config: {report['status']} ({strict_label})")
        for check in report["checks"]:
            print(f"- {check['name']}: {check['status']} - {check['message']}")

    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
