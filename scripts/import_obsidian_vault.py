from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.memory.obsidian_importer import ObsidianImporter


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Import an Obsidian vault into Personal AI OS memories.")
    parser.add_argument("--user-id", required=True, help="Target user scope")
    parser.add_argument("--project-id", required=True, help="Target project scope")
    parser.add_argument("--vault-path", default=None, help="Override OBSIDIAN_VAULT_PATH")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    return parser


def main() -> None:
    args = parse_args().parse_args()
    db = SessionLocal()
    try:
        imported = ObsidianImporter(vault_path=args.vault_path).import_vault(db, args.user_id, args.project_id)
    finally:
        db.close()

    report = {"imported": imported, "user_id": args.user_id, "project_id": args.project_id}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"obsidian import complete: imported={imported} user_id={args.user_id} project_id={args.project_id}")


if __name__ == "__main__":
    main()
