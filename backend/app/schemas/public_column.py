"""
公开日记专栏相关 Pydantic Schema
"""

from datetime import datetime, date as DateType
from typing import Optional, List
from pydantic import BaseModel

from app.schemas.tag import TagResponse


class PublicDiaryListItem(BaseModel):
    """列表项：摘要信息"""
    NID: int
    author_name: str
    content_summary: str  # 前 200 字
    publish_time: datetime
    tags: List[TagResponse] = []

    model_config = {"from_attributes": True}


class PublicDiaryDetail(BaseModel):
    """详情：完整内容"""
    NID: int
    author_name: str
    content: str
    date: Optional[DateType] = None
    weather: Optional[str] = None
    publish_time: datetime
    tags: List[TagResponse] = []

    model_config = {"from_attributes": True}


class PublishResponse(BaseModel):
    """发布/下架响应"""
    message: str
    nid: int
