"""向量化引擎 — 调用 Ollama Embedding API

核心机制：
1. Chunk 级状态跟踪：每个 chunk 有独立的 embed_status (pending/done/failed)
2. 分批处理 + 间歇提交：每批 batch_size 个 chunk 向量化后立即写入 DB，不攒到最后
3. 断点续传：reprocess 时跳过已 done 的 chunk，只处理 pending/failed 的
4. 进度查询：通过 file.progress 字段实时返回 (done/total)
5. 超时退避：单个 chunk 3 次重试，指数退避 (2^n)
6. 批量 SQL：用 executemany 或单条 UPDATE 合并写入
"""
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

# Chunk embedding 状态
CHUNK_STATUS_PENDING = "pending"
CHUNK_STATUS_DONE = "done"
CHUNK_STATUS_FAILED = "failed"


async def get_embedding(api_base: str, model: str, text_input: str, timeout: int = 60) -> list[float]:
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
    timeout: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
) -> list[Optional[list[float]]]:
    """批量获取向量（并发 batch_size 个请求，每个请求独立重试）

    返回 list[Optional[list[float]]]，失败的 chunk 对应位置为 None
    """
    results: list[Optional[list[float]]] = [None] * len(texts)
    semaphore = asyncio.Semaphore(batch_size)

    async def _embed_one(idx: int, text_input: str):
        for attempt in range(max_retries):
            try:
                async with semaphore:
                    results[idx] = await get_embedding(api_base, model, text_input, timeout)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"Embedding 重试 {attempt+1}/{max_retries} (chunk {idx}), "
                        f"{wait}s 后重试: {e}"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Embedding 最终失败 (chunk {idx}): {e}")
                    results[idx] = None  # 标记失败，不 raise

    tasks = [_embed_one(i, t) for i, t in enumerate(texts)]
    await asyncio.gather(*tasks)
    return results


async def process_file(
    db: AsyncSession,
    file_id: str,
    api_base: str,
    model: str,
    timeout: int = 60,
    batch_size: int = 10,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    chunk_strategy: str = "fixed",
):
    """完整处理一个文件: 解析 → 分段 → 向量化 → 存储

    断点续传逻辑：
    - 如果文件已有 chunk 记录（status=processing），只对 pending/failed 的 chunk 重新向量化
    - 新文件：创建 chunk 记录 → 向量化 → 写入
    """
    result = await db.execute(select(File).where(File.id == file_id))
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise ValueError(f"文件不存在: {file_id}")

    try:
        file_record.status = "processing"
        file_record.error_message = None
        # 初始化进度：如果之前有 chunk 记录，保留已完成的数量
        existing_done = await db.scalar(
            text("SELECT count(*) FROM chunks WHERE file_id = :fid AND embed_status = 'done'"),
            {"fid": file_id},
        )
        if existing_done and existing_done > 0:
            # 断点续传：跳过解析和分段，直接进入向量化阶段
            logger.info(f"断点续传: {file_record.filename}, 已完成 {existing_done} 个 chunk")
            file_record.progress_done = existing_done
            await db.commit()

            # 查询待处理的 chunk
            chunk_rows = await db.execute(
                text(
                    "SELECT id, content, chunk_index FROM chunks "
                    "WHERE file_id = :fid AND embed_status != 'done' "
                    "ORDER BY chunk_index"
                ),
                {"fid": file_id},
            )
            pending_chunks = chunk_rows.fetchall()
            if not pending_chunks:
                # 全部已完成
                total = await db.scalar(
                    text("SELECT count(*) FROM chunks WHERE file_id = :fid"),
                    {"fid": file_id},
                )
                file_record.chunk_count = total
                file_record.status = "ready"
                file_record.progress_done = total
                file_record.progress_total = total
                await db.commit()
                return

            await _embed_and_store(
                db, file_record, pending_chunks, api_base, model, timeout, batch_size,
                existing_done,
            )
            return

        # 新文件：完整处理流程
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

        # 4. 创建分段记录（不含向量，embed_status=pending）
        chunk_records = []
        for i, c in enumerate(chunks):
            chunk = Chunk(
                file_id=file_record.id,
                chunk_index=i,
                content=c.content,
                char_count=c.char_count,
                char_offset=c.char_offset,
                token_count=c.token_count,
                embed_status=CHUNK_STATUS_PENDING,
                metadata={},
            )
            db.add(chunk)
            chunk_records.append(chunk)
        await db.flush()

        # 5. 分批向量化 + 间歇写入
        await _embed_and_store(
            db, file_record,
            [(str(cr.id), cr.content, cr.chunk_index) for cr in chunk_records],
            api_base, model, timeout, batch_size,
            0,
        )

    except Exception as e:
        logger.error(f"文件处理失败 {file_record.filename}: {e}", exc_info=True)
        file_record.status = "failed"
        file_record.error_message = str(e)
        await db.commit()
        raise


async def _embed_and_store(
    db: AsyncSession,
    file_record: File,
    pending_chunks: list[tuple],  # [(id, content, chunk_index), ...]
    api_base: str,
    model: str,
    timeout: int,
    batch_size: int,
    done_so_far: int,
):
    """分批向量化 + 间歇写入 DB

    - 每批 batch_size 个 chunk 并发向量化
    - 每批完成后立即写入 DB + 更新 file.progress
    - 失败的 chunk 标记 embed_status=failed，不阻断整体流程
    - 最后检查是否有失败的 chunk，决定 file.status
    """
    total_chunks = done_so_far + len(pending_chunks)
    file_record.progress_total = total_chunks
    done_count = done_so_far
    failed_count = 0

    for i in range(0, len(pending_chunks), batch_size):
        batch = pending_chunks[i:i + batch_size]
        texts = [b[1] for b in batch]

        # 批量向量化（内部并发 + 重试）
        embeddings = await get_embeddings_batch(
            api_base, model, texts, timeout, batch_size,
        )

        # 逐条写入（向量写入需要 CAST，无法批量 executemany）
        for (chunk_id, content, chunk_idx), emb in zip(batch, embeddings):
            if emb is not None:
                vec_str = "[" + ",".join(str(v) for v in emb) + "]"
                await db.execute(
                    text(
                        "UPDATE chunks SET "
                        "embedding = CAST(:vec AS vector(2560)), "
                        "embedding_half = CAST(:vec AS halfvec(2560)), "
                        "embed_status = 'done' "
                        "WHERE id = :cid"
                    ),
                    {"vec": vec_str, "cid": chunk_id},
                )
                done_count += 1
            else:
                await db.execute(
                    text(
                        "UPDATE chunks SET embed_status = 'failed' WHERE id = :cid"
                    ),
                    {"cid": chunk_id},
                )
                failed_count += 1

        # 每批提交一次进度
        file_record.progress_done = done_count
        await db.commit()
        logger.info(
            f"批次完成: {file_record.filename}, "
            f"已向量化 {done_count}/{total_chunks}, 失败 {failed_count}"
        )

    # 最终状态
    file_record.chunk_count = total_chunks
    file_record.progress_done = done_count
    if failed_count == 0:
        file_record.status = "ready"
    elif done_count > 0:
        file_record.status = "ready"  # 部分成功也标 ready，允许检索
        file_record.error_message = f"{failed_count} 个片段向量化失败"
    else:
        file_record.status = "failed"
        file_record.error_message = f"全部 {failed_count} 个片段向量化失败"
    await db.commit()
    logger.info(
        f"文件处理完成: {file_record.filename}, "
        f"成功 {done_count}/{total_chunks}, 失败 {failed_count}"
    )
