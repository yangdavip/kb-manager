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
    """语义检索

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

    # 2. 构建 SQL — pgvector 相似度检索
    sql = f"""
        SELECT c.id, c.file_id, f.filename, c.chunk_index, c.content, c.chunk_metadata,
               (c.embedding {op} :vec)::float AS score
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        WHERE c.embedding IS NOT NULL
          AND f.status = 'ready'
    """
    params: dict = {"vec": vec_str}

    if kb_id is not None:
        sql += " AND f.kb_id = :kb_id"
        params["kb_id"] = str(kb_id)

    if file_id is not None:
        sql += " AND f.file_id = :file_id"
        params["file_id"] = str(file_id)

    # 余弦距离: score 越小越相似 → 转换为相似度 (1 - distance)
    # l2 距离: score 越小越相似
    # inner_product: score 越负越相似 → 取负值
    sql += f" ORDER BY c.embedding {op} :vec LIMIT :top_k"
    params["top_k"] = top_k

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    results = []
    for row in rows:
        score = float(row.score)
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
