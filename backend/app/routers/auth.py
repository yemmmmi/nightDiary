"""
认证路由模块
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="用户注册")
def register(body: UserCreate, db: Session = Depends(get_db)):
    if user_service.get_user_by_username(db, body.user_name):
        raise HTTPException(status_code=400, detail="用户名已存在")
    return user_service.create_user(db, body)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = user_service.authenticate_user(db, body.user_name, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": str(user.UID), "username": user.user_name})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse, summary="修改个人信息")
def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_service.update_user(db, current_user, body)


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
