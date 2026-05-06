import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Memory, ObsidianSyncState
from app.memory.memory_pipeline import MemoryPipeline
from app.memory.memory_schema import MemoryCandidate
from app.memory.obsidian_importer import parse_obsidian_file
from app.memory.obsidian_writer import ObsidianWriter
from app.memory.vector_store import VectorStore


SYNC_STATES = {
    "unchanged",
    "vault_only",
    "db_only",
    "vault_changed",
    "db_changed",
    "both_changed",
    "vault_deleted",
    "path_missing",
}


@dataclass
class VaultFile:
    path: Path
    candidate: MemoryCandidate
    content_hash: str


class ObsidianSyncEngine:
    """Dry-run-first bidirectional sync between Obsidian markdown files and memories."""

    def __init__(
        self,
        vault_path: str | None = None,
        pipeline: MemoryPipeline | None = None,
        vector_store_factory: Callable[[], VectorStore] | None = None,
    ) -> None:
        self.vault = Path(vault_path or settings.obsidian_vault_path).resolve()
        self.pipeline = pipeline or MemoryPipeline(vector_store_factory=vector_store_factory)
        self.vector_store_factory = vector_store_factory or VectorStore
        self.writer = ObsidianWriter(str(self.vault))

    def dry_run(self, db: Session, user_id: str, project_id: str) -> dict[str, Any]:
        return self.sync(db, user_id, project_id, apply=False)

    def apply(self, db: Session, user_id: str, project_id: str) -> dict[str, Any]:
        return self.sync(db, user_id, project_id, apply=True)

    def sync(self, db: Session, user_id: str, project_id: str, apply: bool = False) -> dict[str, Any]:
        items, skipped = self._classify(db, user_id, project_id)
        report = _build_report(items, skipped, apply=apply)
        if not apply:
            return report

        applied: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = list(report["conflicts"])
        errors: list[dict[str, Any]] = []
        changed = False

        for item in items:
            state = item["state"]
            try:
                if state == "unchanged":
                    if item.get("memory") and item.get("path"):
                        self._record_state(db, item["memory"], item["path"], item["file_hash"])
                        changed = True
                    continue
                if state == "vault_only":
                    memory = self._create_memory_from_vault(db, user_id, project_id, item)
                    self._record_state(db, memory, item["path"], item["file_hash"])
                    applied.append(_public_item(item, action="create_memory", memory=memory))
                    changed = True
                    continue
                if state == "db_only":
                    memory = item["memory"]
                    path = self._write_memory_to_vault(memory, None)
                    memory.obsidian_path = str(path)
                    self._record_state(db, memory, path, memory_content_hash(memory))
                    applied.append(_public_item(item, action="create_vault_file", path=path))
                    changed = True
                    continue
                if state == "vault_changed":
                    memory = item["memory"]
                    self._update_memory_from_vault(memory, item["candidate"], item["path"])
                    self._upsert_vector(memory)
                    self._record_state(db, memory, item["path"], item["file_hash"])
                    applied.append(_public_item(item, action="update_memory"))
                    changed = True
                    continue
                if state == "db_changed":
                    memory = item["memory"]
                    path = self._write_memory_to_vault(memory, item["path"])
                    self._record_state(db, memory, path, memory_content_hash(memory))
                    applied.append(_public_item(item, action="update_vault_file", path=path))
                    changed = True
                    continue
                if state == "both_changed":
                    continue
                if state in {"vault_deleted", "path_missing"}:
                    continue
            except Exception as exc:
                errors.append({**_public_item(item), "error": str(exc)})

        if changed:
            db.commit()

        final_report = _build_report(items, skipped, apply=apply)
        final_report["applied"] = applied
        final_report["conflicts"] = conflicts
        final_report["errors"].extend(errors)
        final_report["summary"]["applied"] = len(applied)
        final_report["summary"]["errors"] = len(final_report["errors"])
        return final_report

    def _classify(self, db: Session, user_id: str, project_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        vault_files, skipped = self._scan_vault()
        items: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        memories = db.query(Memory).filter_by(user_id=user_id, project_id=project_id).all()

        for memory in memories:
            item = self._classify_memory(db, memory, vault_files)
            items.append(item)
            if item.get("path"):
                seen_paths.add(str(item["path"]))

        for path_key, vault_file in vault_files.items():
            if path_key in seen_paths:
                continue
            items.append(
                {
                    "state": "vault_only",
                    "action": "create_memory",
                    "path": vault_file.path,
                    "candidate": vault_file.candidate,
                    "file_hash": vault_file.content_hash,
                    "title": vault_file.candidate.title,
                }
            )

        return items, skipped

    def _classify_memory(
        self,
        db: Session,
        memory: Memory,
        vault_files: dict[str, VaultFile],
    ) -> dict[str, Any]:
        base = {
            "memory": memory,
            "memory_id": memory.id,
            "title": memory.title,
            "memory_hash": memory_content_hash(memory),
        }
        if not memory.obsidian_path:
            return {**base, "state": "db_only", "action": "create_vault_file"}

        path = Path(memory.obsidian_path).expanduser().resolve()
        try:
            path.relative_to(self.vault)
        except ValueError:
            return {**base, "state": "path_missing", "action": "skip", "path": path, "reason": "path outside vault"}

        path_key = str(path)
        state = db.query(ObsidianSyncState).filter_by(memory_id=memory.id).first()
        vault_file = vault_files.get(path_key)
        if vault_file is None:
            missing_state = "vault_deleted" if state else "path_missing"
            return {**base, "state": missing_state, "action": "report_only", "path": path}

        item = {
            **base,
            "path": path,
            "candidate": vault_file.candidate,
            "file_hash": vault_file.content_hash,
        }
        if state is None:
            if item["file_hash"] == item["memory_hash"]:
                return {**item, "state": "unchanged", "action": "record_state"}
            return {**item, "state": "both_changed", "action": "conflict"}

        file_changed = state.file_hash != item["file_hash"]
        memory_changed = state.memory_hash != item["memory_hash"]
        if file_changed and memory_changed:
            return {**item, "state": "both_changed", "action": "conflict"}
        if file_changed:
            return {**item, "state": "vault_changed", "action": "update_memory"}
        if memory_changed:
            return {**item, "state": "db_changed", "action": "update_vault_file"}
        return {**item, "state": "unchanged", "action": "record_state"}

    def _scan_vault(self) -> tuple[dict[str, VaultFile], list[dict[str, Any]]]:
        files: dict[str, VaultFile] = {}
        skipped: list[dict[str, Any]] = []
        if not self.vault.exists():
            return files, [{"path": str(self.vault), "reason": "vault does not exist"}]

        for md_file in self.vault.rglob("*.md"):
            if any(part.startswith(".") for part in md_file.relative_to(self.vault).parts):
                skipped.append({"path": str(md_file), "reason": "hidden path"})
                continue
            try:
                candidate = parse_obsidian_file(md_file)
            except Exception as exc:
                skipped.append({"path": str(md_file), "reason": str(exc)})
                continue
            if candidate is None:
                skipped.append({"path": str(md_file), "reason": "empty file"})
                continue
            files[str(md_file.resolve())] = VaultFile(md_file.resolve(), candidate, candidate_content_hash(candidate))
        return files, skipped

    def _create_memory_from_vault(self, db: Session, user_id: str, project_id: str, item: dict[str, Any]) -> Memory:
        saved = self.pipeline.persist(db, user_id, project_id, "obsidian_sync", [item["candidate"]])
        return saved[0]

    def _update_memory_from_vault(self, memory: Memory, candidate: MemoryCandidate, path: Path) -> None:
        memory.session_id = "obsidian_sync"
        memory.memory_type = candidate.memory_type
        memory.title = candidate.title
        memory.content = candidate.content
        memory.tags = candidate.tags
        memory.importance = candidate.importance
        memory.obsidian_path = str(path)

    def _write_memory_to_vault(self, memory: Memory, path: Path | None) -> Path:
        candidate = memory_to_candidate(memory)
        if path is None:
            return Path(self.writer.write_memory(memory.user_id, memory.project_id, memory.session_id, candidate)).resolve()
        return Path(self.writer.write_existing_memory(str(path), memory.user_id, memory.project_id, memory.session_id, candidate)).resolve()

    def _upsert_vector(self, memory: Memory) -> None:
        payload = {
            "user_id": memory.user_id,
            "project_id": memory.project_id,
            "session_id": memory.session_id,
            "memory_type": memory.memory_type,
            "title": memory.title,
            "tags": memory.tags or [],
            "obsidian_path": memory.obsidian_path,
        }
        point_id = self.vector_store_factory().upsert_memory(memory.content, payload, point_id=memory.qdrant_point_id)
        memory.qdrant_point_id = point_id

    def _record_state(self, db: Session, memory: Memory, path: Path, file_hash: str) -> ObsidianSyncState:
        state = db.query(ObsidianSyncState).filter_by(memory_id=memory.id).first()
        if state is None:
            state = ObsidianSyncState(memory_id=memory.id)
            db.add(state)
        state.user_id = memory.user_id
        state.project_id = memory.project_id
        state.obsidian_path = str(path)
        state.file_hash = file_hash
        state.memory_hash = memory_content_hash(memory)
        state.status = "ok"
        state.last_synced_at = datetime.now(UTC)
        return state


def memory_to_candidate(memory: Memory) -> MemoryCandidate:
    return MemoryCandidate(
        memory_type=memory.memory_type,
        title=memory.title,
        content=memory.content,
        tags=memory.tags or [],
        importance=memory.importance,
        obsidian_path=memory.obsidian_path,
    )


def candidate_content_hash(candidate: MemoryCandidate) -> str:
    return _hash_payload(
        {
            "memory_type": candidate.memory_type,
            "title": candidate.title,
            "content": candidate.content,
            "tags": candidate.tags,
            "importance": candidate.importance,
        }
    )


def memory_content_hash(memory: Memory) -> str:
    return _hash_payload(
        {
            "memory_type": memory.memory_type,
            "title": memory.title,
            "content": memory.content,
            "tags": memory.tags or [],
            "importance": memory.importance,
        }
    )


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_report(items: list[dict[str, Any]], skipped: list[dict[str, Any]], apply: bool) -> dict[str, Any]:
    counts = Counter(item["state"] for item in items)
    planned = [_public_item(item) for item in items if item["state"] != "unchanged"]
    conflicts = [_public_item(item) for item in items if item["state"] == "both_changed"]
    errors: list[dict[str, Any]] = []
    return {
        "mode": "apply" if apply else "dry-run",
        "summary": {
            "total": len(items),
            "planned": len(planned),
            "applied": 0,
            "conflicts": len(conflicts),
            "skipped": len(skipped) + len([item for item in items if item["state"] in {"vault_deleted", "path_missing"}]),
            "errors": 0,
            "states": {state: counts.get(state, 0) for state in sorted(SYNC_STATES)},
        },
        "planned": planned,
        "applied": [],
        "conflicts": conflicts,
        "skipped": skipped + [_public_item(item) for item in items if item["state"] in {"vault_deleted", "path_missing"}],
        "errors": errors,
    }


def _public_item(
    item: dict[str, Any],
    action: str | None = None,
    memory: Memory | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    memory_obj = memory or item.get("memory")
    candidate = item.get("candidate")
    return {
        "state": item["state"],
        "action": action or item.get("action", "report_only"),
        "memory_id": getattr(memory_obj, "id", item.get("memory_id", None)),
        "title": getattr(memory_obj, "title", None) or item.get("title") or getattr(candidate, "title", None),
        "path": str(path or item.get("path")) if path or item.get("path") else None,
        "reason": item.get("reason"),
    }
