"""
模型管理服务层
model_key 使用 Fernet 对称加密存储，任何接口均不返回原始 key
注意：当前 model_providers 表无 UID 列，模型为全局共享
"""

import os
import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.models.model_provider import ModelProvider


def _get_fernet() -> Fernet:
    raw = os.getenv("MODEL_KEY_SECRET", "")
    if raw:
        key = raw.encode()
    else:
        secret = os.getenv("JWT_SECRET_KEY", "fallback_secret_change_in_production")
        padded = (secret * 4)[:32].encode()
        key = base64.urlsafe_b64encode(padded)
    return Fernet(key)


def _encrypt(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("model_key 解密失败，密钥可能已更换")


def get_models(db: Session, user_id: int = 0) -> list[ModelProvider]:
    return db.query(ModelProvider).all()


def get_model(db: Session, user_id: int, model_id: int) -> Optional[ModelProvider]:
    return db.query(ModelProvider).filter(ModelProvider.id == model_id).first()


def create_model(db: Session, user_id: int, model_name: str, model_key: str, base_url: str) -> ModelProvider:
    model = ModelProvider(
        model_name=model_name,
        model_key_encrypted=_encrypt(model_key),
        base_url=base_url,
        is_active=False,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def update_model(
    db: Session,
    user_id: int,
    model_id: int,
    model_name: Optional[str] = None,
    model_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[ModelProvider]:
    model = get_model(db, user_id, model_id)
    if model is None:
        return None

    if model_name is not None:
        model.model_name = model_name
    if model_key is not None:
        model.model_key_encrypted = _encrypt(model_key)
    if base_url is not None:
        model.base_url = base_url

    db.commit()
    db.refresh(model)
    return model


def delete_model(db: Session, user_id: int, model_id: int) -> bool:
    model = get_model(db, user_id, model_id)
    if model is None:
        return False
    db.delete(model)
    db.commit()
    return True
