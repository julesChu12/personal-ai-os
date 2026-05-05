# N3-N5 Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the detailed implementation plan for N3 Executor DAG/parallelism, N4 write-tool allowlist, and N5 MCP read-only Tool Registry exposure while preserving auditability and scope isolation.

**Architecture:** N3 extends the existing `AgentPlan -> AgentWorkflow -> ExecutorAgent` pipeline without replacing it. N4 adds conservative write tools through `ToolRegistry`, not direct filesystem access from Agent code. N5 exposes Tool Registry contracts through a narrow MCP adapter and records every tool call through the existing `ToolRun` audit path.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, Qdrant-independent unit tests, Docker Compose smoke tests, MCP JSON-RPC `tools/list` and `tools/call` semantics.

---

## Scope And Preconditions

- N1 retrieval-quality-foundation is complete.
- N2 Planner model mode is complete.
- N7 multi API key and user/project binding must be completed before implementing N5, N4, or any externally reachable write capability.
- This plan does not implement N6 Obsidian import, N8 online embedding quality, N9 CLI, or N10 migration-only startup.
- Do not create git commits unless the user explicitly asks for commits.

## External Protocol Notes

The N5 plan follows the official Model Context Protocol tool shape:

- Tool servers declare tool capability and expose tool discovery through `tools/list`.
- Tool invocation uses `tools/call` with `params.name` and `params.arguments`.
- Tool definitions expose `name`, `description`, and `inputSchema`.
- Tool execution failures are returned as tool results with `isError=true`; protocol-level errors are reserved for invalid JSON-RPC, unknown methods, or malformed requests.

References used when writing this plan:

- https://modelcontextprotocol.io/docs/sdk
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools

## File Responsibility Map

| File | Responsibility |
| --- | --- |
| `app/agents/planner.py` | Extend `AgentStep` and `validate_agent_plan()` with step ids, dependencies, and conservative condition schema. |
| `app/agents/executor.py` | Extend `AgentStepResult` with `step_id` and skipped-step serialization. |
| `app/agents/workflow.py` | Execute validated DAG steps sequentially for N3a, then optionally execute safe independent read-only batches for N3b. |
| `app/api/routes_agents.py` | Accept execution mode only after workflow behavior is covered by tests. |
| `app/tools/registry.py` | Add write tools, side-effect classification, and read-only filtering helpers for MCP/parallel safety. |
| `app/tools/file_tool.py` | Add conservative `write_text()` with path escape prevention and no overwrite-by-default behavior. |
| `app/tools/obsidian_tool.py` | Add `append_note()` using the same vault path boundary rules as Obsidian writer. |
| `app/tools/mcp_adapter.py` | Convert Tool Registry definitions/results to MCP-compatible tool list and call results. |
| `app/tools/mcp_server.py` | Provide a thin JSON-RPC handler around the adapter and existing `record_tool_run()`. |
| `scripts/run_mcp_server.py` | Run the MCP stdio server entrypoint for local clients. |
| `tests/test_agent_plan.py` | Validate DAG schema, duplicate ids, missing dependencies, cycles, and condition schema. |
| `tests/test_agent_workflow.py` | Validate sequential DAG execution, skipped trace, fail-fast, and limited parallel behavior. |
| `tests/test_agents_route.py` | Validate HTTP exposure for execution mode and backward compatibility. |
| `tests/test_tool_registry.py` | Validate write tool contracts, path safety, side-effect classification, and read-only filtering. |
| `tests/test_tools_route.py` | Validate write tool success/failure audit through `/tools/{tool}/invoke`. |
| `tests/test_mcp_server.py` | Validate MCP tool list/call mapping and ToolRun audit. |
| `README.md`, `docs/testing.md`, `docs/development-roadmap.md` | Document completed behavior and regression commands. |

## Execution Order

| Order | Task | Reason |
| --- | --- | --- |
| 1 | N5 read-only MCP adapter core | It depends on Tool Registry and N7 auth, but not on N3/N4 behavior; keeping it read-only prevents new write risk. |
| 2 | N3a sequential DAG | It extends current Agent execution semantics before adding new write tools or concurrency. |
| 3 | N4 write-tool allowlist | Write tools should land after read-only MCP and sequential DAG semantics are stable. |
| 4 | N3b limited parallel executor | Parallelism should wait until side-effect classification exists from N4. |

---

## Task N5.1: MCP Adapter Core

**Files:**
- Create: `app/tools/mcp_adapter.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing test for read-only tool listing**

Add this test to `tests/test_mcp_server.py`:

```python
from app.tools.mcp_adapter import list_mcp_tools
from app.tools.registry import build_default_tool_registry


