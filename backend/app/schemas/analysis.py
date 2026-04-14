"""
AI 分析相关 Pydantic Schema
============================

数据流向：
- AnalysisCreate: 前端请求 → 后端（触发分析）
- AnalysisResponse: 后端 → 前端（返回分析结果）
- AnalysisUpdate: 前端请求 → 后端（重新分析，需检查防重）
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AnalysisCreate(BaseModel):
    """
    创建分析请求。
    前端只需提供日记 NID，后端自动读取日记内容和标签，调用 AI 生成分析。
    """
    nid: int  # 要分析的日记 ID


class AnalysisResponse(BaseModel):
    """
    分析结果响应。
    返回给前端展示的完整分析信息。
    注意：字段名需与 Analysis SQLAlchemy 模型的 Python 属性名一致（from_attributes=True）
    """
    Thk_ID: int
    NID: int
    Thk_time: Optional[datetime] = None
    Token_cost: Optional[int] = None
    cache_hit_tokens: Optional[int] = None     # 缓存命中（免费）
    cache_miss_tokens: Optional[int] = None    # 缓存未命中（付费输入）
    output_tokens: Optional[int] = None        # 输出 token（付费）
    Thk_log: Optional[str] = None
    diary_length: Optional[int] = None

    model_config = {"from_attributes": True}


class AnalysisUpdate(BaseModel):
    """
    更新分析请求（重新生成）。
    前端只需提供日记 NID，后端会检查日记内容是否有变化（防重机制）。
    """
    nid: int  # 要重新分析的日记 ID
