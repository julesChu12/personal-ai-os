from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.database import engine
from app.db.migrations.runner import SCHEMA_MIGRATIONS_TABLE, apply_migrations, get_migration_status


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Run Personal AI OS database migrations.")
    parser.add_argument("--dry-run", action="store_true", help="Show migration status without applying changes")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> int:
    args = parse_args().parse_args()
    report = get_migration_status(engine) if args.dry_run else apply_migrations(engine)
    report = {
        **report,
        "schema_table": SCHEMA_MIGRATIONS_TABLE,
        "dry_run": args.dry_run,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    mode = "dry-run" if args.dry_run else "apply"
    print(f"database migrations: {report['status']} ({mode})")
    print(f"- schema_migrations table: {report['schema_table']}")
    print(f"- applied: {', '.join(report['applied']) if report['applied'] else 'none'}")
    print(f"- pending: {', '.join(report['pending']) if report['pending'] else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
