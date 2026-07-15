"""配置管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AppConfig
from app.schemas import ConfigItem, ConfigResponse, ConfigUpdateRequest

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    """获取所有配置"""
    result = await db.execute(select(AppConfig).order_by(AppConfig.key))
    rows = result.scalars().all()
    return ConfigResponse(
        items=[ConfigItem(key=r.key, value=r.value, description=r.description) for r in rows]
    )


@router.put("")
async def update_config(
    req: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新单个配置项"""
    result = await db.execute(select(AppConfig).where(AppConfig.key == req.key))
    config_item = result.scalar_one_or_none()
    if not config_item:
        # 创建新配置
        config_item = AppConfig(key=req.key, value=req.value)
        db.add(config_item)
    else:
        config_item.value = req.value
    await db.commit()
    return {"message": "配置已更新", "key": req.key, "value": req.value}
