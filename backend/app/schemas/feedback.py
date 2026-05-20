"""
用户反馈相关 Pydantic Schema
============================

数据流向：
- FeedbackCreate: 前端请求 → 后端（提交显式/隐式反馈）
- FeedbackResponse: 后端 → 前端（返回反馈记录）
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    """
    创建反馈请求。
    支持显式反馈（点赞/点踩 + 原因）和隐式反馈（行为信号）。
    """
    diary_nid: int
    response_style: str  # empathetic | practical | philosophical | humorous
    feedback_type: Literal["positive", "negative"]
    reason: Optional[str] = None  # too_long | too_short | irrelevant | too_generic | lacks_suggestion
    source: Literal["explicit", "implicit"] = "explicit"
    signal_type: Optional[str] = None  # read_complete | inspired_writing | frequent_usage


class FeedbackResponse(BaseModel):
    """
    反馈记录响应。
    返回给前端展示的反馈信息。
    """
    id: int
    user_id: int
    diary_nid: int
    response_style: str
    feedback_type: str
    reason: Optional[str] = None
    source: str
    signal_type: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
