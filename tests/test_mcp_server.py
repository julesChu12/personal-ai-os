from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import ToolRun
from app.tools.mcp_adapter import list_mcp_tools
from app.tools.mcp_server import handle_mcp_request
from app.tools.registry import build_default_tool_registry


def build_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_mcp_adapter_lists_only_read_safe_tools_by_default(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    tools = list_mcp_tools(registry)

    names = {tool["name"] for tool in tools}
    assert {"file.read_text", "git.status", "shell.run_safe"}.issubset(names)
    assert all("inputSchema" in tool for tool in tools)
    assert all(tool["name"] != "file.write_text" for tool in tools)


def test_mcp_adapter_hides_write_tools(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    registry = build_default_tool_registry(base_dir=str(tmp_path), obsidian_vault_path=str(vault))

    tools = list_mcp_tools(registry)

    names = {tool["name"] for tool in tools}
    assert "file.write_text" not in names
    assert "obsidian.append_note" not in names


def test_mcp_server_handles_tools_list(tmp_path):
    db = build_db_session()
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
        registry=registry,
        db=db,
        user_id="u1",
        project_id="p1",
        session_id=None,
        request_id="req-mcp-list",
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert "file.read_text" in names


def test_mcp_server_calls_tool_and_records_tool_run(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("mcp output", encoding="utf-8")
    db = build_db_session()
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "file.read_text",
                "arguments": {"path": "note.md"},
            },
        },
        registry=registry,
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        request_id="req-mcp-call",
    )

    assert response["result"]["content"][0]["text"] == "mcp output"
    assert response["result"]["isError"] is False
    runs = db.query(ToolRun).all()
    assert len(runs) == 1
    assert runs[0].tool_name == "file.read_text"
    assert runs[0].request_id == "req-mcp-call"
