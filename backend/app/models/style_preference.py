"""
风格偏好模型 — Thompson Sampling Beta 分布参数
"""

from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class StylePreference(Base):
    __tablename__ = "style_preferences"

    id: Mapped[int] = mapped_column("id", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("user_id", Integer, ForeignKey("users.UID"), nullable=False, index=True)
    style: Mapped[str] = mapped_column("style", String(32), nullable=False)
    alpha: Mapped[float] = mapped_column("alpha", Float, default=1.0, nullable=False)
    beta: Mapped[float] = mapped_column("beta", Float, default=1.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<StylePreference id={self.id} user_id={self.user_id} style={self.style}>"
