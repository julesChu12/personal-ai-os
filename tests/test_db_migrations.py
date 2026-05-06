from sqlalchemy import create_engine, inspect, text

from app.db import database
from app.db.migrations.runner import apply_migrations, get_migration_status


def test_initial_migration_creates_current_schema_and_records_revision():
    engine = create_engine("sqlite:///:memory:")

    report = apply_migrations(engine)

    assert report["applied"] == [
        "0001_initial_schema",
        "0002_tool_runs",
        "0003_agent_runs",
        "0004_obsidian_sync_states",
    ]
    assert report["status"] == "ok"

    inspector = inspect(engine)
    assert {"messages", "memories", "tool_runs", "agent_runs", "obsidian_sync_states", "schema_migrations"}.issubset(
        set(inspector.get_table_names())
    )

    message_columns = {column["name"] for column in inspector.get_columns("messages")}
    assert {"id", "user_id", "project_id", "session_id", "role", "content", "meta", "created_at"}.issubset(
        message_columns
    )

    memory_columns = {column["name"] for column in inspector.get_columns("memories")}
    assert {
        "id",
        "user_id",
        "project_id",
        "session_id",
        "memory_type",
        "title",
        "content",
        "tags",
        "importance",
        "obsidian_path",
        "qdrant_point_id",
        "created_at",
        "updated_at",
    }.issubset(memory_columns)

    tool_run_columns = {column["name"] for column in inspector.get_columns("tool_runs")}
    assert {
        "id",
        "user_id",
        "project_id",
        "session_id",
        "tool_name",
        "status",
        "input_payload",
        "output",
        "error",
        "request_id",
        "created_at",
    }.issubset(tool_run_columns)

    agent_run_columns = {column["name"] for column in inspector.get_columns("agent_runs")}
    assert {
        "id",
        "user_id",
        "project_id",
        "session_id",
        "task",
        "status",
        "error",
        "answer",
        "plan_payload",
        "steps",
        "agent_trace",
        "memory_saved",
        "request_id",
        "created_at",
    }.issubset(agent_run_columns)

    sync_columns = {column["name"] for column in inspector.get_columns("obsidian_sync_states")}
    assert {
        "id",
        "memory_id",
        "user_id",
        "project_id",
        "obsidian_path",
        "file_hash",
        "memory_hash",
        "status",
        "last_synced_at",
    }.issubset(sync_columns)

    with engine.connect() as connection:
        revisions = connection.execute(text("select revision from schema_migrations")).scalars().all()
    assert revisions == [
        "0001_initial_schema",
        "0002_tool_runs",
        "0003_agent_runs",
        "0004_obsidian_sync_states",
    ]


def test_migrations_are_idempotent_and_report_status():
    engine = create_engine("sqlite:///:memory:")

    first_report = apply_migrations(engine)
    second_report = apply_migrations(engine)
    status = get_migration_status(engine)

    assert first_report["applied"] == [
        "0001_initial_schema",
        "0002_tool_runs",
        "0003_agent_runs",
        "0004_obsidian_sync_states",
    ]
    assert second_report["applied"] == []
    assert status["applied"] == [
        "0001_initial_schema",
        "0002_tool_runs",
        "0003_agent_runs",
        "0004_obsidian_sync_states",
    ]
    assert status["pending"] == []
    assert status["status"] == "ok"


def test_init_db_requires_migrated_schema(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(database, "engine", engine)

    try:
        database.init_db()
    except RuntimeError as exc:
        assert "Run migrations first: python scripts/run_migrations.py" in str(exc)
        assert "memories" in str(exc)
    else:
        raise AssertionError("init_db should fail when required migration tables are missing")


def test_init_db_accepts_schema_created_by_migrations(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    apply_migrations(engine)
    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
