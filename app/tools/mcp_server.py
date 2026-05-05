from typing import Any

from sqlalchemy.orm import Session

from app.tools.audit import record_tool_run
from app.tools.mcp_adapter import MCP_EXPOSED_RISK_LEVELS, list_mcp_tools, mcp_result_from_tool_result
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
    if definition.risk_level not in MCP_EXPOSED_RISK_LEVELS:
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
