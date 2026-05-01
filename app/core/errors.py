import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import REQUEST_ID_HEADER, get_request_id


logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register consistent API error handlers while preserving /v1 compatibility."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = str(exc.detail) if exc.detail else _default_message(exc.status_code)
    code = _code_for_status(exc.status_code)
    if _is_openai_compat(request):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": message, "type": _openai_error_type(exc.status_code), "code": code}},
            headers=_merge_headers(request, exc.headers),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "type": "http_error"}},
        headers=_merge_headers(request, exc.headers),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    if _is_openai_compat(request):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "request validation failed",
                    "type": "invalid_request_error",
                    "code": "validation_error",
                }
            },
            headers=_request_id_headers(request),
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "request validation failed",
                "type": "request_validation_error",
            }
        },
        headers=_request_id_headers(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled request error",
        extra={
            "request_id": _request_id_from_request(request, "unknown"),
            "method": request.method,
            "path": request.url.path,
            "status": 500,
            "exception_type": type(exc).__name__,
        },
    )
    if _is_openai_compat(request):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "internal server error",
                    "type": "server_error",
                    "code": "internal_error",
                }
            },
            headers=_request_id_headers(request),
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "internal server error",
                "type": "internal_error",
            }
        },
        headers=_request_id_headers(request),
    )


def _request_id_headers(request: Request) -> dict[str, str]:
    request_id = _request_id_from_request(request)
    if request_id is None:
        return {}
    return {REQUEST_ID_HEADER: request_id}


def _merge_headers(request: Request, headers: dict[str, str] | None) -> dict[str, str]:
    return {**(headers or {}), **_request_id_headers(request)}


def _request_id_from_request(request: Request, default: str | None = None) -> str | None:
    return getattr(request.state, "request_id", None) or get_request_id(default)


def _is_openai_compat(request: Request) -> bool:
    return request.url.path.startswith("/v1/")


def _default_message(status_code: int) -> str:
    return {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
    }.get(status_code, "request failed")


def _code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }.get(status_code, "http_error")


def _openai_error_type(status_code: int) -> str:
    if status_code == 401:
        return "authentication_error"
    if status_code in {400, 404, 409, 422}:
        return "invalid_request_error"
    if status_code == 403:
        return "permission_error"
    return "server_error"
