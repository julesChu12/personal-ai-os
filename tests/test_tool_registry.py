import pytest

from app.tools.registry import ToolNotFoundError, build_default_tool_registry


def test_default_registry_lists_stable_tool_contracts(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("hello from tool", encoding="utf-8")
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    tools = {tool.name: tool for tool in registry.list_tools()}

    assert {"file.read_text", "git.status", "shell.run_safe"}.issubset(tools)
    assert tools["file.read_text"].risk_level == "read"
    assert tools["shell.run_safe"].risk_level == "guarded"
    result = registry.invoke("file.read_text", {"path": "note.md"})
    assert result.tool_name == "file.read_text"
    assert result.status == "ok"
    assert result.output == "hello from tool"
    assert result.error is None


def test_registry_blocks_file_reads_outside_base(tmp_path):
    outside = tmp_path.parent / "outside-tool-test.md"
    outside.write_text("secret", encoding="utf-8")
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    result = registry.invoke("file.read_text", {"path": "../outside-tool-test.md"})

    assert result.status == "error"
    assert result.output is None
    assert "outside allowed base" in result.error


def test_registry_keeps_shell_tool_on_allowlist(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    result = registry.invoke("shell.run_safe", {"command": "cat /etc/passwd"})

    assert result.tool_name == "shell.run_safe"
    assert result.status == "error"
    assert "Command not allowed" in result.error


def test_registry_rejects_unknown_tools(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    with pytest.raises(ToolNotFoundError):
        registry.invoke("unknown.tool", {})
