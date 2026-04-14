"""
用户相关 Pydantic Schema — 对齐新字段名
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class UserCreate(BaseModel):
    user_name: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Literal["M", "F", "Other"]] = None
    address: Optional[str] = None


class UserUpdate(BaseModel):
    user_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Literal["M", "F", "Other"]] = None
    address: Optional[str] = None


class UserResponse(BaseModel):
    UID: int
    user_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    role: Optional[str] = None
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    user_name: str
    password: str
