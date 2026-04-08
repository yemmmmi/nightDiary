"""
用户服务层
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


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


def authenticate_user(db: Session, user_name: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, user_name)
    if user is None or not verify_password(password, user.password_hash):
        return None
    # 更新最后登录时间
    user.last_time = datetime.utcnow()
    db.commit()
    return user
