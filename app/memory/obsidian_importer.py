import logging
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.memory.memory_pipeline import MemoryPipeline
from app.memory.memory_schema import MemoryCandidate

logger = logging.getLogger(__name__)

# 简单的正则用于提取 YAML frontmatter
FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


@dataclass(frozen=True)
class ObsidianImportResult:
    scanned: int
    imported: int
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run: bool = False
    items: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, int | bool | list[dict[str, str]]]:
        return {
            "scanned": self.scanned,
            "imported": self.imported,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "items": self.items or [],
        }


class ObsidianImporter:
    """从 Obsidian Vault 中单向导入 Markdown 文件作为记忆。"""

    def __init__(self, vault_path: str | None = None, pipeline: MemoryPipeline | None = None) -> None:
        self.vault = Path(vault_path or settings.obsidian_vault_path)
        self.pipeline = pipeline or MemoryPipeline()

    def import_vault(
        self,
        db: Session,
        user_id: str,
        project_id: str,
        session_id: str = "obsidian_import",
        dry_run: bool = False,
    ) -> ObsidianImportResult:
        """扫描并导入整个 Vault，返回增量报告。"""
        if not self.vault.exists():
            logger.warning("Obsidian vault path does not exist: %s", self.vault)
            return _build_result([], dry_run=dry_run)

        items: list[dict[str, str]] = []
        planned: list[tuple[MemoryCandidate, dict[str, str]]] = []
        for md_file in scan_markdown_files(self.vault):
            try:
                candidate = parse_obsidian_file(md_file)
            except Exception as exc:
                logger.error("Failed to parse obsidian file %s: %s", md_file, exc)
                items.append({"path": _display_path(md_file, self.vault), "status": "failed", "error": str(exc)})
                continue
            if candidate is None:
                continue

            item = {
                "path": _display_path(md_file, self.vault),
                "status": _candidate_status(db, user_id, project_id, candidate),
            }
            items.append(item)
            planned.append((candidate, item))

        if dry_run:
            return _build_result(items, dry_run=True)

        for candidate, item in planned:
            if item["status"] == "unchanged":
                continue
            try:
                saved = self.pipeline.persist(db, user_id, project_id, session_id, [candidate])
            except Exception as exc:
                item["status"] = "failed"
                item["error"] = str(exc)
                continue
            if not saved:
                item["status"] = "skipped"
        return _build_result(items, dry_run=False)

    def _parse_file(self, path: Path) -> MemoryCandidate | None:
        return parse_obsidian_file(path)


def scan_markdown_files(vault_path: str | Path) -> list[Path]:
    vault = Path(vault_path)
    if not vault.is_dir():
        raise ValueError("vault path is not a directory")

    files: list[Path] = []
    for path in vault.rglob("*.md"):
        if not path.is_file():
            continue
        relative = path.relative_to(vault)
        if any(part.startswith(".") for part in relative.parts):
            continue
        files.append(path)
    return sorted(files)


def parse_obsidian_file(path: Path) -> MemoryCandidate | None:
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return None

    title = path.stem
    memory_type = "obsidian_manual"
    tags: list[str] = []
    importance = 5
    body = content

    match = FRONTMATTER_PATTERN.match(content)
    if match:
        frontmatter = match.group(1)
        body = content[match.end():].strip()

        # 简单解析 key: value
        for line in frontmatter.split("\n"):
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip().strip("\"'")

            if key == "title":
                title = val or title
            elif key == "type":
                memory_type = val
            elif key == "importance":
                try:
                    importance = int(val)
                except ValueError:
                    pass
            elif key == "tags":
                # 处理列表 [tag1, tag2] 或单行逗号分隔
                tags_match = re.search(r"\[(.*?)\]", val)
                if tags_match:
                    tags = [t.strip().strip("\"'") for t in tags_match.group(1).split(",") if t.strip()]
                else:
                    tags = [t.strip().strip("\"'") for t in val.split(",") if t.strip()]

    if title == path.stem:
        h1 = re.search(r"(?m)^#\s+(.+?)\s*$", body)
        if h1:
            title = h1.group(1).strip()

    summary = re.search(r"(?ms)^## Summary\s*\n(.*?)(?:\n##\s|\Z)", body)
    if summary:
        body = summary.group(1).strip()

    return MemoryCandidate(
        memory_type=memory_type,
        title=title,
        content=body,
        tags=tags,
        importance=importance,
        obsidian_path=str(path.absolute()),
    )


def _candidate_status(db: Session, user_id: str, project_id: str, candidate: MemoryCandidate) -> str:
    from app.db.models import Memory
    from app.memory.memory_identity import build_memory_identity

    identity = build_memory_identity(user_id, project_id, candidate)
    existing = db.query(Memory).filter_by(**identity).first()
    if existing is None:
        return "created"
    if existing.content == candidate.content:
        return "unchanged"
    return "updated"


def _build_result(items: list[dict[str, str]], *, dry_run: bool) -> ObsidianImportResult:
    counts = {
        "created": _count_status(items, "created"),
        "updated": _count_status(items, "updated"),
        "unchanged": _count_status(items, "unchanged"),
        "skipped": _count_status(items, "skipped"),
        "failed": _count_status(items, "failed"),
    }
    imported = counts["created"] + counts["updated"] if not dry_run else 0
    return ObsidianImportResult(
        scanned=len(items),
        imported=imported,
        dry_run=dry_run,
        items=items,
        **counts,
    )


def _count_status(items: list[dict[str, str]], status: str) -> int:
    return sum(1 for item in items if item["status"] == status)


def _display_path(path: Path, vault: Path) -> str:
    try:
        return path.relative_to(vault).as_posix()
    except ValueError:
        return str(path)
