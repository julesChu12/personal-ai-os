#!/usr/bin/env python3
"""run_mcp_server.py: JSON-RPC stdio entrypoint for local MCP clients."""

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
