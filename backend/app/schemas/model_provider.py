"""
模型提供商相关 Pydantic Schema
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class ModelCreate(BaseModel):
    model_name: str = "未命名"
    model_key: str
    base_url: str

    @field_validator("model_key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model_key 不能为空")
        return v

    @field_validator("base_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("base_url 不能为空")
        return v


class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    model_key: Optional[str] = None
    base_url: Optional[str] = None


class ModelResponse(BaseModel):
    id: int
    model_name: str
    is_active: bool
    base_url: Optional[str]
    create_time: Optional[datetime]
    # model_key_encrypted 不返回，防止泄露

    model_config = {"from_attributes": True}
