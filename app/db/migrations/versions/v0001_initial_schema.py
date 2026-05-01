from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, func


revision = "0001_initial_schema"
description = "create messages and memories tables"

metadata = MetaData()

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("project_id", String(128), nullable=False, index=True),
    Column("session_id", String(128), nullable=False, index=True),
    Column("role", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("meta", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

memories = Table(
    "memories",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("project_id", String(128), nullable=False, index=True),
    Column("session_id", String(128), nullable=False, index=True),
    Column("memory_type", String(64), nullable=False, index=True),
    Column("title", String(255), nullable=False),
    Column("content", Text, nullable=False),
    Column("tags", JSON, nullable=True),
    Column("importance", Integer, nullable=False),
    Column("obsidian_path", Text, nullable=True),
    Column("qdrant_point_id", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def upgrade(connection) -> None:
    metadata.create_all(bind=connection)


def downgrade(connection) -> None:
    metadata.drop_all(bind=connection)
