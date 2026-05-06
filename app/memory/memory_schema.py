from pydantic import BaseModel, Field


class MemoryCandidate(BaseModel):
    memory_type: str = "learning"
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    importance: int = 5
    obsidian_path: str | None = None
