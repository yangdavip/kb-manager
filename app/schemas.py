"""Pydantic 请求/响应模型"""
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


# ─── File ───
class FileResponse(BaseModel):
    id: UUID
    kb_id: UUID | None = None
    filename: str
    file_size: int
    file_type: str
    content_hash: str | None = None
    chunk_count: int
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    total: int
    items: list[FileResponse]


# ─── Chunk ───
class ChunkResponse(BaseModel):
    id: UUID
    file_id: UUID
    chunk_index: int
    content: str
    char_count: int
    char_offset: int
    metadata: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        data['metadata'] = data.pop('chunk_metadata', None)
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


class ChunkListResponse(BaseModel):
    total: int
    items: list[ChunkResponse]


# ─── Retrieve ───
class RetrieveRequest(BaseModel):
    query: str
    top_k: int | None = None
    distance_metric: str | None = None  # cosine / l2 / inner_product
    score_threshold: float | None = None
    kb_id: UUID | None = None
    file_id: UUID | None = None


class RetrieveResult(BaseModel):
    chunk_id: UUID
    file_id: UUID
    filename: str
    chunk_index: int
    content: str
    score: float
    metadata: dict


class RetrieveResponse(BaseModel):
    query: str
    total: int
    results: list[RetrieveResult]


# ─── Config ───
class ConfigItem(BaseModel):
    key: str
    value: str | int | float
    description: str | None = None


class ConfigResponse(BaseModel):
    items: list[ConfigItem]


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str | int | float


# ─── Stats ───
class StatsResponse(BaseModel):
    total_files: int
    total_chunks: int
    ready_files: int
    processing_files: int
    failed_files: int
    db_size_mb: float
    embedding_dim: int
    vector_index: list[dict] = []
    hnsw_config: dict = {}


# ─── Reprocess ───
class ReprocessResponse(BaseModel):
    file_id: UUID
    status: str
    message: str