def test_mcp_adapter_lists_only_read_safe_tools_by_default(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    tools = list_mcp_tools(registry)

    names = {tool["name"] for tool in tools}
    assert {"file.read_text", "git.status", "shell.run_safe"}.issubset(names)
    assert all("inputSchema" in tool for tool in tools)
    assert all(tool["name"] != "file.write_text" for tool in tools)
```

- [ ] **Step 2: Run red test**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_mcp_server.py::test_mcp_adapter_lists_only_read_safe_tools_by_default -q
```

Expected result:

```text
ModuleNotFoundError: No module named 'app.tools.mcp_adapter'
```

- [ ] **Step 3: Implement adapter list mapping**

Create `app/tools/mcp_adapter.py`:

```python
import json
from typing import Any

from app.tools.registry import ToolInvocationResult, ToolRegistry

MCP_EXPOSED_RISK_LEVELS = {"read", "guarded"}


def list_mcp_tools(registry: ToolRegistry) -> list[dict[str, Any]]:
    tools = []
    for definition in registry.list_tools():
        if definition.risk_level not in MCP_EXPOSED_RISK_LEVELS:
            continue
        tools.append(
            {
                "name": definition.name,
                "description": definition.description,
                "inputSchema": definition.input_schema,
            }
        )
    return tools


def mcp_result_from_tool_result(result: ToolInvocationResult) -> dict[str, Any]:
    text = result.error if result.status != "ok" else _serialize_output(result.output)
    return {
        "content": [{"type": "text", "text": text or ""}],
        "isError": result.status != "ok",
    }


def _serialize_output(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    return json.dumps(output, ensure_ascii=False, default=str)
```

- [ ] **Step 4: Run green test**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_mcp_server.py::test_mcp_adapter_lists_only_read_safe_tools_by_default -q
```

Expected result:

```text
1 passed
```

## Task N5.2: MCP JSON-RPC Tool Calls With Audit

**Files:**
- Create: `app/tools/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing test for `tools/list` JSON-RPC**

Append this test:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.tools.mcp_server import handle_mcp_request


def build_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


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
```

- [ ] **Step 2: Write failing test for `tools/call` audit**

Append this test:

```python
from app.db.models import ToolRun


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
```

- [ ] **Step 3: Run red tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_mcp_server.py -q
```

Expected result includes:

```text
ModuleNotFoundError: No module named 'app.tools.mcp_server'
```

- [ ] **Step 4: Implement JSON-RPC handler**

Create `app/tools/mcp_server.py`:

```python
from typing import Any

from sqlalchemy.orm import Session

from app.tools.audit import record_tool_run
from app.tools.mcp_adapter import list_mcp_tools, mcp_result_from_tool_result
from app.tools.registry import ToolNotFoundError, ToolRegistry

JSONRPC_VERSION = "2.0"


def handle_mcp_request(
    request: dict[str, Any],
    *,
    registry: ToolRegistry,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    request_id: str | None,
) -> dict[str, Any]:
    method = request.get("method")
    request_id_value = request.get("id")
    if method == "tools/list":
        return _response(request_id_value, {"tools": list_mcp_tools(registry)})
    if method == "tools/call":
        return _handle_tools_call(
            request,
            registry=registry,
            db=db,
            user_id=user_id,
            project_id=project_id,
            session_id=session_id,
            request_id=request_id,
        )
    return _error(request_id_value, -32601, f"method not found: {method}")


def _handle_tools_call(
    request: dict[str, Any],
    *,
    registry: ToolRegistry,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    request_id: str | None,
) -> dict[str, Any]:
    params = request.get("params") or {}
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}
    request_id_value = request.get("id")
    if not isinstance(tool_name, str) or not tool_name.strip():
        return _error(request_id_value, -32602, "params.name must be a non-empty string")
    if not isinstance(arguments, dict):
        return _error(request_id_value, -32602, "params.arguments must be an object")
    try:
        definition = registry.get_definition(tool_name)
    except ToolNotFoundError:
        return _error(request_id_value, -32602, f"unknown tool: {tool_name}")
    if definition.risk_level not in {"read", "guarded"}:
        return _error(request_id_value, -32602, f"tool is not exposed through MCP: {tool_name}")

    result = registry.invoke(tool_name, arguments)
    record_tool_run(
        db,
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        result=result,
        input_payload=arguments,
        request_id=request_id,
    )
    return _response(request_id_value, mcp_result_from_tool_result(result))


def _response(request_id_value: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id_value, "result": result}


def _error(request_id_value: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id_value, "error": {"code": code, "message": message}}
```

- [ ] **Step 5: Run MCP adapter tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_mcp_server.py -q
```

Expected result:

```text
3 passed
```

## Task N5.3: MCP Stdio Runner

**Files:**
- Create: `scripts/run_mcp_server.py`
- Modify: `tests/test_project_contracts.py`
- Modify: `README.md`
- Modify: `docs/testing.md`

- [ ] **Step 1: Add contract test for MCP runner documentation**

Modify `tests/test_project_contracts.py` by extending the tool-layer contract test with these assertions:

```python
    mcp_server = read_text("app/tools/mcp_server.py")
    mcp_runner = read_text("scripts/run_mcp_server.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")

    assert "handle_mcp_request" in mcp_server
    assert "tools/list" in mcp_server
    assert "tools/call" in mcp_server
    assert "run_mcp_server.py" in mcp_runner
    assert "MCP" in readme
    assert "MCP" in testing
```

- [ ] **Step 2: Run red contract test**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_project_contracts.py::test_p2_tool_layer_contract_is_documented -q
```

Expected result includes a missing file or missing assertion failure for `scripts/run_mcp_server.py`.

- [ ] **Step 3: Create stdio runner**

Create `scripts/run_mcp_server.py`:

```python
#!/usr/bin/env python3
import json
import sys

from app.db.database import SessionLocal
from app.tools.mcp_server import handle_mcp_request
from app.tools.registry import build_default_tool_registry


def main() -> None:
    registry = build_default_tool_registry()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        with SessionLocal() as db:
            response = handle_mcp_request(
                request,
                registry=registry,
                db=db,
                user_id="mcp-local",
                project_id="personal-ai-os",
                session_id=None,
                request_id="mcp-stdio",
            )
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Document MCP first slice**

Add this paragraph to README and `docs/testing.md`:

```markdown
MCP first slice exposes read-safe Tool Registry entries through a JSON-RPC stdio runner. It supports `tools/list` and `tools/call`, maps Tool Registry `input_schema` to MCP `inputSchema`, and records every `tools/call` as a `ToolRun`. Write tools are not exposed through MCP by default.
```

- [ ] **Step 5: Verify MCP runner contracts**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_mcp_server.py tests/test_project_contracts.py -q
```

Expected result includes:

```text
passed
```

---

## Task N3a.1: Extend Plan Schema With Step IDs And Dependencies

**Files:**
- Modify: `app/agents/planner.py`
- Modify: `tests/test_agent_plan.py`

- [ ] **Step 1: Write failing test for step ids and dependency order**

Add this test:

```python
def test_validate_agent_plan_accepts_step_ids_and_dependencies(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {
                "id": "read-note",
                "tool_name": "file.read_text",
                "input": {"path": "note.md"},
                "reason": "read note",
            },
            {
                "id": "show-cwd",
                "depends_on": ["read-note"],
                "tool_name": "shell.run_safe",
                "input": {"command": "pwd"},
                "reason": "show cwd after note read",
            },
        ]
    }

    plan = validate_agent_plan(raw_plan, registry)

    assert plan.steps[0].step_id == "read-note"
    assert plan.steps[1].depends_on == ["read-note"]
    assert plan.to_dict()["steps"][1]["depends_on"] == ["read-note"]
```

- [ ] **Step 2: Write failing tests for invalid DAG**

Add these tests:

```python
def test_validate_agent_plan_rejects_duplicate_step_ids(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {"id": "same", "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "first"},
            {"id": "same", "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "second"},
        ]
    }

    with pytest.raises(AgentPlanValidationError, match="step id must be unique"):
        validate_agent_plan(raw_plan, registry)


def test_validate_agent_plan_rejects_missing_dependency(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {
                "id": "show-cwd",
                "depends_on": ["missing"],
                "tool_name": "shell.run_safe",
                "input": {"command": "pwd"},
                "reason": "show cwd",
            }
        ]
    }

    with pytest.raises(AgentPlanValidationError, match="depends_on references unknown step"):
        validate_agent_plan(raw_plan, registry)


def test_validate_agent_plan_rejects_dependency_cycle(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {"id": "a", "depends_on": ["b"], "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "a"},
            {"id": "b", "depends_on": ["a"], "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "b"},
        ]
    }

    with pytest.raises(AgentPlanValidationError, match="dependency cycle"):
        validate_agent_plan(raw_plan, registry)
```

- [ ] **Step 3: Run red tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_agent_plan.py -q
```

Expected result includes `AttributeError: 'AgentStep' object has no attribute 'step_id'`.

- [ ] **Step 4: Extend `AgentStep`**

Modify `app/agents/planner.py`:

```python
@dataclass(frozen=True)
class AgentStep:
    tool_name: str
    input: dict[str, Any]
    reason: str
    step_id: str
    depends_on: list[str]
    condition: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.step_id,
            "tool_name": self.tool_name,
            "input": self.input,
            "reason": self.reason,
            "depends_on": self.depends_on,
        }
        if self.condition is not None:
            payload["condition"] = self.condition
        return payload
