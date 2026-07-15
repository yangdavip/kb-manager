"""检索引擎 — 基于 pgvector 的向量相似度检索"""
import logging
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AppConfig

logger = logging.getLogger("kb-manager.retriever")

# 距离度量 → pgvector 操作符映射
DISTANCE_OPS = {
    "cosine": "<=>",        # 余弦距离
    "l2": "<->",             # 欧氏距离
    "inner_product": "<#>",  # 内积（负值）
}


async def retrieve(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    distance_metric: str = "cosine",
    score_threshold: float = 0.0,
    api_base: str = "http://localhost:11434",
    model: str = "qwen3-embedding:4b",
    timeout: int = 30,
    kb_id: UUID | None = None,
    file_id: UUID | None = None,
) -> list[dict]:
    """语义检索 — 使用 halfvec + HNSW 索引加速

    检索流程：
    1. 调用 Embedding API 获取查询向量
    2. 设置 hnsw.ef_search 控制召回率（默认 40，设为 top_k*4 保证召回）
    3. 用 halfvec 列走 HNSW 索引检索（近似最近邻）
    4. 用全精度 embedding 列重排（精排，提升精度）

    Returns:
        list of dict: [{chunk_id, file_id, filename, chunk_index, content, score, metadata}]
    """
    op = DISTANCE_OPS.get(distance_metric, "<=>")

    # 1. 获取查询向量
    url = f"{api_base}/api/embeddings"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json={"model": model, "prompt": query})
        resp.raise_for_status()
        query_vec = resp.json()["embedding"]

    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    # 2. 设置 HNSW ef_search（越大召回越高，但越慢）
    #    取 max(40, top_k * 4) 保证足够候选
    ef_search = max(40, top_k * 4)
    await db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))

    # 3. 构建 SQL — HNSW 索引检索 + 精排
    #    用 embedding_half 走 HNSW 索引获取候选（ORDER BY...LIMIT）
    #    用全精度 embedding 重排计算最终 score
    #    使用 CAST(:vec AS halfvec(2560)) 避免与 SQLAlchemy 参数绑定冲突
    sql = f"""
        WITH candidates AS (
            SELECT c.id, c.file_id, f.filename, c.chunk_index, c.content, c.chunk_metadata,
                   c.embedding,
                   (c.embedding_half {op} CAST(:vec AS halfvec(2560)))::float AS approx_score
            FROM chunks c
            JOIN files f ON f.id = c.file_id
            WHERE c.embedding_half IS NOT NULL
              AND c.embed_status = 'done'
              AND f.status = 'ready'
    """
    params: dict = {"vec": vec_str}

    if kb_id is not None:
        sql += " AND f.kb_id = :kb_id"
        params["kb_id"] = str(kb_id)

    if file_id is not None:
        sql += " AND f.file_id = :file_id"
        params["file_id"] = str(file_id)

    # HNSW 近似检索取候选（取 3 倍 top_k 候选用于精排）
    candidate_k = min(top_k * 3, 100)
    sql += f"""
            ORDER BY c.embedding_half {op} CAST(:vec AS halfvec(2560))
            LIMIT :candidate_k
        )
        SELECT id, file_id, filename, chunk_index, content, chunk_metadata,
               (embedding {op} CAST(:vec AS vector(2560)))::float AS exact_score
        FROM candidates
        ORDER BY exact_score
        LIMIT :top_k
    """
    params["candidate_k"] = candidate_k
    params["top_k"] = top_k

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    results = []
    for row in rows:
        score = float(row.exact_score)
        # 对于余弦距离，转换为相似度分数 (0~1)
        if distance_metric == "cosine":
            similarity = 1.0 - score
        elif distance_metric == "l2":
            similarity = 1.0 / (1.0 + score)
        else:
            similarity = -score

        if similarity < score_threshold:
            continue

        results.append({
            "chunk_id": str(row.id),
            "file_id": str(row.file_id),
            "filename": row.filename,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "score": round(similarity, 4),
            "metadata": row.chunk_metadata or {},
        })

    return results
