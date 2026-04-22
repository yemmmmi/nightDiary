"""
标签模型 — 对齐 MySQL tags 表
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, Table, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.diary import DiaryEntry

# M:N 关联表
diary_tag_association = Table(
    "diary_tags",
    Base.metadata,
    Column("diary_id", Integer, ForeignKey("diary_entries.NID", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",   Integer, ForeignKey("tags.TID",           ondelete="CASCADE"), primary_key=True),
    Column("create_time", DateTime, server_default=func.now()),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column("TID", Integer, primary_key=True, autoincrement=True)
    tag_name: Mapped[Optional[str]] = mapped_column("TagName", String(15), nullable=True, unique=True)
    color: Mapped[Optional[str]] = mapped_column("color", String(20), nullable=True, default="#6B7280")
    creator: Mapped[Optional[str]] = mapped_column("creator", String(50), nullable=True)
    usage_count: Mapped[int] = mapped_column("Usagecnt", Integer, nullable=False, default=0)
    create_time: Mapped[Optional[datetime]] = mapped_column("create_time", DateTime, default=datetime.utcnow)

    diary_entries: Mapped[List["DiaryEntry"]] = relationship(
        "DiaryEntry",
        secondary=diary_tag_association,
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"<Tag id={self.id} tag_name={self.tag_name!r}>"
