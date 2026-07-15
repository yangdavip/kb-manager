"""文件管理 API"""
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, File, Chunk, AppConfig, async_session
from app.schemas import FileResponse, FileListResponse, ChunkResponse, ChunkListResponse, ReprocessResponse
from app.config import get_settings
from app.services.file_parser import compute_hash
from app.services.embedder import process_file

router = APIRouter(prefix="/api/v1/files", tags=["files"])
settings = get_settings()

# 文件存储目录
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """上传文件"""
    # 验证文件类型
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_types_list:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": f"不支持的文件类型: {ext}"})

    # 验证文件大小
    content = await file.read()
    max_bytes = settings.file_max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": f"文件大小超过限制: {settings.file_max_size_mb}MB"})

    # 保存文件
    file_id = uuid.uuid4()
    file_dir = STORAGE_DIR / str(file_id)
    file_dir.mkdir(exist_ok=True)
    file_path = file_dir / file.filename
    with open(file_path, "wb") as f:
        f.write(content)

    # 计算哈希
    content_hash = compute_hash(str(file_path))

    # 创建数据库记录
    file_record = File(
        id=file_id,
        filename=file.filename,
        file_path=str(file_path),
        file_size=len(content),
        file_type=ext,
        content_hash=content_hash,
        status="pending",
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    # 后台处理: 分段 + 向量化
    background_tasks.add_task(_process_file_background, str(file_id))

    return FileResponse.model_validate(file_record)


async def _process_file_background(file_id: str):
    """后台任务: 获取配置并处理文件"""
    from app.database import async_session

    async with async_session() as db:
        # 从数据库读取配置
        config = await _get_config_dict(db)
        await process_file(
            db=db,
            file_id=file_id,
            api_base=config.get("embedding_api_base", settings.embedding_api_base),
            model=config.get("embedding_model", settings.embedding_model),
            timeout=int(config.get("embedding_timeout", settings.embedding_timeout)),
            batch_size=int(config.get("embedding_batch_size", settings.embedding_batch_size)),
            chunk_size=int(config.get("chunk_size", settings.chunk_size)),
            chunk_overlap=int(config.get("chunk_overlap", settings.chunk_overlap)),
            chunk_strategy=config.get("chunk_strategy", settings.chunk_strategy),
        )


async def _get_config_dict(db: AsyncSession) -> dict:
    """从 app_config 表读取所有配置"""
    result = await db.execute(select(AppConfig))
    rows = result.scalars().all()
    config = {}
    for row in rows:
        config[row.key] = row.value
    return config


@router.get("", response_model=FileListResponse)
async def list_files(
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取文件列表"""
    query = select(File)
    if status:
        query = query.where(File.status == status)
    query = query.order_by(File.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    count_query = select(func.count(File.id))
    if status:
        count_query = count_query.where(File.status == status)
    total = (await db.execute(count_query)).scalar()

    return FileListResponse(
        total=total,
        items=[FileResponse.model_validate(f) for f in items],
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: str, db: AsyncSession = Depends(get_db)):
    """获取文件详情"""
    result = await db.execute(select(File).where(File.id == file_id))
    file_record = result.scalar_one_or_none()
    if not file_record:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    return FileResponse.model_validate(file_record)


@router.delete("/{file_id}")
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db)):
    """删除文件及其分段和向量"""
    result = await db.execute(select(File).where(File.id == file_id))
    file_record = result.scalar_one_or_none()
    if not file_record:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    # 删除数据库记录（级联删除 chunks）
    await db.execute(delete(File).where(File.id == file_id))
    await db.commit()

    # 删除物理文件
    file_dir = STORAGE_DIR / file_id
    if file_dir.exists():
        shutil.rmtree(file_dir, ignore_errors=True)

    return {"message": "删除成功", "file_id": file_id}


@router.post("/{file_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_file(
    file_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """重新分段+向量化"""
    result = await db.execute(select(File).where(File.id == file_id))
    file_record = result.scalar_one_or_none()
    if not file_record:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    file_record.status = "pending"
    file_record.error_message = None
    await db.commit()

    background_tasks.add_task(_process_file_background, file_id)

    return ReprocessResponse(
        file_id=file_record.id,
        status="pending",
        message="已加入处理队列",
    )


@router.get("/{file_id}/chunks", response_model=ChunkListResponse)
async def get_chunks(
    file_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """获取文件的分段列表"""
    # 验证文件存在
    result = await db.execute(select(File).where(File.id == file_id))
    if not result.scalar_one_or_none():
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "文件不存在"})

    query = (
        select(Chunk)
        .where(Chunk.file_id == file_id)
        .order_by(Chunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    count = (
        await db.execute(
            select(func.count(Chunk.id)).where(Chunk.file_id == file_id)
        )
    ).scalar()

    return ChunkListResponse(
        total=count,
        items=[ChunkResponse.from_orm(c) for c in items],
    )
