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


def test_registry_writes_new_file_inside_base(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    result = registry.invoke("file.write_text", {"path": "created.md", "content": "hello"})

    assert result.status == "ok"
    assert result.output == {"path": "created.md", "bytes": 5}
    assert (tmp_path / "created.md").read_text(encoding="utf-8") == "hello"


def test_registry_blocks_file_writes_outside_base(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    result = registry.invoke("file.write_text", {"path": "../escape.md", "content": "secret"})

    assert result.status == "error"
    assert "outside allowed base" in result.error


def test_registry_refuses_to_overwrite_existing_file_by_default(tmp_path):
    existing = tmp_path / "existing.md"
    existing.write_text("keep", encoding="utf-8")
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    result = registry.invoke("file.write_text", {"path": "existing.md", "content": "replace"})

    assert result.status == "error"
    assert "path already exists" in result.error
    assert existing.read_text(encoding="utf-8") == "keep"


def test_registry_appends_obsidian_note_inside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    registry = build_default_tool_registry(base_dir=str(tmp_path), obsidian_vault_path=str(vault))

    result = registry.invoke(
        "obsidian.append_note",
        {"path": "Projects/personal.md", "content": "new note line"},
    )

    assert result.status == "ok"
    note = vault / "Projects" / "personal.md"
    assert "new note line" in note.read_text(encoding="utf-8")


def test_registry_blocks_obsidian_append_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    registry = build_default_tool_registry(base_dir=str(tmp_path), obsidian_vault_path=str(vault))

    result = registry.invoke("obsidian.append_note", {"path": "../escape.md", "content": "secret"})

    assert result.status == "error"
    assert "path is outside allowed vault" in result.error


def test_registry_identifies_parallel_safe_tools(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    assert registry.is_parallel_safe("file.read_text") is True
    assert registry.is_parallel_safe("git.status") is True
    assert registry.is_parallel_safe("shell.run_safe") is False
    assert registry.is_parallel_safe("file.write_text") is False
