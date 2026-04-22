"""
认证路由模块
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse, UserUpdate
from app.services import user_service
from app.services.weather_service import preheat_weather_cache
from app.core.redis import get_redis

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="用户注册")
def register(body: UserCreate, db: Session = Depends(get_db)):
    if user_service.get_user_by_username(db, body.user_name):
        raise HTTPException(status_code=400, detail="用户名已存在")
    return user_service.create_user(db, body)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = user_service.authenticate_user(db, body.user_name, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": str(user.UID), "username": user.user_name})

    # 登录成功后异步预热天气缓存（不阻塞登录响应）
    if user.address:
        asyncio.ensure_future(preheat_weather_cache(user.UID, user.address))

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse, summary="修改个人信息")
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    old_address = current_user.address
    updated_user = user_service.update_user(db, current_user, body)
    new_address = updated_user.address

    # 仅当请求中包含 address 字段且地址发生变化时处理缓存
    if body.address is not None and new_address != old_address:
        redis_client = get_redis()
        # 立即删除旧缓存
        if redis_client:
            try:
                await redis_client.delete(f"weather:{updated_user.UID}")
            except Exception:
                pass
        # 新地址非空时异步预加载新地址天气
        if new_address and new_address.strip():
            asyncio.ensure_future(preheat_weather_cache(updated_user.UID, new_address))

    return updated_user


@router.post("/logout", summary="退出登录")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """退出登录，更新用户的 last_time 字段"""
    user_service.update_last_time(db, current_user)
    return {"message": "退出成功"}


@router.delete("/me", summary="注销账号")
def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除当前用户账号，级联删除关联数据"""
    user_service.delete_user(db, current_user)
    return {"message": "账号已注销"}
