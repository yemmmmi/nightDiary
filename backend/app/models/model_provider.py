"""
LLM 模型提供商配置模型 — 对齐 MySQL model_providers 表
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ModelProvider(Base):
    __tablename__ = "model_providers"

    id: Mapped[int] = mapped_column("Mod_ID", Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[Optional[int]] = mapped_column("UID", Integer, ForeignKey("users.UID"), nullable=True, index=True)

    model_name: Mapped[str] = mapped_column("Model_name", String(100), nullable=False, default="未命名")

    model_key_encrypted: Mapped[Optional[str]] = mapped_column("Model_Key", String(512), nullable=True)

    base_url: Mapped[Optional[str]] = mapped_column("base_url", String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column("is_active", Boolean, default=False, nullable=False)
    
    create_time: Mapped[Optional[datetime]] = mapped_column("create_time", DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ModelProvider id={self.id} model_name={self.model_name!r}>"
