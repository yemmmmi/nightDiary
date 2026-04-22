"""
AI 分析记录模型 — 对齐 MySQL analysis 表
Token 消耗分为: cache_hit(免费)、cache_miss(付费输入)、output(付费输出)
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.diary import DiaryEntry


class Analysis(Base):
    __tablename__ = "analysis"

    Thk_ID: Mapped[int] = mapped_column("Thk_ID", Integer, primary_key=True, autoincrement=True)
    NID: Mapped[int] = mapped_column("NID", Integer, ForeignKey("diary_entries.NID"), nullable=False, index=True)
    Thk_time: Mapped[Optional[datetime]] = mapped_column("Thk_time", DateTime, default=datetime.utcnow)
    Token_cost: Mapped[Optional[int]] = mapped_column("Token_cost", Integer, nullable=True)
    cache_hit_tokens: Mapped[Optional[int]] = mapped_column("cache_hit_tokens", Integer, nullable=True)
    cache_miss_tokens: Mapped[Optional[int]] = mapped_column("cache_miss_tokens", Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column("output_tokens", Integer, nullable=True)
    Thk_log: Mapped[Optional[str]] = mapped_column("Thk_log", Text, nullable=True)
    diary_length: Mapped[Optional[int]] = mapped_column("diary_length", Integer, nullable=True)

    diary_entry: Mapped["DiaryEntry"] = relationship("DiaryEntry", back_populates="analysis")

    def __repr__(self) -> str:
        return f"<Analysis Thk_ID={self.Thk_ID} NID={self.NID}>"
