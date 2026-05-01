import json
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.chat_persistence import persist_chat_exchange
from app.core.orchestrator import Orchestrator
from app.core.schemas import OpenAICompatChatRequest, OpenAICompatMessage
from app.core.session_identity import resolve_openai_identity
from app.db.database import get_db

router = APIRouter()

MODEL_ID = "personal-ai-os-chat"
MODEL_OWNER = "personal-ai-os"


def _check_authorization(authorization: str | None):
    """校验 Open WebUI 使用的共享兼容层密钥。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    if token != settings.openai_compat_api_key:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def _build_prompt(messages: list[OpenAICompatMessage]) -> str | None:
    """把 OpenAI messages 压成当前 Orchestrator 接受的单条 prompt。"""
    last_user_index = None
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            last_user_index = index
            break

    if last_user_index is None:
        return None

    current_user_message = messages[last_user_index].content
    history = messages[:last_user_index]
    if not history:
        return current_user_message

    history_text = "\n".join(f"{message.role}: {message.content}" for message in history)
    return f"[Open WebUI Context]\n{history_text}\n\n[Current User Message]\n{current_user_message}"


def _get_latest_user_message(messages: list[OpenAICompatMessage]) -> str | None:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return None


def _extract_stream_content(chunk: str) -> str:
    """从 OpenAI-compatible SSE chunk 中提取 assistant 文本用于持久化。"""
    contents: list[str] = []
    for line in chunk.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        for choice in data.get("choices", []):
            delta = choice.get("delta", {})
            content = delta.get("content")
            if content:
                contents.append(content)

    return "".join(contents)


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None)):
    _check_authorization(authorization)
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": 0,
                "owned_by": MODEL_OWNER,
            }
        ],
    }


async def _stream_chat(
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str,
    prompt: str,
    user_message: str,
    model: str,
) -> AsyncIterator[str]:
    """代理流式聊天，并在流结束后保存完整助手回复。"""
    orchestrator = Orchestrator()
    assistant_parts: list[str] = []

    async for chunk in orchestrator.chat_stream(user_id, project_id, session_id, prompt, model=model):
        assistant_parts.append(_extract_stream_content(chunk))
        yield chunk

    persist_chat_exchange(db, user_id, project_id, session_id, user_message, "".join(assistant_parts))
    yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(
    req: OpenAICompatChatRequest,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _check_authorization(authorization)

    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    prompt = _build_prompt(req.messages)
    if prompt is None:
        raise HTTPException(status_code=400, detail="at least one user message is required")
    user_message = _get_latest_user_message(req.messages)
    if user_message is None:
        raise HTTPException(status_code=400, detail="at least one user message is required")

    identity = resolve_openai_identity(req, x_session_id)

    if req.stream:
        return StreamingResponse(
            _stream_chat(
                db,
                identity.user_id,
                identity.project_id,
                identity.session_id,
                prompt,
                user_message,
                req.model or MODEL_ID,
            ),
            media_type="text/event-stream",
        )

    result = Orchestrator().chat(identity.user_id, identity.project_id, identity.session_id, prompt)
    persist_chat_exchange(db, identity.user_id, identity.project_id, identity.session_id, user_message, result["answer"])
    created = int(time.time())

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": req.model or MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["answer"],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
