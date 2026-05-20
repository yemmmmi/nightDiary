"""
反馈 API 路由模块
=================

提供显式反馈（点赞/点踩）和隐式反馈信号（行为事件）的收集端点。
收到反馈后通过 BackgroundTasks 异步更新 Thompson Sampling Beta 分布参数，
确保 API 在 200ms 内响应，不阻塞 UI。

端点：
- POST /api/feedback        — 显式反馈（点赞/点踩 + 可选原因）
- POST /api/feedback/implicit — 隐式信号（read_complete, inspired_writing, frequent_usage）
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.feedback.thompson_sampling import ThompsonSampling
from app.models.feedback import Feedback
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request Schemas ─────────────────────────────────────────────────────────


class ExplicitFeedbackRequest(BaseModel):
    """显式反馈请求：点赞/点踩 + 可选原因"""
    diary_nid: int
    response_style: str  # empathetic | practical | philosophical | humorous
    feedback_type: Literal["positive", "negative"]
    reason: Optional[str] = None  # too_long | too_short | irrelevant | too_generic | lacks_suggestion


class ImplicitFeedbackRequest(BaseModel):
    """隐式反馈请求：行为信号"""
    diary_nid: int
    response_style: str  # empathetic | practical | philosophical | humorous
    signal_type: Literal["read_complete", "inspired_writing", "frequent_usage"]


# ─── Response Schema ─────────────────────────────────────────────────────────


class FeedbackAck(BaseModel):
    """反馈确认响应"""
    success: bool = True
    message: str = "反馈已记录"


# ─── Background Task ─────────────────────────────────────────────────────────


def _update_thompson_sampling(
    user_id: int,
    style: str,
    is_positive: bool,
    db_factory,
) -> None:
    """
    后台任务：更新 Thompson Sampling Beta 分布参数。

    使用独立的数据库会话，避免与请求会话冲突。
    """
    try:
        db: Session = db_factory()
        try:
            ts = ThompsonSampling(db)
            ts.update_reward(user_id=user_id, style=style, is_positive=is_positive)
            logger.debug(
                f"Thompson Sampling 更新完成: user_id={user_id}, "
                f"style={style}, positive={is_positive}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Thompson Sampling 后台更新失败: {e}")


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=FeedbackAck,
    status_code=status.HTTP_200_OK,
    summary="提交显式反馈",
    description="用户对 AI 回应进行点赞或点踩评价，可附带原因。",
)
async def submit_explicit_feedback(
    body: ExplicitFeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    接收显式反馈（点赞/点踩 + 原因），持久化到 Feedback 表，
    然后通过后台任务异步更新 Thompson Sampling 参数。
    """
    # 持久化反馈记录
    feedback = Feedback(
        user_id=current_user.UID,
        diary_nid=body.diary_nid,
        response_style=body.response_style,
        feedback_type=body.feedback_type,
        reason=body.reason,
        source="explicit",
        signal_type=None,
    )
    db.add(feedback)
    db.commit()

    # 后台异步更新 Thompson Sampling（不阻塞响应）
    is_positive = body.feedback_type == "positive"
    from app.core.database import SessionLocal
    background_tasks.add_task(
        _update_thompson_sampling,
        user_id=current_user.UID,
        style=body.response_style,
        is_positive=is_positive,
        db_factory=SessionLocal,
    )

    return FeedbackAck(success=True, message="反馈已记录")


@router.post(
    "/implicit",
    response_model=FeedbackAck,
    status_code=status.HTTP_200_OK,
    summary="提交隐式反馈信号",
    description="采集用户行为作为隐式反馈信号（阅读完成、受启发写作、频繁使用）。",
)
async def submit_implicit_feedback(
    body: ImplicitFeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    接收隐式反馈信号，持久化到 Feedback 表（source='implicit'），
    然后通过后台任务异步更新 Thompson Sampling 参数。

    隐式信号映射：
    - read_complete: 正向信号（用户完整阅读了回应）
    - inspired_writing: 正向信号（用户受启发继续写作）
    - frequent_usage: 正向信号（用户频繁使用 AI 分析）
    """
    # 隐式信号均视为正向反馈
    feedback_type = "positive"

    # 持久化反馈记录
    feedback = Feedback(
        user_id=current_user.UID,
        diary_nid=body.diary_nid,
        response_style=body.response_style,
        feedback_type=feedback_type,
        reason=None,
        source="implicit",
        signal_type=body.signal_type,
    )
    db.add(feedback)
    db.commit()

    # 后台异步更新 Thompson Sampling（不阻塞响应）
    from app.core.database import SessionLocal
    background_tasks.add_task(
        _update_thompson_sampling,
        user_id=current_user.UID,
        style=body.response_style,
        is_positive=True,  # 隐式信号均为正向
        db_factory=SessionLocal,
    )

    return FeedbackAck(success=True, message="反馈已记录")
