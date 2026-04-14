"""
LLM 模型提供商配置模型 — 对齐 MySQL model_providers 表
实际表结构: Mod_ID, is_active, Model_name, Model_Key, base_url
"""

from typing import Optional
from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ModelProvider(Base):
    __tablename__ = "model_providers"

    id: Mapped[int] = mapped_column("Mod_ID", Integer, primary_key=True, autoincrement=True)

    model_name: Mapped[str] = mapped_column("Model_name", String(100), nullable=False, default="未命名")

    model_key_encrypted: Mapped[Optional[str]] = mapped_column("Model_Key", String(255), nullable=True)

    base_url: Mapped[Optional[str]] = mapped_column("base_url", String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column("is_active", Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<ModelProvider id={self.id} model_name={self.model_name!r}>"
