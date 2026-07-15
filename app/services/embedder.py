"""向量化引擎 — 调用 Ollama Embedding API"""
import asyncio
import logging
from typing import Optional

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Chunk, File, AppConfig
from app.services.chunker import chunk_text
from app.services.file_parser import parse_file, compute_hash

logger = logging.getLogger("kb-manager.embedder")


async def get_embedding(api_base: str, model: str, text_input: str, timeout: int = 30) -> list[float]:
    """调用 Ollama /api/embeddings 获取单条文本的向量"""
    url = f"{api_base}/api/embeddings"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json={"model": model, "prompt": text_input})
        resp.raise_for_status()
        data = resp.json()
        return data["embedding"]


async def get_embeddings_batch(
    api_base: str,
    model: str,
    texts: list[str],
    timeout: int = 30,
    batch_size: int = 10,
) -> list[list[float]]:
    """批量获取向量（并发 batch_size 个请求）"""
    results: list[Optional[list[float]]] = [None] * len(texts)

    async def _embed_one(idx: int, text_input: str, retry: int = 3):
        for attempt in range(retry):
            try:
                results[idx] = await get_embedding(api_base, model, text_input, timeout)
                return
            except Exception as e:
                if attempt < retry - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Embedding 请求失败 (attempt {attempt+1}/{retry}), {wait}s 后重试: {e}")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Embedding 请求最终失败 (chunk {idx}): {e}")
                    raise

    # 分批并发
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        tasks = [_embed_one(i + j, t) for j, t in enumerate(batch)]
        await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


async def process_file(
    db: AsyncSession,
    file_id: str,
    api_base: str,
    model: str,
    timeout: int = 30,
    batch_size: int = 10,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    chunk_strategy: str = "fixed",
):
    """完整处理一个文件: 解析 → 分段 → 向量化 → 存储"""
    # 查询文件记录
    result = await db.execute(select(File).where(File.id == file_id))
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise ValueError(f"文件不存在: {file_id}")

    try:
        file_record.status = "processing"
        file_record.error_message = None
        await db.commit()

        # 1. 解析文件
        raw_text = parse_file(file_record.file_path)
        file_record.content_hash = compute_hash(file_record.file_path)

        # 2. 分段
        chunks = chunk_text(raw_text, chunk_size, chunk_overlap, chunk_strategy)
        if not chunks:
            file_record.status = "ready"
            file_record.chunk_count = 0
            file_record.error_message = "文件内容为空"
            await db.commit()
            return

        # 3. 删除旧分段（如果有）
        await db.execute(
            text("DELETE FROM chunks WHERE file_id = :fid"),
            {"fid": file_id},
        )

        # 4. 创建分段记录（不含向量）
        chunk_records = []
        for i, c in enumerate(chunks):
            chunk = Chunk(
                file_id=file_record.id,
                chunk_index=i,
                content=c.content,
                char_count=c.char_count,
                char_offset=c.char_offset,
                metadata={},
            )
            db.add(chunk)
            chunk_records.append(chunk)
        await db.flush()  # 获取 chunk.id

        # 5. 批量向量化
        texts = [c.content for c in chunks]
        embeddings = await get_embeddings_batch(api_base, model, texts, timeout, batch_size)

        # 6. 批量写入向量（全精度 + 半精度同步写入）
        #    embedding: 原始 vector(2560)，用于精确计算
        #    embedding_half: halfvec(2560)，HNSW 索引检索用
        for chunk_rec, embedding in zip(chunk_records, embeddings):
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
            await db.execute(
                text(
                    "UPDATE chunks SET embedding = CAST(:vec AS vector(2560)), "
                    "embedding_half = CAST(:vec AS halfvec(2560)) "
                    "WHERE id = :cid"
                ),
                {"vec": vec_str, "cid": str(chunk_rec.id)},
            )

        file_record.chunk_count = len(chunks)
        file_record.status = "ready"
        await db.commit()
        logger.info(f"文件处理完成: {file_record.filename}, {len(chunks)} 个片段")

    except Exception as e:
        logger.error(f"文件处理失败: {file_record.filename}: {e}", exc_info=True)
        file_record.status = "failed"
        file_record.error_message = str(e)
        await db.commit()
        raise