```

- [ ] **Step 5: Preserve deterministic planner compatibility**

In deterministic planner branches, instantiate steps with generated ids:

```python
AgentStep(
    step_id="step-1",
    tool_name="file.read_text",
    input={"path": path},
    reason="read requested workspace file",
    depends_on=[],
)
```

- [ ] **Step 6: Add validation helpers**

Add these helpers in `app/agents/planner.py`:

```python
def _optional_step_id(raw_step: dict[str, Any], index: int) -> str:
    value = raw_step.get("id") or f"step-{index + 1}"
    if not isinstance(value, str) or not value.strip():
        raise AgentPlanValidationError(f"steps[{index}].id must be a non-empty string")
    return value.strip()


def _optional_depends_on(raw_step: dict[str, Any], index: int) -> list[str]:
    value = raw_step.get("depends_on", [])
    if not isinstance(value, list):
        raise AgentPlanValidationError(f"steps[{index}].depends_on must be a list")
    dependencies = []
    for dependency in value:
        if not isinstance(dependency, str) or not dependency.strip():
            raise AgentPlanValidationError(f"steps[{index}].depends_on entries must be non-empty strings")
        dependencies.append(dependency.strip())
    return dependencies
```

- [ ] **Step 7: Validate duplicate ids, missing dependencies, and cycles**

Add this validation after building steps:

```python
def _validate_step_graph(steps: list[AgentStep]) -> None:
    seen: set[str] = set()
    for step in steps:
        if step.step_id in seen:
            raise AgentPlanValidationError("step id must be unique")
        seen.add(step.step_id)

    for step in steps:
        for dependency in step.depends_on:
            if dependency not in seen:
                raise AgentPlanValidationError("depends_on references unknown step")

    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {step.step_id: step for step in steps}

    def visit(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            raise AgentPlanValidationError("dependency cycle detected")
        visiting.add(step_id)
        for dependency in by_id[step_id].depends_on:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step in steps:
        visit(step.step_id)
```

- [ ] **Step 8: Run green tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_agent_plan.py -q
```

Expected result includes:

```text
passed
```

## Task N3a.2: Sequential DAG Execution And Skipped Steps

**Files:**
- Modify: `app/agents/executor.py`
- Modify: `app/agents/workflow.py`
- Modify: `tests/test_agent_workflow.py`

- [ ] **Step 1: Write failing test for dependency execution order**

Add this test:

```python
def test_agent_workflow_executes_dag_in_dependency_order(tmp_path):
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
        task="dag plan",
        plan_payload={
            "steps": [
                {"id": "second", "depends_on": ["first"], "tool_name": "file.read_text", "input": {"path": "second.md"}, "reason": "read second"},
                {"id": "first", "tool_name": "file.read_text", "input": {"path": "first.md"}, "reason": "read first"},
            ]
        },
    )

    assert result["status"] == "ok"
    assert [step["id"] for step in result["steps"]] == ["first", "second"]
    assert result["answer"] == "first output\nsecond output"
```

- [ ] **Step 2: Write failing test for condition skip**

Add this test:

```python
def test_agent_workflow_records_condition_skipped_step_without_tool_run(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("dirty working tree", encoding="utf-8")
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="conditional plan",
        plan_payload={
            "steps": [
                {"id": "read", "tool_name": "file.read_text", "input": {"path": "note.md"}, "reason": "read note"},
                {
                    "id": "pwd-if-clean",
                    "depends_on": ["read"],
                    "condition": {"step_id": "read", "output_contains": "nothing to commit"},
                    "tool_name": "shell.run_safe",
                    "input": {"command": "pwd"},
                    "reason": "show cwd only when clean",
                },
            ]
        },
    )

    assert result["status"] == "ok"
    assert [step["status"] for step in result["steps"]] == ["ok", "skipped"]
    assert result["steps"][1]["run_id"] is None
    assert db.query(ToolRun).count() == 1
    assert result["agent_trace"][-1]["action"] == "skip_tool"
```

- [ ] **Step 3: Run red workflow tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_agent_workflow.py -q
```

Expected result includes missing `id` in step serialization or condition not being applied.

- [ ] **Step 4: Extend `AgentStepResult`**

Modify `app/agents/executor.py`:

```python
@dataclass(frozen=True)
class AgentStepResult:
    tool_name: str
    input: dict[str, Any]
    status: str
    output: Any | None = None
    error: str | None = None
    run_id: int | None = None
    step_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.step_id,
            "tool_name": self.tool_name,
            "input": self.input,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "run_id": self.run_id,
        }
