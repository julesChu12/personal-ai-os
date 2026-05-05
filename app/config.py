from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "personal-ai-os"
    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "personal_ai_os_memories"

    obsidian_vault_path: str = "/data/obsidian"

    minimax_api_key: str | None = None
    minimax_base_url: str | None = None
    minimax_model: str | None = None

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_compat_api_key: str = "EMPTY"
    openai_compat_api_keys: str | None = None
    provider_timeout_seconds: float = 120.0
    provider_retry_attempts: int = 1
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int = 384

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder"

    embedding_provider: str = "mock"
    local_embedding_model: str = "BAAI/bge-small-zh-v1.5"


settings = Settings()
