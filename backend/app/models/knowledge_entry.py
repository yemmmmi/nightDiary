"""
结构化知识条目模型 — 从日记中抽取的实体知识
"""

from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column("id", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("user_id", Integer, ForeignKey("users.UID"), nullable=False, index=True)
    diary_nid: Mapped[int] = mapped_column("diary_nid", Integer, ForeignKey("diary_entries.NID"), nullable=False)
    entity_type: Mapped[str] = mapped_column("entity_type", String(32), nullable=False)
    entity_data: Mapped[str] = mapped_column("entity_data", Text, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column("extracted_at", DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<KnowledgeEntry id={self.id} user_id={self.user_id} type={self.entity_type}>"
