import json
import time
import uuid
from typing import AsyncIterator

import httpx
from openai import OpenAI
from app.config import settings
from app.core.provider_errors import ProviderRequestError, retry_provider_call


def _is_minimax_endpoint(url: str) -> bool:
    return bool(url) and ("minimax" in url.lower() or "minimaxi" in url.lower())


def _transform_to_anthropic_format(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-style messages to Anthropic /v1/messages format.

    MiniMax Anthropic API does not support multiple system messages,
    so we merge all system messages into one.
    """
    system_parts: list[str] = []
    result: list[dict] = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]

        if role == "system":
            for block in content:
                if block.get("type") == "text":
                    system_parts.append(block["text"])
        else:
            if system_parts:
                result.append({"role": "system", "content": [{"type": "text", "text": "\n\n".join(system_parts)}]})
                system_parts = []
            result.append({"role": role, "content": content})

    if system_parts:
        result.insert(0, {"role": "system", "content": [{"type": "text", "text": "\n\n".join(system_parts)}]})

    return result


def _parse_sse_line(line: str) -> tuple[str, str] | None:
    """Parse a single SSE line. Returns (event, data) or None."""
    line = line.rstrip("\n\r")
    if line.startswith("event:"):
        return ("event", line[6:].strip())
    if line.startswith("data:"):
        return ("data", line[5:].strip())
    return None


def _make_chunk(id_: str, created: int, model: str, content: str | None = None, role: str | None = None, finish: bool = False) -> str:
    delta = {}
    if role:
        delta["role"] = role
    if content:
        delta["content"] = content
    finish_reason = "stop" if finish else None
    return f'data: {json.dumps({"id": id_, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]})}\n\n'


class ModelRouter:
    """根据运行配置选择 mock、OpenAI-compatible 或 MiniMax 模型后端。"""

    def __init__(self) -> None:
        self.provider = "mock"
        self.model = "mock"
        self._minimax_api_key: str | None = None
        self._minimax_base_url: str | None = None
        self.provider_timeout_seconds = getattr(settings, "provider_timeout_seconds", 120.0)
        self.provider_retry_attempts = getattr(settings, "provider_retry_attempts", 1)

        # Priority 1: MiniMax Anthropic-compatible endpoint via OPENAI_BASE_URL
        if settings.openai_api_key and _is_minimax_endpoint(settings.openai_base_url):
            self.provider = "minimax"
            self._minimax_api_key = settings.openai_api_key
            self._minimax_base_url = settings.openai_base_url.rstrip("/")
            self.model = settings.openai_model
        # Priority 2: Standard OpenAI-compatible
        elif settings.openai_api_key and settings.openai_base_url:
            self.provider = "openai"
            self._client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=self.provider_timeout_seconds,
                max_retries=0,
            )
            self.model = settings.openai_model
        # Priority 3: MiniMax native config
        elif settings.minimax_api_key and settings.minimax_base_url and settings.minimax_model:
            self.provider = "minimax"
            self._minimax_api_key = settings.minimax_api_key
            self._minimax_base_url = settings.minimax_base_url.rstrip("/")
            self.model = settings.minimax_model

    def chat(self, messages: list[dict], model: str | None = None, **kwargs) -> str:
        """统一的非流式聊天接口；未配置真实模型时返回可诊断 mock 响应。"""
        model = model or self.model

        if self.provider == "minimax":
            anthropic_messages = _transform_to_anthropic_format(messages)
            with httpx.Client(timeout=httpx.Timeout(self.provider_timeout_seconds)) as client:
                def call_minimax():
                    response = client.post(
                        f"{self._minimax_base_url}/v1/messages",
                        headers={
                            "Authorization": f"Bearer {self._minimax_api_key}",
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": anthropic_messages,
                            "max_tokens": 4096,
                        },
                    )
                    response.raise_for_status()
                    return response

                resp = retry_provider_call(
                    call_minimax,
                    attempts=self.provider_retry_attempts,
                    error_message="model provider request failed",
                )
                data = resp.json()
                content_blocks = data.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "text":
                        return block["text"]
                return str(content_blocks)

        if hasattr(self, "_client") and self._client:
            resp = retry_provider_call(
                lambda: self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=kwargs.get("temperature", 0.2),
                ),
                attempts=self.provider_retry_attempts,
                error_message="model provider request failed",
            )
            return resp.choices[0].message.content or ""

        last = messages[-1]["content"] if messages else ""
        return f"[MOCK:{self.provider}] 已收到：{last}\n\n配置 MINIMAX 或 OPENAI API 后可启用真实模型。"

    async def chat_stream(self, messages: list[dict], model: str | None = None) -> AsyncIterator[str]:
        """把各模型后端的流式输出统一转换为 OpenAI-compatible SSE chunk。"""
        model = model or self.model
        created = int(time.time())
        id_ = f"chatcmpl-{uuid.uuid4().hex}"

        if self.provider == "minimax":
            anthropic_messages = _transform_to_anthropic_format(messages)
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.provider_timeout_seconds)) as client:
                    async with client.stream(
                        "POST",
                        f"{self._minimax_base_url}/v1/messages",
                        headers={
                            "Authorization": f"Bearer {self._minimax_api_key}",
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": anthropic_messages,
                            "max_tokens": 4096,
                            "stream": True,
                        },
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            parsed = _parse_sse_line(line)
                            if not parsed:
                                continue
                            kind, value = parsed

                            if kind == "event":
                                event_type = value
                                if event_type == "message_start":
                                    yield _make_chunk(id_, created, model, role="assistant")
                                elif event_type == "message_stop":
                                    yield _make_chunk(id_, created, model, finish=True)
                            elif kind == "data":
                                try:
                                    data = json.loads(value)
                                except json.JSONDecodeError:
                                    continue

                                delta_type = data.get("type", "")
                                if delta_type == "content_block_delta":
                                    delta = data.get("delta", {})
                                    delta_kind = delta.get("type", "")
                                    if delta_kind == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            yield _make_chunk(id_, created, model, content=text)
                                    # Skip thinking_delta and signature_delta
                                elif delta_type == "message_delta":
                                    # Send final chunk with finish_reason
                                    yield _make_chunk(id_, created, model, finish=True)
            except ProviderRequestError:
                raise
            except Exception as exc:
                raise ProviderRequestError("model provider request failed") from exc
            return

        if hasattr(self, "_client") and self._client:
            stream = retry_provider_call(
                lambda: self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=0.2,
                ),
                attempts=self.provider_retry_attempts,
                error_message="model provider request failed",
            )
            for chunk in stream:
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Mock
        yield _make_chunk(id_, created, model, role="assistant")
        yield _make_chunk(id_, created, model, content=f"[MOCK] 已收到。配置 API Key 后可启用真实模型。", finish=True)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """历史兼容的 deterministic embedding；新向量路径应使用 embedding_provider。"""
        vectors = []
        for text in texts:
            base = sum(ord(c) for c in text) % 997
            vectors.append([((base + i * 13) % 100) / 100 for i in range(384)])
        return vectors
