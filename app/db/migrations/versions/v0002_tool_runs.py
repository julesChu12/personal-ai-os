from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, func


revision = "0002_tool_runs"
description = "create tool runs audit table"

metadata = MetaData()

tool_runs = Table(
    "tool_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("project_id", String(128), nullable=False, index=True),
    Column("session_id", String(128), nullable=True, index=True),
    Column("tool_name", String(128), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column("input_payload", JSON, nullable=True),
    Column("output", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("request_id", String(128), nullable=True, index=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def upgrade(connection) -> None:
    metadata.create_all(bind=connection)


def downgrade(connection) -> None:
    metadata.drop_all(bind=connection)
