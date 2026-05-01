from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, func


revision = "0003_agent_runs"
description = "create agent runs audit table"

metadata = MetaData()

agent_runs = Table(
    "agent_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("project_id", String(128), nullable=False, index=True),
    Column("session_id", String(128), nullable=True, index=True),
    Column("task", Text, nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("error", Text, nullable=True),
    Column("answer", Text, nullable=True),
    Column("plan_payload", JSON, nullable=True),
    Column("steps", JSON, nullable=True),
    Column("agent_trace", JSON, nullable=True),
    Column("memory_saved", Integer, nullable=False),
    Column("request_id", String(128), nullable=True, index=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def upgrade(connection) -> None:
    metadata.create_all(bind=connection)


def downgrade(connection) -> None:
    metadata.drop_all(bind=connection)
