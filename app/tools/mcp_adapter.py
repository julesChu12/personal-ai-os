import json
from typing import Any

from app.tools.registry import ToolInvocationResult, ToolRegistry

MCP_EXPOSED_RISK_LEVELS = {"read", "guarded"}


def list_mcp_tools(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Expose read-safe ToolRegistry definitions in MCP tool shape."""
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
