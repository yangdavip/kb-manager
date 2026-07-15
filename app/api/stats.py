"""统计信息 API"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, File, Chunk
from app.schemas import StatsResponse

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取系统统计信息"""
    total_files = (await db.execute(select(func.count(File.id)))).scalar() or 0
    total_chunks = (await db.execute(select(func.count(Chunk.id)))).scalar() or 0
    ready_files = (await db.execute(select(func.count(File.id)).where(File.status == "ready"))).scalar() or 0
    processing_files = (await db.execute(select(func.count(File.id)).where(File.status == "processing"))).scalar() or 0
    failed_files = (await db.execute(select(func.count(File.id)).where(File.status == "failed"))).scalar() or 0

    # 数据库大小
    db_size = (await db.execute(text("SELECT pg_database_size(current_database())"))).scalar() or 0
    db_size_mb = round(db_size / 1024 / 1024, 2)

    # 向量维度
    try:
        dim = (await db.execute(
            text("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'")
        )).scalar() or 2560
    except Exception:
        dim = 2560

    # 索引信息
    index_info = []
    try:
        rows = await db.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'chunks' AND indexname LIKE '%hnsw%' OR indexname LIKE '%ivf%'"
        ))
        for r in rows:
            index_info.append({"name": r[0], "def": r[1]})
    except Exception:
        pass

    # HNSW 配置
    hnsw_config = {}
    try:
        ef_search = (await db.execute(text("SHOW hnsw.ef_search"))).scalar()
        hnsw_config["ef_search"] = ef_search
    except Exception:
        pass

    return StatsResponse(
        total_files=total_files,
        total_chunks=total_chunks,
        ready_files=ready_files,
        processing_files=processing_files,
        failed_files=failed_files,
        db_size_mb=db_size_mb,
        embedding_dim=dim,
        vector_index=index_info,
        hnsw_config=hnsw_config,
    )
