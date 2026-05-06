from pathlib import Path
from datetime import UTC, datetime
from slugify import slugify
from app.config import settings
from app.memory.memory_schema import MemoryCandidate


class ObsidianWriter:
    def __init__(self, vault_path: str | None = None) -> None:
        self.vault = Path(vault_path or settings.obsidian_vault_path)

    def write_memory(self, user_id: str, project_id: str, session_id: str, memory: MemoryCandidate) -> str:
        folder = self.vault / "10-Projects" / project_id / "Notes"
        folder.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        filename = f"{ts}-{slugify(memory.title)[:80]}.md"
        path = folder / filename

        path.write_text(render_memory_markdown(user_id, project_id, session_id, memory), encoding="utf-8")
        return str(path)

    def write_existing_memory(self, path: str, user_id: str, project_id: str, session_id: str, memory: MemoryCandidate) -> str:
        target = Path(path).resolve()
        vault = self.vault.resolve()
        try:
            target.relative_to(vault)
        except ValueError as exc:
            raise ValueError("path is outside configured obsidian vault") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_memory_markdown(user_id, project_id, session_id, memory), encoding="utf-8")
        return str(target)


def render_memory_markdown(user_id: str, project_id: str, session_id: str, memory: MemoryCandidate) -> str:
    tags = ", ".join(memory.tags)
    return (
        f"---\n"
        f"title: \"{memory.title}\"\n"
        f"type: {memory.memory_type}\n"
        f"user_id: {user_id}\n"
        f"project_id: {project_id}\n"
        f"session_id: {session_id}\n"
        f"tags: [{tags}]\n"
        f"importance: {memory.importance}\n"
        f"created_at: {datetime.now(UTC).isoformat()}\n"
        f"source: personal-ai-os\n"
        f"---\n\n"
        f"# {memory.title}\n\n"
        f"## Summary\n{memory.content}\n\n"
        f"## Context\n来自 `{session_id}` 的对话或任务沉淀。\n\n"
        f"## Links\n- Project: [[{project_id}]]\n"
    )
