from app.memory.memory_schema import MemoryCandidate


def normalize_memory_type(memory_type: str) -> str:
    """在记忆身份比较前规范化 memory type。"""
    return memory_type.strip().lower()


def normalize_memory_title(title: str) -> str:
    """在记忆身份比较前规范化 title。"""
    return title.strip()


def build_memory_identity(user_id: str, project_id: str, candidate: MemoryCandidate) -> dict[str, str]:
    """定义一条长期记忆的稳定身份，用于 update-or-create。"""
    return {
        "user_id": user_id,
        "project_id": project_id,
        "memory_type": normalize_memory_type(candidate.memory_type),
        "title": normalize_memory_title(candidate.title),
    }
