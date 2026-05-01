from pydantic import BaseModel, Field
from typing import Any


class ChatRequest(BaseModel):
    user_id: str
    project_id: str
    session_id: str
    message: str
    mode: str = "chat"


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    memory_used: list[dict[str, Any]] = Field(default_factory=list)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class TaskRequest(BaseModel):
    user_id: str
    project_id: str
    session_id: str
    task: str
    agents: list[str] = Field(default_factory=list)


class MemoryIngestRequest(BaseModel):
    user_id: str
    project_id: str
    session_id: str
    content: str
    memory_type: str = "learning"
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    importance: int = 5


class OpenAICompatMessage(BaseModel):
    role: str
    content: str


class OpenAICompatChatRequest(BaseModel):
    model: str
    messages: list[OpenAICompatMessage] = Field(default_factory=list)
    stream: bool = False
    user: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
