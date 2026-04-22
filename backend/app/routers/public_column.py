"""
公开日记专栏路由模块
======================

提供公开日记专栏的 RESTful API 接口。
列表和详情接口无需认证，发布和下架接口需 JWT 认证。
所有接口均应用 IP 限流。

接口列表：
- GET    /entries              — 公开日记列表（无需认证）
- GET    /entries/{nid}        — 公开日记详情（无需认证）
- POST   /entries/{nid}/publish   — 发布日记到专栏（需 JWT 认证）
- DELETE /entries/{nid}/publish   — 从专栏下架日记（需 JWT 认证）

错误码约定：
- 400: 业务逻辑错误（仅公开日记可发布、日记不在专栏中等）
- 403: 无权访问（日记不存在或不属于当前用户）
- 404: 资源不存在
- 409: 冲突（日记已在专栏中）
- 429: 请求频率超限
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.core.rate_limiter import check_rate_limit
from app.models.user import User
from app.schemas.public_column import PublicDiaryListItem, PublicDiaryDetail, PublishResponse
from app.services import public_column_service

router = APIRouter()


def _set_rate_limit_headers(response: Response, rate_limit_headers: dict) -> None:
    """将限流信息写入响应头"""
    for key, value in rate_limit_headers.items():
        response.headers[key] = value


# ---------------------------------------------------------------------------
# 7.1 公开接口（无需认证）
# ---------------------------------------------------------------------------

@router.get(
    "/entries",
    response_model=List[PublicDiaryListItem],
    summary="公开日记列表",
    description="分页获取公开专栏日记列表，无需认证。按发布时间倒序排列。",
)
async def list_public_entries(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
    rate_limit_headers: dict = Depends(check_rate_limit),
):
    """
    获取公开专栏日记列表。
    支持 skip/limit 分页参数，默认返回前 20 条。
    """
    _set_rate_limit_headers(response, rate_limit_headers)
    entries = await public_column_service.get_public_entries(
        db=db, redis_client=redis_client, skip=skip, limit=limit,
    )
    return entries


@router.get(
    "/entries/{nid}",
    response_model=PublicDiaryDetail,
    summary="公开日记详情",
    description="获取指定公开日记的完整内容，无需认证。",
)
async def get_public_entry_detail(
    nid: int,
    response: Response,
    db: Session = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
    rate_limit_headers: dict = Depends(check_rate_limit),
):
    """
    获取公开日记详情。
    若日记不存在或未发布到专栏，返回 404。
    """
    _set_rate_limit_headers(response, rate_limit_headers)
    detail = await public_column_service.get_public_entry_detail(
        db=db, redis_client=redis_client, nid=nid,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="日记不存在或未公开",
        )
    return detail


# ---------------------------------------------------------------------------
# 7.2 认证接口（需 JWT）
# ---------------------------------------------------------------------------

@router.post(
    "/entries/{nid}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_201_CREATED,
    summary="发布日记到专栏",
    description="将指定日记发布到公开专栏，需 JWT 认证。日记必须为公开状态（is_open=true）。",
)
async def publish_diary(
    nid: int,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
    rate_limit_headers: dict = Depends(check_rate_limit),
):
    """
    发布日记到公开专栏。
    验证：日记归属、is_open=true、未重复发布。
    """
    _set_rate_limit_headers(response, rate_limit_headers)
    try:
        result = await public_column_service.publish_diary(
            db=db, redis_client=redis_client,
            user_id=current_user.UID, nid=nid,
        )
        return result
    except ValueError as exc:
        error_msg = str(exc)
        if "仅公开日记可发布到专栏" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            ) from exc
        elif "日记不存在或无权访问" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg,
            ) from exc
        elif "该日记已在专栏中" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            ) from exc


@router.delete(
    "/entries/{nid}/publish",
    response_model=PublishResponse,
    summary="从专栏下架日记",
    description="将指定日记从公开专栏下架，需 JWT 认证。",
)
async def unpublish_diary(
    nid: int,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
    rate_limit_headers: dict = Depends(check_rate_limit),
):
    """
    从公开专栏下架日记。
    验证：日记归属、已在专栏中。
    """
    _set_rate_limit_headers(response, rate_limit_headers)
    try:
        result = await public_column_service.unpublish_diary(
            db=db, redis_client=redis_client,
            user_id=current_user.UID, nid=nid,
        )
        return result
    except ValueError as exc:
        error_msg = str(exc)
        if "该日记不在专栏中" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            ) from exc
        elif "日记不存在或无权访问" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg,
            ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            ) from exc