```

- [ ] **Step 5: Add deterministic topological order helper**

Add helper to `app/agents/workflow.py`:

```python
def _ordered_steps_for_execution(plan) -> list:
    by_id = {step.step_id: step for step in plan.steps}
    ordered: list = []
    visited: set[str] = set()

    def visit(step) -> None:
        if step.step_id in visited:
            return
        for dependency in step.depends_on:
            visit(by_id[dependency])
        visited.add(step.step_id)
        ordered.append(step)

    for step in plan.steps:
        visit(step)
    return ordered
```

- [ ] **Step 6: Add condition helper**

Add helper to `app/agents/workflow.py`:

```python
def _condition_matches(step, results_by_id: dict[str, AgentStepResult]) -> bool:
    if not step.condition:
        return True
    condition = step.condition
    source = results_by_id.get(condition["step_id"])
    if source is None:
        return False
    if "status" in condition and source.status != condition["status"]:
        return False
    if "output_contains" in condition and condition["output_contains"] not in str(source.output or ""):
        return False
    return True
```

- [ ] **Step 7: Execute ordered steps and record skipped trace**

In `AgentWorkflow.run()`, replace the direct `for step in plan.steps` loop with ordered execution:

```python
results_by_id: dict[str, AgentStepResult] = {}
for step in _ordered_steps_for_execution(plan):
    if not _condition_matches(step, results_by_id):
        skipped = AgentStepResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            input=step.input,
            status="skipped",
        )
        step_results.append(skipped)
        results_by_id[step.step_id] = skipped
        trace.append({"agent": "executor", "action": "skip_tool", "tool_name": step.tool_name, "step_id": step.step_id})
        continue
    result = self.executor.execute(step, self.registry)
    run = record_tool_run(
        db,
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        result=result,
        input_payload=step.input,
        request_id=request_id,
    )
    step_result = AgentStepResult(
        step_id=step.step_id,
        tool_name=step.tool_name,
        input=step.input,
        status=result.status,
        output=result.output,
        error=result.error,
        run_id=run.id,
    )
    step_results.append(step_result)
    results_by_id[step.step_id] = step_result
    trace.append(
        {
            "agent": "executor",
            "action": "execute_tool",
            "tool_name": step.tool_name,
            "step_id": step.step_id,
            "status": result.status,
            "run_id": run.id,
        }
    )
    if result.status != "ok":
        break
