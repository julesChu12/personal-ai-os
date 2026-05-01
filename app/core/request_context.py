import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request


REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(__name__)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id(default: str | None = None) -> str | None:
    """返回当前请求的 request id；非请求上下文中返回 default。"""
    return _request_id.get() or default


def register_request_context_middleware(app: FastAPI) -> None:
    """为每个请求设置 request id、响应头和结构化请求完成日志。"""

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = _resolve_request_id(request)
        request.state.request_id = request_id
        token = _request_id.set(request_id)
        started_at = time.perf_counter()
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )
            _request_id.reset(token)


def _resolve_request_id(request: Request) -> str:
    inbound_request_id = request.headers.get(REQUEST_ID_HEADER)
    if inbound_request_id and inbound_request_id.strip():
        return inbound_request_id.strip()
    return str(uuid.uuid4())
