from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.workflow import AgentWorkflow
from app.db.database import Base
from app.db.models import ToolRun
from app.tools.registry import build_default_tool_registry


def build_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_agent_workflow_reads_file_and_records_tool_run(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("agent workflow output", encoding="utf-8")
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="read file note.md",
        request_id="req-agent-1",
    )

    assert result["status"] == "ok"
    assert result["answer"] == "agent workflow output"
    assert result["agent_trace"][0]["agent"] == "planner"
    assert result["agent_trace"][1]["agent"] == "executor"
    assert result["steps"][0]["tool_name"] == "file.read_text"
    assert result["steps"][0]["status"] == "ok"

    runs = db.query(ToolRun).all()
    assert len(runs) == 1
    assert runs[0].tool_name == "file.read_text"
    assert runs[0].status == "ok"
    assert runs[0].request_id == "req-agent-1"


def test_agent_workflow_rejects_unsupported_tasks_without_tool_run(tmp_path):
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="delete everything",
        request_id="req-agent-2",
    )

    assert result["status"] == "error"
    assert "unsupported agent task" in result["error"]
    assert result["steps"] == []
    assert db.query(ToolRun).count() == 0