```

Keep the existing fail-fast behavior after executed error steps:

```python
if result.status != "ok":
    break
```

- [ ] **Step 8: Run green workflow tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_agent_plan.py tests/test_agent_workflow.py -q
```

Expected result includes:

```text
passed
```

---

## Task N4.1: `file.write_text` Allowlisted Tool

**Files:**
- Modify: `app/tools/file_tool.py`
- Modify: `app/tools/registry.py`
- Modify: `tests/test_tool_registry.py`
- Modify: `tests/test_tools_route.py`

- [ ] **Step 1: Write failing registry test for safe file write**

Add this test:

```python
def test_registry_writes_new_file_inside_base(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    result = registry.invoke("file.write_text", {"path": "created.md", "content": "hello"})

    assert result.status == "ok"
    assert result.output == {"path": "created.md", "bytes": 5}
    assert (tmp_path / "created.md").read_text(encoding="utf-8") == "hello"
```

- [ ] **Step 2: Write failing tests for write safety**

Add these tests:

```python
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
```

- [ ] **Step 3: Run red registry tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_tool_registry.py -q
```

Expected result includes `ToolNotFoundError` or `unknown.tool` for `file.write_text`.

- [ ] **Step 4: Implement file writer helper**

Add to `app/tools/file_tool.py`:

```python
def write_text(path: str, content: str, base_dir: str = ".") -> dict[str, int | str]:
    """Write a new UTF-8 text file inside base_dir; refuse overwrites and path escapes."""
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    safe_path = resolve_within_base(path, base_dir)
    if safe_path.exists():
        raise ValueError("path already exists")
    if not safe_path.parent.is_dir():
        raise ValueError("parent directory is not a directory")
    safe_path.write_text(content, encoding="utf-8")
    return {"path": path, "bytes": len(content.encode("utf-8"))}
