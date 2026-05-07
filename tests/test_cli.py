from typer.testing import CliRunner

from app.cli import main as cli_main


runner = CliRunner()


def test_chat_prints_answer_field(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})
        return {"answer": "hello from api"}

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(cli_main.app, ["chat", "hello", "--user", "alice", "--project", "proj"])

    assert result.exit_code == 0
    assert "AI: hello from api" in result.output
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/chat"
    assert calls[0]["json_data"]["message"] == "hello"
    assert calls[0]["json_data"]["user_id"] == "alice"
    assert calls[0]["json_data"]["project_id"] == "proj"


def test_chat_json_output_is_forwarded(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(cli_main.app, ["chat", "hello", "--json"])

    assert result.exit_code == 0
    assert calls[0]["use_json"] is True


def test_agents_run_prints_agent_run_id(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})
        return {
            "status": "ok",
            "agent_run_id": 42,
            "answer": "done",
            "memory_saved": 1,
        }

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(cli_main.app, ["agents", "run", "check status", "--user", "alice", "--project", "proj"])

    assert result.exit_code == 0
    assert "Run ID: 42" in result.output
    assert "Answer: done" in result.output
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/agents/run"
    assert calls[0]["json_data"]["user_id"] == "alice"
    assert calls[0]["json_data"]["project_id"] == "proj"


def test_agents_runs_queries_scoped_history(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})
        return {"runs": [{"id": 7, "status": "ok", "task": "read file"}]}

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(
        cli_main.app,
        ["agents", "runs", "--user", "alice", "--project", "proj", "--limit", "5"],
    )

    assert result.exit_code == 0
    assert "ID: 7" in result.output
    assert calls[0]["method"] == "GET"
    assert calls[0]["path"] == "/agents/runs"
    assert calls[0]["params"] == {"user_id": "alice", "project_id": "proj", "limit": 5}


def test_agents_runs_json_output_is_forwarded(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(cli_main.app, ["agents", "runs", "--json"])

    assert result.exit_code == 0
    assert calls[0]["use_json"] is True


def test_obsidian_sync_defaults_to_dry_run(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})
        return {"mode": "dry-run", "summary": {"planned": 2, "applied": 0, "conflicts": 1, "errors": 0}}

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(cli_main.app, ["obsidian-sync", "--user", "alice", "--project", "proj"])

    assert result.exit_code == 0
    assert "Obsidian sync dry-run" in result.output
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/memory/obsidian/sync"
    assert calls[0]["params"] == {"user_id": "alice", "project_id": "proj", "dry_run": True}


def test_obsidian_sync_apply_and_json_are_forwarded(monkeypatch):
    calls = []

    def fake_call_api(method, path, params=None, json_data=None, use_json=False):
        calls.append({"method": method, "path": path, "params": params, "json_data": json_data, "use_json": use_json})

    monkeypatch.setattr(cli_main, "call_api", fake_call_api)

    result = runner.invoke(cli_main.app, ["obsidian-sync", "--apply", "--json"])

    assert result.exit_code == 0
    assert calls[0]["params"]["dry_run"] is False
    assert calls[0]["use_json"] is True
