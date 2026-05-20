"""
用户反馈模型 — 用于强化学习反馈闭环
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column("id", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("user_id", Integer, ForeignKey("users.UID"), nullable=False, index=True)
    diary_nid: Mapped[int] = mapped_column("diary_nid", Integer, ForeignKey("diary_entries.NID"), nullable=False)
    response_style: Mapped[str] = mapped_column("response_style", String(32), nullable=False)
    feedback_type: Mapped[str] = mapped_column("feedback_type", String(16), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column("reason", String(64), nullable=True)
    source: Mapped[str] = mapped_column("source", String(16), nullable=False)
    signal_type: Mapped[Optional[str]] = mapped_column("signal_type", String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} user_id={self.user_id} type={self.feedback_type}>"
