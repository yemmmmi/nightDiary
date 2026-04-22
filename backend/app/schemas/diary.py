"""
日记条目相关 Pydantic Schema
"""

from datetime import datetime, date as DateType
from typing import Optional, List, Union
from pydantic import BaseModel, field_validator
from app.schemas.tag import TagResponse


class DiaryEntryCreate(BaseModel):
    content: str
    is_public: bool = False
    tag_ids: List[int] = []

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("日记内容不能为空")
        return v


class DiaryUpdate(BaseModel):
    content: Optional[str] = None
    is_open: Optional[bool] = None
    tag_ids: Optional[List[int]] = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("日记内容不能为空")
        return v


class DiaryEntryResponse(BaseModel):
    NID: int
    UID: Optional[int] = None
    content: Optional[str] = None
    is_open: bool = True
    date: Union[DateType, None] = None
    weather: Optional[str] = None
    AI_ans: Optional[str] = None
    create_time: Optional[datetime] = None
    published_to_column: bool = False
    publish_time: Optional[datetime] = None
    tags: List[TagResponse] = []

    model_config = {"from_attributes": True}
