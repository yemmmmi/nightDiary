"""
日记条目数据模型 — 对齐 MySQL diary_entries 表
"""

from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Integer, Text, DateTime, Date, ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.tag import diary_tag_association

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.analysis import Analysis
    from app.models.tag import Tag


class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    NID: Mapped[int] = mapped_column("NID", Integer, primary_key=True, autoincrement=True)
    UID: Mapped[Optional[int]] = mapped_column("UID", Integer, ForeignKey("users.UID"), nullable=True)
    content: Mapped[Optional[str]] = mapped_column("content", Text, nullable=True)
    is_open: Mapped[bool] = mapped_column("is_open", Boolean, default=True, nullable=True)  # 1=公开
    date: Mapped[Optional[date]] = mapped_column("date", Date, nullable=True)
    weather: Mapped[Optional[str]] = mapped_column("weather", String(50), nullable=True)
    AI_ans: Mapped[Optional[str]] = mapped_column("AI_ans", Text, nullable=True)
    create_time: Mapped[Optional[datetime]] = mapped_column("create_time", DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="diary_entries")
    analysis: Mapped[Optional["Analysis"]] = relationship(
        "Analysis", back_populates="diary_entry", uselist=False, cascade="all, delete-orphan"
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=diary_tag_association, back_populates="diary_entries"
    )

    def __repr__(self) -> str:
        return f"<DiaryEntry NID={self.NID} UID={self.UID}>"
