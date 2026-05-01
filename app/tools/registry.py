from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.tools.file_tool import read_text, resolve_within_base
from app.tools.git_tool import status as git_status
from app.tools.shell_tool import run_safe


ToolHandler = Callable[[dict[str, Any]], Any]


class ToolNotFoundError(KeyError):
    """工具不存在时抛出，便于 API 层映射为 404。"""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True)
class ToolInvocationResult:
    tool_name: str
    status: str
    output: Any | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "output": self.output,
            "error": self.error,
        }


class ToolRegistry:
    """统一管理可枚举、可调用、可审计的工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._tools[definition.name] = (definition, handler)

    def list_tools(self) -> list[ToolDefinition]:
        return [self._tools[name][0] for name in sorted(self._tools)]

    def get_definition(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name][0]

    def invoke(self, name: str, input_payload: dict[str, Any] | None = None) -> ToolInvocationResult:
        if name not in self._tools:
            raise ToolNotFoundError(name)

        _, handler = self._tools[name]
        try:
            output = handler(input_payload or {})
        except Exception as exc:
            return ToolInvocationResult(tool_name=name, status="error", error=str(exc))
        return ToolInvocationResult(tool_name=name, status="ok", output=output)


def build_default_tool_registry(base_dir: str = ".") -> ToolRegistry:
    registry = ToolRegistry()
    resolved_base = str(Path(base_dir).resolve())

    registry.register(
        ToolDefinition(
            name="file.read_text",
            description="Read a UTF-8 text file inside the allowed workspace.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            risk_level="read",
        ),
        lambda payload: read_text(_required_string(payload, "path"), base_dir=resolved_base),
    )
    registry.register(
        ToolDefinition(
            name="git.status",
            description="Run git status inside the allowed workspace.",
            input_schema={
                "type": "object",
                "properties": {"cwd": {"type": "string"}},
            },
            risk_level="read",
        ),
        lambda payload: git_status(cwd=_resolve_cwd(payload, resolved_base)),
    )
    registry.register(
        ToolDefinition(
            name="shell.run_safe",
            description="Run a small allowlisted shell command inside the allowed workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "enum": ["pwd", "ls", "git status"]},
                    "cwd": {"type": "string"},
                },
                "required": ["command"],
            },
            risk_level="guarded",
        ),
        lambda payload: run_safe(_required_string(payload, "command"), cwd=_resolve_cwd(payload, resolved_base)),
    )
    return registry


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _resolve_cwd(payload: dict[str, Any], base_dir: str) -> str:
    cwd = payload.get("cwd") or "."
    if not isinstance(cwd, str):
        raise ValueError("cwd must be a string")
    path = resolve_within_base(cwd, base_dir)
    if not path.is_dir():
        raise ValueError("cwd is not a directory")
    return str(path)
