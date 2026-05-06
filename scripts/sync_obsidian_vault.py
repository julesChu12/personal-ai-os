from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.memory.obsidian_sync import ObsidianSyncEngine


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Bidirectionally sync an Obsidian vault with Personal AI OS memories.")
    parser.add_argument("--user-id", required=True, help="User id scope for imported memories")
    parser.add_argument("--project-id", required=True, help="Project id scope for imported memories")
    parser.add_argument("--vault-path", default=None, help="Override OBSIDIAN_VAULT_PATH")
    parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> int:
    args = parse_args().parse_args()
    db = SessionLocal()
    try:
        engine = ObsidianSyncEngine(vault_path=args.vault_path)
        report = engine.apply(db, args.user_id, args.project_id) if args.apply else engine.dry_run(db, args.user_id, args.project_id)
    finally:
        db.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    summary = report["summary"]
    print(
        f"obsidian sync {report['mode']}: planned={summary['planned']} "
        f"applied={summary['applied']} conflicts={summary['conflicts']} errors={summary['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
