from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.memory.obsidian_importer import ObsidianImportResult, ObsidianImporter


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Import an Obsidian vault into Personal AI OS memories.")
    parser.add_argument("--user-id", required=True, help="Target user scope")
    parser.add_argument("--project-id", required=True, help="Target project scope")
    parser.add_argument("--vault-path", default=None, help="Override OBSIDIAN_VAULT_PATH")
    parser.add_argument("--session-id", default="obsidian_import", help="Import session id")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report planned changes without persisting")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> None:
    args = parse_args().parse_args()
    importer = ObsidianImporter(vault_path=args.vault_path)
    with SessionLocal() as db:
        result = importer.import_vault(
            db,
            args.user_id,
            args.project_id,
            session_id=args.session_id,
            dry_run=args.dry_run,
        )

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return
    print(format_result(result))


def format_result(result: ObsidianImportResult) -> str:
    return (
        "obsidian import"
        + (" (dry-run)" if result.dry_run else "")
        + f": scanned={result.scanned}"
        + f" imported={result.imported}"
        + f" created={result.created}"
        + f" updated={result.updated}"
        + f" unchanged={result.unchanged}"
        + f" skipped={result.skipped}"
        + f" failed={result.failed}"
    )


if __name__ == "__main__":
    main()
