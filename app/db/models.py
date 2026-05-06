from sqlalchemy import String, Text, DateTime, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    importance: Mapped[int] = mapped_column(Integer, default=5)
    obsidian_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ObsidianSyncState(Base):
    __tablename__ = "obsidian_sync_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    memory_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True)
    obsidian_path: Mapped[str] = mapped_column(Text, index=True)
    file_hash: Mapped[str] = mapped_column(String(64))
    memory_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="ok", index=True)
    last_synced_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ToolRun(Base):
    __tablename__ = "tool_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_payload: Mapped[dict | None] = mapped_column(JSON, default=dict)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_payload: Mapped[dict | None] = mapped_column(JSON, default=dict)
    steps: Mapped[list | None] = mapped_column(JSON, default=list)
    agent_trace: Mapped[list | None] = mapped_column(JSON, default=list)
    memory_saved: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
