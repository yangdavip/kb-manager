"""kb-manager 配置管理"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 数据库
    database_url: str = "postgresql+asyncpg://postgres@127.0.0.1:5433/kb_manager"

    # Embedding API
    embedding_api_base: str = "http://localhost:11434"
    embedding_model: str = "qwen3-embedding:4b"
    embedding_timeout: int = 30
    embedding_batch_size: int = 10

    # 分段配置
    chunk_size: int = 500
    chunk_overlap: int = 50
    chunk_strategy: str = "fixed"

    # 检索配置
    retrieve_top_k: int = 5
    retrieve_distance_metric: str = "cosine"
    retrieve_score_threshold: float = 0.0

    # 文件上传
    file_max_size_mb: int = 50
    file_allowed_types: str = "txt,md,pdf,docx,csv,json,html"

    # 服务器
    host: str = "0.0.0.0"
    port: int = 8900

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def allowed_types_list(self) -> list[str]:
        return [t.strip().lower() for t in self.file_allowed_types.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