```

- [ ] **Step 5: Register write tool**

Modify `app/tools/registry.py` imports:

```python
from app.tools.file_tool import read_text, resolve_within_base, write_text
```

Register:

```python
registry.register(
    ToolDefinition(
        name="file.write_text",
        description="Write a new UTF-8 text file inside the allowed workspace. Existing files are refused.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        risk_level="write",
    ),
    lambda payload: write_text(
        _required_string(payload, "path"),
        _required_string(payload, "content"),
        base_dir=resolved_base,
    ),
)
```

- [ ] **Step 6: Add HTTP audit test for write tool**

Add to `tests/test_tools_route.py`:

```python
def test_tool_invoke_records_file_write_run(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/tools/file.write_text/invoke",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "input": {"path": "created.md", "content": "hello"},
        },
        headers={"X-Request-ID": "req-tool-write"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert (tmp_path / "created.md").read_text(encoding="utf-8") == "hello"
    runs = client.get("/tools/runs", params={"user_id": "u1", "project_id": "p1"}).json()["runs"]
    assert runs[0]["tool_name"] == "file.write_text"
    assert runs[0]["status"] == "ok"
    assert runs[0]["request_id"] == "req-tool-write"
```

- [ ] **Step 7: Run green tool tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_tool_registry.py tests/test_tools_route.py -q
```

Expected result includes:

```text
passed
```

## Task N4.2: `obsidian.append_note` Allowlisted Tool

**Files:**
- Create: `app/tools/obsidian_tool.py`
- Modify: `app/tools/registry.py`
- Modify: `tests/test_tool_registry.py`

- [ ] **Step 1: Write failing Obsidian append test**

Add this test:

```python
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
```

- [ ] **Step 2: Write failing vault escape test**

Add this test:

```python
def test_registry_blocks_obsidian_append_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    registry = build_default_tool_registry(base_dir=str(tmp_path), obsidian_vault_path=str(vault))

    result = registry.invoke("obsidian.append_note", {"path": "../escape.md", "content": "secret"})

    assert result.status == "error"
    assert "path is outside allowed vault" in result.error
```

- [ ] **Step 3: Run red tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_tool_registry.py -q
```

Expected result includes missing keyword argument `obsidian_vault_path` or unknown tool.

- [ ] **Step 4: Implement Obsidian tool**

Create `app/tools/obsidian_tool.py`:

```python
from pathlib import Path


def append_note(path: str, content: str, vault_path: str) -> dict[str, int | str]:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    safe_path = _resolve_within_vault(path, vault_path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    text = content.rstrip() + "\n"
    with safe_path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    return {"path": str(Path(path)), "bytes": len(text.encode("utf-8"))}


def _resolve_within_vault(path: str, vault_path: str) -> Path:
    vault = Path(vault_path).resolve()
    candidate_path = Path(path)
    candidate = candidate_path.resolve() if candidate_path.is_absolute() else (vault / candidate_path).resolve()
    try:
        candidate.relative_to(vault)
    except ValueError as exc:
        raise ValueError("path is outside allowed vault") from exc
    return candidate
```

- [ ] **Step 5: Register Obsidian append tool**

Modify `build_default_tool_registry()` signature:

```python
def build_default_tool_registry(base_dir: str = ".", obsidian_vault_path: str | None = None) -> ToolRegistry:
```

Use settings fallback:

```python
from app.config import settings
from app.tools.obsidian_tool import append_note

resolved_vault = str(Path(obsidian_vault_path or settings.obsidian_vault_path).resolve())
```

Register:

```python
registry.register(
    ToolDefinition(
        name="obsidian.append_note",
        description="Append text to a Markdown note inside the configured Obsidian vault.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        risk_level="write",
    ),
    lambda payload: append_note(
        _required_string(payload, "path"),
        _required_string(payload, "content"),
        vault_path=resolved_vault,
    ),
)
```

- [ ] **Step 6: Verify write tools are hidden from MCP**

Add this test to `tests/test_mcp_server.py`:

```python
def test_mcp_adapter_hides_write_tools(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path), obsidian_vault_path=str(tmp_path / "vault"))

    tools = list_mcp_tools(registry)

    names = {tool["name"] for tool in tools}
    assert "file.write_text" not in names
    assert "obsidian.append_note" not in names
```

- [ ] **Step 7: Run tool and MCP tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_tool_registry.py tests/test_tools_route.py tests/test_mcp_server.py -q
```

Expected result includes:

```text
passed
```

---

## Task N3b.1: Side-Effect Classification And Explicit Parallel Mode

**Files:**
- Modify: `app/tools/registry.py`
- Modify: `app/agents/workflow.py`
- Modify: `app/api/routes_agents.py`
- Modify: `tests/test_agent_workflow.py`
- Modify: `tests/test_agents_route.py`

- [ ] **Step 1: Write failing test for read-only side-effect helper**

Add this test to `tests/test_tool_registry.py`:

```python
def test_registry_identifies_parallel_safe_tools(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    assert registry.is_parallel_safe("file.read_text") is True
    assert registry.is_parallel_safe("git.status") is True
    assert registry.is_parallel_safe("shell.run_safe") is False
    assert registry.is_parallel_safe("file.write_text") is False
```

- [ ] **Step 2: Implement side-effect helper**

Add to `ToolRegistry`:

```python
    def is_parallel_safe(self, name: str) -> bool:
        definition = self.get_definition(name)
        return definition.risk_level == "read"
```

- [ ] **Step 3: Write failing workflow test for explicit parallel mode**

Add this test:

```python
def test_agent_workflow_parallel_mode_preserves_plan_order(tmp_path):
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
        task="parallel reads",
        execution_mode="parallel",
        plan_payload={
            "steps": [
                {"id": "first", "tool_name": "file.read_text", "input": {"path": "first.md"}, "reason": "read first"},
                {"id": "second", "tool_name": "file.read_text", "input": {"path": "second.md"}, "reason": "read second"},
            ]
        },
    )

    assert result["status"] == "ok"
    assert [step["id"] for step in result["steps"]] == ["first", "second"]
    assert result["answer"] == "first output\nsecond output"
```

- [ ] **Step 4: Add execution mode to route payload**

Modify `AgentRunRequest`:

```python
    execution_mode: str = "sequential"
```

Pass it into workflow:

```python
execution_mode=payload.execution_mode,
```

- [ ] **Step 5: Validate execution mode**

Add helper in `AgentWorkflow.run()`:

```python
def _normalize_execution_mode(execution_mode: str) -> str:
    normalized = execution_mode.strip().lower()
    if normalized not in {"sequential", "parallel"}:
        raise ValueError("execution_mode must be one of: sequential, parallel")
    return normalized
```

Use sequential mode as the default path.

- [ ] **Step 6: Run targeted tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_tool_registry.py tests/test_agent_workflow.py tests/test_agents_route.py -q
```

Expected result includes:

```text
passed
```

## Task N3b.2: Limited Parallel Execution

**Files:**
- Modify: `app/agents/workflow.py`
- Modify: `tests/test_agent_workflow.py`

- [ ] **Step 1: Write failing test that guarded/write tools remain sequential**

Add this test:

```python
def test_agent_workflow_parallel_mode_keeps_guarded_tools_sequential(tmp_path):
    db = build_db_session()
    workflow = AgentWorkflow(registry=build_default_tool_registry(base_dir=str(tmp_path)))

    result = workflow.run(
        db=db,
        user_id="u1",
        project_id="p1",
        session_id="s1",
        task="parallel guarded",
        execution_mode="parallel",
        plan_payload={
            "steps": [
                {"id": "pwd", "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "show cwd"},
                {"id": "status", "tool_name": "git.status", "input": {}, "reason": "git status"},
            ]
        },
    )

    assert result["status"] == "ok"
    assert [entry["action"] for entry in result["agent_trace"] if entry["agent"] == "executor"] == [
        "execute_tool",
        "execute_tool",
    ]
```

- [ ] **Step 2: Implement batch grouping**

Add helper in `app/agents/workflow.py`:

```python
def _parallel_batches(steps: list, registry: ToolRegistry) -> list[list]:
    batches: list[list] = []
    current: list = []
    for step in steps:
        if step.depends_on or not registry.is_parallel_safe(step.tool_name):
            if current:
                batches.append(current)
                current = []
            batches.append([step])
            continue
        current.append(step)
    if current:
        batches.append(current)
    return batches
```

- [ ] **Step 3: Execute safe batches with fixed worker limit**

Use `ThreadPoolExecutor(max_workers=2)` only for batches with more than one step:

```python
from concurrent.futures import ThreadPoolExecutor


def _execute_parallel_batch(executor: ExecutorAgent, registry: ToolRegistry, batch: list) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(executor.execute, step, registry): step for step in batch}
        return {futures[future].step_id: future.result() for future in futures}
```

After each parallel batch, record `ToolRun` rows in original plan order, not completion order.

- [ ] **Step 4: Preserve fail-fast across batches**

After recording a batch, compute:

```python
failed = next((step for step in step_results if step.status == "error"), None)
if failed is not None:
    break
```

This allows in-flight steps within the same safe batch to finish, but prevents later batches from starting.

- [ ] **Step 5: Run workflow tests**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest tests/test_agent_workflow.py tests/test_agents_route.py -q
```

Expected result includes:

```text
passed
```

---

## Task N3-N5 Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/testing.md`
- Modify: `docs/development-roadmap.md`
- Modify: `docs/superpowers/specs/2026-05-04-next-stage-execution-spec.md`
- Modify: `docs/superpowers/plans/2026-05-04-next-stage-execution.md`
- Modify: `tests/test_project_contracts.py`

- [ ] **Step 1: Update status rows**

When each task is completed, update these statuses:

```markdown
| N5 | MCP Server 适配：只读暴露 Tool Registry | P1 | 已完成 |
| N3a | Executor 条件分支与顺序 DAG | P1 | 已完成 |
| N4 | 写类工具白名单 | P1 | 已完成 |
| N3b | Executor 有限并行 | P2 | 已完成 |
```

- [ ] **Step 2: Update testing coverage**

Add this coverage text to `docs/testing.md`:

```markdown
- MCP adapter：`tools/list` 和 `tools/call` 复用 Tool Registry schema，默认只暴露 read/guarded 工具，调用写入 ToolRun。
- Executor DAG：plan step id、depends_on、条件跳过、循环依赖拒绝、fail-fast 和 skipped trace 均有测试覆盖。
- 写类工具：`file.write_text` 拒绝路径逃逸和覆盖已有文件，`obsidian.append_note` 限制在 vault 内，成功与失败都走 ToolRun 审计。
- Executor parallel：仅显式 `execution_mode=parallel` 时启用，只有 read 工具可进入并行 batch，响应顺序保持 plan 顺序。
```

- [ ] **Step 3: Add project contract assertions**

Extend `tests/test_project_contracts.py` with assertions that these strings exist:

```python
assert "depends_on" in read_text("app/agents/planner.py")
assert "execution_mode" in read_text("app/agents/workflow.py")
assert "file.write_text" in read_text("app/tools/registry.py")
assert "obsidian.append_note" in read_text("app/tools/registry.py")
assert "handle_mcp_request" in read_text("app/tools/mcp_server.py")
assert "tools/call" in read_text("app/tools/mcp_server.py")
```

- [ ] **Step 4: Run targeted regression suite**

Run:

```bash
"/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m pytest \
  tests/test_agent_plan.py \
  tests/test_agent_workflow.py \
  tests/test_agents_route.py \
  tests/test_tool_registry.py \
  tests/test_tools_route.py \
  tests/test_mcp_server.py \
  tests/test_project_contracts.py \
  -q
```

Expected result includes:

```text
passed
```

- [ ] **Step 5: Run full CI**

Run:

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected result includes:

```text
passed
database migrations: pending (dry-run)
```

- [ ] **Step 6: Run Docker smoke**

Run:

```bash
docker compose exec -T api bash scripts/smoke_api.sh
```

Expected result:

```text
smoke checks passed
```

- [ ] **Step 7: Run diff hygiene check**

Run:

```bash
git diff --check
```

Expected result: no output and exit code 0.

## Self-Review Checklist

- N5 maps Tool Registry definitions to MCP `inputSchema` and Tool Registry results to MCP content blocks.
- N5 calls always write `ToolRun`; read-only list calls do not write `ToolRun`.
- N5 hides `risk_level="write"` tools by default.
- N3a rejects duplicate step ids, missing dependencies, and cycles before execution.
- N3a skipped steps appear in `AgentRun.steps` and `agent_trace`, but do not write `ToolRun`.
- N3a keeps existing fail-fast semantics for executed failures.
- N4 write tools never bypass `ToolRegistry`.
- N4 file write refuses path escape and existing-file overwrite.
- N4 Obsidian append is constrained to configured vault path.
- N3b parallel mode is opt-in and only uses read tools.
- N3b records results in plan order.
- N3b does not start later batches after a failed batch.
- README, testing docs, roadmap, spec, and task plan statuses stay aligned.
