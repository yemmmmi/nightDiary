"""
用户数据模型 — 对齐 MySQL users 表
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Integer, String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.diary import DiaryEntry


class User(Base):
    __tablename__ = "users"

    UID: Mapped[int] = mapped_column("UID", Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column("user_name", String(50), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column("email", String(100), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column("password_hash", String(255), nullable=False)
    gender: Mapped[Optional[str]] = mapped_column("gender", Enum("M", "F", "Other"), nullable=True)
    age: Mapped[Optional[int]] = mapped_column("age", Integer, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column("phone", String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column("address", String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column("role", String(20), nullable=True, default="user")
    create_time: Mapped[Optional[datetime]] = mapped_column("create_time", DateTime, default=datetime.utcnow)
    last_time: Mapped[Optional[datetime]] = mapped_column("last_time", DateTime, nullable=True)

    diary_entries: Mapped[List["DiaryEntry"]] = relationship(
        "DiaryEntry", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User UID={self.UID} user_name={self.user_name!r}>"
