from pathlib import Path
from datetime import datetime
from slugify import slugify
from app.config import settings
from app.memory.memory_schema import MemoryCandidate


class ObsidianWriter:
    def __init__(self, vault_path: str | None = None) -> None:
        self.vault = Path(vault_path or settings.obsidian_vault_path)

    def write_memory(self, user_id: str, project_id: str, session_id: str, memory: MemoryCandidate) -> str:
        folder = self.vault / "10-Projects" / project_id / "Notes"
        folder.mkdir(parents=True, exist_ok=True)

        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"{ts}-{slugify(memory.title)[:80]}.md"
        path = folder / filename

        tags = "\n".join([f"  - {tag}" for tag in memory.tags])
        content = (
            f"---\n"
            f"type: {memory.memory_type}\n"
            f"user_id: {user_id}\n"
            f"project_id: {project_id}\n"
            f"session_id: {session_id}\n"
            f"tags:\n{tags}\n"
            f"importance: {memory.importance}\n"
            f"created_at: {datetime.utcnow().isoformat()}\n"
            f"source: personal-ai-os\n"
            f"---\n\n"
            f"# {memory.title}\n\n"
            f"## Summary\n{memory.content}\n\n"
            f"## Context\n来自 `{session_id}` 的对话或任务沉淀。\n\n"
            f"## Links\n- Project: [[{project_id}]]\n"
        )
        path.write_text(content, encoding="utf-8")
        return str(path)
