from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, func


revision = "0004_obsidian_sync_states"
description = "create obsidian sync state table"

metadata = MetaData()

obsidian_sync_states = Table(
    "obsidian_sync_states",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("memory_id", Integer, nullable=False, index=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("project_id", String(128), nullable=False, index=True),
    Column("obsidian_path", Text, nullable=False, index=True),
    Column("file_hash", String(64), nullable=False),
    Column("memory_hash", String(64), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("last_synced_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def upgrade(connection) -> None:
    metadata.create_all(bind=connection)


def downgrade(connection) -> None:
    metadata.drop_all(bind=connection)
