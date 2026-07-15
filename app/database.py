"""数据库连接与初始化"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, DateTime, Float,
    ForeignKey, JSON, Index, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    file_type = Column(String(20), nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending/processing/ready/failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_files_status", "status"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
    char_offset = Column(Integer, nullable=False, default=0)
    chunk_metadata = Column(JSONB, default=dict)
    token_count = Column(Integer, nullable=False, default=0)
    # pgvector 向量列 — 使用 raw SQL 创建，此处仅声明用于 ORM 映射
    # embedding 列通过 init_db 中的 SQL 创建: vector(2560)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("File", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_file_id", "file_id"),
        Index("idx_chunks_file_chunk", "file_id", "chunk_index", unique=True),
    )


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    """创建表和向量列、索引"""
    async with engine.begin() as conn:
        # 先确保 pgvector 扩展存在
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        # 添加 token_count 列（如果不存在）
        await conn.execute(text(
            "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS token_count INTEGER DEFAULT 0"
        ))
        # 添加 embedding 向量列（全精度，保留原始向量）
        await conn.execute(text(
            "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(2560)"
        ))
        # 添加 halfvec 列（半精度，用于 HNSW 索引检索）
        # pgvector 0.8.0 HNSW 限制 2000 维，halfvec 限制 4000 维，2560 OK
        await conn.execute(text(
            "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_half halfvec(2560)"
        ))
        # 创建 HNSW 索引（halfvec + cosine）
        # m=16: 每个节点最大连接数（推荐 16-48）
        # ef_construction=64: 构建时候选列表大小（推荐 64-256）
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw "
            "ON chunks USING hnsw (embedding_half halfvec_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        ))
        # 插入默认配置
        await conn.execute(text(
            "INSERT INTO app_config (key, value, description) VALUES "
            "('embedding_api_base', '\"http://localhost:11434\"', 'Embedding API 地址'), "
            "('embedding_model', '\"qwen3-embedding:4b\"', '向量模型名称'), "
            "('embedding_timeout', '30', '请求超时秒数'), "
            "('embedding_batch_size', '10', '批量请求大小'), "
            "('chunk_size', '500', '分段长度'), "
            "('chunk_overlap', '50', '分段重叠'), "
            "('chunk_strategy', '\"fixed\"', '分段策略'), "
            "('retrieve_top_k', '5', '默认返回结果数'), "
            "('retrieve_distance_metric', '\"cosine\"', '距离度量'), "
            "('retrieve_score_threshold', '0.0', '相似度阈值') "
            "ON CONFLICT (key) DO NOTHING"
        ))


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
