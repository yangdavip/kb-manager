"""检索 API"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AppConfig
from app.schemas import RetrieveRequest, RetrieveResponse, RetrieveResult
from app.services.retriever import retrieve
from app.config import get_settings

router = APIRouter(prefix="/api/v1/retrieve", tags=["retrieve"])
settings = get_settings()


async def _get_config_dict(db: AsyncSession) -> dict:
    result = await db.execute(select(AppConfig))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.post("", response_model=RetrieveResponse)
async def retrieve_endpoint(
    req: RetrieveRequest,
    db: AsyncSession = Depends(get_db),
):
    """语义检索"""
    config = await _get_config_dict(db)

    results = await retrieve(
        db=db,
        query=req.query,
        top_k=req.top_k or int(config.get("retrieve_top_k", settings.retrieve_top_k)),
        distance_metric=req.distance_metric or config.get("retrieve_distance_metric", settings.retrieve_distance_metric),
        score_threshold=req.score_threshold if req.score_threshold is not None else float(config.get("retrieve_score_threshold", settings.retrieve_score_threshold)),
        api_base=config.get("embedding_api_base", settings.embedding_api_base),
        model=config.get("embedding_model", settings.embedding_model),
        timeout=int(config.get("embedding_timeout", settings.embedding_timeout)),
        kb_id=req.kb_id,
        file_id=req.file_id,
    )

    return RetrieveResponse(
        query=req.query,
        total=len(results),
        results=[RetrieveResult(**r) for r in results],
    )
