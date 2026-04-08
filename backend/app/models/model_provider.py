"""
LLM 模型提供商配置模型 — 对齐 MySQL model_providers 表
"""

from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.user import User


class ModelProvider(Base):
    __tablename__ = "model_providers"

    Mod_ID: Mapped[int] = mapped_column("Mod_ID", Integer, primary_key=True, autoincrement=True)
    is_active: Mapped[Optional[bool]] = mapped_column("is_active", Boolean, default=True, nullable=True)
    Model_name: Mapped[str] = mapped_column("Model_name", String(100), nullable=False)
    Model_Key: Mapped[Optional[str]] = mapped_column("Model_Key", String(255), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column("base_url", String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<ModelProvider Mod_ID={self.Mod_ID} Model_name={self.Model_name!r}>"
