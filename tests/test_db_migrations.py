from sqlalchemy import create_engine, inspect, text

from app.db.migrations.runner import apply_migrations, get_migration_status


def test_initial_migration_creates_current_schema_and_records_revision():
    engine = create_engine("sqlite:///:memory:")

    report = apply_migrations(engine)

    assert report["applied"] == ["0001_initial_schema", "0002_tool_runs", "0003_agent_runs"]
    assert report["status"] == "ok"

    inspector = inspect(engine)
    assert {"messages", "memories", "tool_runs", "agent_runs", "schema_migrations"}.issubset(
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

    with engine.connect() as connection:
        revisions = connection.execute(text("select revision from schema_migrations")).scalars().all()
    assert revisions == ["0001_initial_schema", "0002_tool_runs", "0003_agent_runs"]


def test_migrations_are_idempotent_and_report_status():
    engine = create_engine("sqlite:///:memory:")

    first_report = apply_migrations(engine)
    second_report = apply_migrations(engine)
    status = get_migration_status(engine)

    assert first_report["applied"] == ["0001_initial_schema", "0002_tool_runs", "0003_agent_runs"]
    assert second_report["applied"] == []
    assert status["applied"] == ["0001_initial_schema", "0002_tool_runs", "0003_agent_runs"]
    assert status["pending"] == []
    assert status["status"] == "ok"
