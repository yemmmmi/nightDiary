"""
标签相关 Pydantic Schema
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class TagCreate(BaseModel):
    tag_name: str
    color: Optional[str] = "#6B7280"

    @field_validator("tag_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("标签名不能为空")
        if len(v) > 15:
            raise ValueError("标签名不超过 15 字")
        return v


class TagUpdate(BaseModel):
    tag_name: Optional[str] = None
    color: Optional[str] = None

    @field_validator("tag_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("标签名不能为空")
        if len(v) > 15:
            raise ValueError("标签名不超过 15 字")
        return v


class TagResponse(BaseModel):
    id: int
    tag_name: Optional[str]
    color: Optional[str]
    creator: Optional[str]
    usage_count: int
    create_time: Optional[datetime]

    model_config = {"from_attributes": True}
