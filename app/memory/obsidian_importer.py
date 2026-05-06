import logging
import re
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings
from app.memory.memory_pipeline import MemoryPipeline
from app.memory.memory_schema import MemoryCandidate

logger = logging.getLogger(__name__)

# 简单的正则用于提取 YAML frontmatter
FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class ObsidianImporter:
    """从 Obsidian Vault 中单向导入 Markdown 文件作为记忆。"""

    def __init__(self, vault_path: str | None = None) -> None:
        self.vault = Path(vault_path or settings.obsidian_vault_path)
        self.pipeline = MemoryPipeline()

    def import_vault(self, db: Session, user_id: str, project_id: str) -> int:
        """扫描并导入整个 Vault。返回新导入或更新的记忆数量。"""
        if not self.vault.exists():
            logger.warning("Obsidian vault path does not exist: %s", self.vault)
            return 0

        candidates = []
        # 递归寻找所有 .md 文件，排除隐藏目录（如 .obsidian）
        for md_file in self.vault.rglob("*.md"):
            if any(part.startswith(".") for part in md_file.parts):
                continue
            
            try:
                candidate = self._parse_file(md_file)
                if candidate:
                    candidates.append(candidate)
            except Exception as e:
                logger.error("Failed to parse obsidian file %s: %s", md_file, e)

        if not candidates:
            return 0

        # 调用 pipeline 持久化。session_id 使用 "obsidian_import"
        # 注意：MemoryPipeline.persist 内部会处理 update-or-create
        saved = self.pipeline.persist(db, user_id, project_id, "obsidian_import", candidates)
        return len(saved)

    def _parse_file(self, path: Path) -> MemoryCandidate | None:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return None

        title = path.stem
        memory_type = "obsidian_manual"
        tags = []
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
                val = val.strip()
                
                if key == "type":
                    memory_type = val
                elif key == "importance":
                    try:
                        importance = int(val)
                    except ValueError:
                        pass
                elif key == "tags":
                    # 处理列表 [tag1, tag2] 或多行
                    tags_match = re.search(r"\[(.*?)\]", val)
                    if tags_match:
                        tags = [t.strip() for t in tags_match.group(1).split(",") if t.strip()]
                    else:
                        # 暂时不支持复杂的 YAML 列表解析，仅处理单行逗号分隔
                        tags = [t.strip() for t in val.split(",") if t.strip()]

        return MemoryCandidate(
            memory_type=memory_type,
            title=title,
            content=body,
            tags=tags,
            importance=importance,
            obsidian_path=str(path.absolute())
        )
