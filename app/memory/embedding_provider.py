import logging

from openai import OpenAI

from app.config import settings
from app.core.provider_errors import ProviderConfigurationError, ProviderRequestError, retry_provider_call

logger = logging.getLogger(__name__)


class MockEmbeddingProvider:
    """用于本地开发和测试的 deterministic embedding provider。"""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            base = sum(ord(c) for c in text) % 997
            vectors.append([((base + i * 13) % 100) / 100 for i in range(384)])
        return vectors


class OpenAICompatibleEmbeddingProvider:
    """通过 OpenAI-compatible embeddings API 生成真实向量。"""

    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: float, retry_attempts: int) -> None:
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self.model = model
        self.retry_attempts = retry_attempts

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding，返回顺序与输入文本保持一致。"""
        response = retry_provider_call(
            lambda: self.client.embeddings.create(model=self.model, input=texts),
            attempts=self.retry_attempts,
            error_message="embedding provider request failed",
        )
        return [item.embedding for item in response.data]


def build_embedding_provider():
    """根据配置构造 embedding provider；配置错误时显式记录日志。"""
    provider_name = settings.embedding_provider

    if provider_name == "mock":
        return MockEmbeddingProvider()

    if provider_name == "openai-compatible":
        if not settings.embedding_api_key or not settings.embedding_base_url or not settings.embedding_model:
            logger.error("embedding provider config is incomplete")
            raise ProviderConfigurationError("embedding provider config is incomplete")
        return OpenAICompatibleEmbeddingProvider(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
            timeout_seconds=getattr(settings, "provider_timeout_seconds", 120.0),
            retry_attempts=getattr(settings, "provider_retry_attempts", 1),
        )

    raise ValueError(f"unsupported embedding provider: {provider_name}")


def validate_embedding_dimension(vector: list[float], expected_dimension: int) -> None:
    """校验向量维度，避免把不匹配的 embedding 写入或查询 Qdrant。"""
    actual_dimension = len(vector)
    if actual_dimension != expected_dimension:
        logger.error(
            "embedding dimension mismatch: expected=%s actual=%s",
            expected_dimension,
            actual_dimension,
        )
        raise ValueError(f"embedding dimension mismatch: expected {expected_dimension}, got {actual_dimension}")
