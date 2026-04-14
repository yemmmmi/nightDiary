"""
用户服务层
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_user_by_username(db: Session, user_name: str) -> Optional[User]:
    return db.query(User).filter(User.user_name == user_name).first()


def get_user_by_id(db: Session, uid: int) -> Optional[User]:
    return db.query(User).filter(User.UID == uid).first()


def create_user(db: Session, body: UserCreate) -> User:
    user = User(
        user_name=body.user_name,
        email=body.email,
        password_hash=hash_password(body.password),
        phone=body.phone,
        age=body.age,
        gender=body.gender,
        address=body.address,
        role="user",
        create_time=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def update_user(db: Session, user: User, body: UserUpdate) -> User:
    update_data = body.model_dump(exclude_unset=True)

    # 如果修改 user_name，检查唯一性
    if "user_name" in update_data and update_data["user_name"] is not None:
        existing = get_user_by_username(db, update_data["user_name"])
        if existing and existing.UID != user.UID:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="用户名已存在")

    # 如果修改 email，检查格式和唯一性（MVP 简化：跳过验证码，仅校验格式和唯一性）
    if "email" in update_data and update_data["email"] is not None:
        import re
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", update_data["email"]):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        existing = get_user_by_email(db, update_data["email"])
        if existing and existing.UID != user.UID:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="邮箱已被使用")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, user_name: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, user_name)
    if user is None or not verify_password(password, user.password_hash):
        return None
    # 更新最后登录时间
    user.last_time = datetime.utcnow()
    db.commit()
    return user


def update_last_time(db: Session, user: User) -> User:
    """更新用户的 last_time 字段为当前时间（用于退出登录等场景）"""
    user.last_time = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    """物理删除用户，级联删除关联的日记、分析等记录"""
    db.delete(user)
    db.commit()
