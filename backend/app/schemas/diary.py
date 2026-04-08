"""
日记条目相关 Pydantic Schema
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class DiaryEntryCreate(BaseModel):
    content: str
    mood: Optional[str] = None
    is_public: bool = False

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("日记内容不能为空")
        return v


class DiaryEntryResponse(BaseModel):
    id: int
    user_id: int
    mood: Optional[str] = None
    content: str
    is_public: bool
    weather: Optional[str] = None
    ai_comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
