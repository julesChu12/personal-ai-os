from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.workflow import AgentWorkflow
from app.db.database import Base
from app.db.models import ToolRun
from app.tools.registry import build_default_tool_registry


class RecordingMemoryPipeline:
    def __init__(self) -> None:
        self.persist_calls = []

    def persist(self, db, user_id, project_id, session_id, candidates):
        self.persist_calls.append(
            {
                "user_id": user_id,
                "project_id": project_id,
                "session_id": session_id,
                "candidates": candidates,
            }
        )
        return candidates


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


def test_agent_workflow_executes_valid_structured_plan(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("structured plan output", encoding="utf-8")
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="ignored when plan is supplied",
        request_id="req-agent-plan",
        plan_payload={
            "steps": [
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "note.md"},
                    "reason": "read note via structured plan",
                }
            ]
        },
    )

    assert result["status"] == "ok"
    assert result["answer"] == "structured plan output"
    assert result["agent_trace"][0]["action"] == "validate_plan"
    assert result["steps"][0]["tool_name"] == "file.read_text"


def test_agent_workflow_executes_multi_step_structured_plan(tmp_path):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("first output", encoding="utf-8")
    second.write_text("second output", encoding="utf-8")
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="ignored when plan is supplied",
        request_id="req-agent-plan-multi",
        plan_payload={
            "steps": [
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "first.md"},
                    "reason": "read first note",
                },
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "second.md"},
                    "reason": "read second note",
                },
            ]
        },
    )

    assert result["status"] == "ok"
    assert result["answer"] == "first output\nsecond output"
    assert [step["status"] for step in result["steps"]] == ["ok", "ok"]
    assert db.query(ToolRun).count() == 2


def test_agent_workflow_stops_after_first_failed_step(tmp_path):
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="ignored when plan is supplied",
        request_id="req-agent-plan-stop-first",
        plan_payload={
            "steps": [
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "missing.md"},
                    "reason": "read missing note",
                },
                {
                    "tool_name": "shell.run_safe",
                    "input": {"command": "pwd"},
                    "reason": "show cwd after failure",
                },
            ]
        },
    )

    assert result["status"] == "error"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["tool_name"] == "file.read_text"
    assert result["steps"][0]["status"] == "error"
    assert result["error"] == "path is not a file"
    assert [entry["action"] for entry in result["agent_trace"]] == ["validate_plan", "execute_tool"]
    assert db.query(ToolRun).count() == 1


def test_agent_workflow_stops_after_later_failed_step(tmp_path):
    first = tmp_path / "first.md"
    first.write_text("first output", encoding="utf-8")
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="ignored when plan is supplied",
        request_id="req-agent-plan-stop-later",
        plan_payload={
            "steps": [
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "first.md"},
                    "reason": "read first note",
                },
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "missing.md"},
                    "reason": "read missing note",
                },
                {
                    "tool_name": "shell.run_safe",
                    "input": {"command": "pwd"},
                    "reason": "show cwd after failure",
                },
            ]
        },
    )

    assert result["status"] == "error"
    assert len(result["steps"]) == 2
    assert [step["status"] for step in result["steps"]] == ["ok", "error"]
    assert result["steps"][1]["tool_name"] == "file.read_text"
    assert result["error"] == "path is not a file"
    assert db.query(ToolRun).count() == 2


def test_agent_workflow_persists_successful_agent_result_when_requested(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("memory worthy output", encoding="utf-8")
    db = build_db_session()
    memory_pipeline = RecordingMemoryPipeline()
    workflow = AgentWorkflow(
        registry=build_default_tool_registry(base_dir=str(tmp_path)),
        memory_pipeline=memory_pipeline,
    )

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="read file note.md",
        request_id="req-agent-memory",
        persist_agent_result=True,
    )

    assert result["status"] == "ok"
    assert result["memory_saved"] == 1
    assert len(memory_pipeline.persist_calls) == 1
    call = memory_pipeline.persist_calls[0]
    assert call["user_id"] == "u1"
    assert call["project_id"] == "p1"
    assert call["session_id"] == "s1"
    candidate = call["candidates"][0]
    assert candidate.memory_type == "agent_result"
    assert candidate.title == "Agent result: read file note.md"
    assert "Task: read file note.md" in candidate.content
    assert "memory worthy output" in candidate.content
    assert "agent" in candidate.tags


def test_agent_workflow_does_not_persist_failed_agent_result(tmp_path):
    db = build_db_session()
    memory_pipeline = RecordingMemoryPipeline()
    workflow = AgentWorkflow(
        registry=build_default_tool_registry(base_dir=str(tmp_path)),
        memory_pipeline=memory_pipeline,
    )

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="ignored when plan is supplied",
        request_id="req-agent-memory-failed",
        persist_agent_result=True,
        plan_payload={
            "steps": [
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "missing.md"},
                    "reason": "read missing note",
                }
            ]
        },
    )

    assert result["status"] == "error"
    assert result["memory_saved"] == 0
    assert memory_pipeline.persist_calls == []


def test_agent_workflow_rejects_invalid_structured_plan_without_tool_run(tmp_path):
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="ignored when plan is supplied",
        request_id="req-agent-plan-invalid",
        plan_payload={
            "steps": [
                {
                    "tool_name": "shell.run_safe",
                    "input": {"command": "cat /etc/passwd"},
                    "reason": "unsafe command",
                }
            ]
        },
    )

    assert result["status"] == "error"
    assert "command must be one of" in result["error"]
    assert result["memory_saved"] == 0
    assert result["steps"] == []
    assert db.query(ToolRun).count() == 0


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
    assert result["memory_saved"] == 0
    assert result["steps"] == []
    assert db.query(ToolRun).count() == 0
