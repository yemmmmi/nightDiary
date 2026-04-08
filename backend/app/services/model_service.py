"""
模型管理服务层
model_key 使用 Fernet 对称加密存储，任何接口均不返回原始 key
"""

import os
import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.models.model_provider import ModelProvider


def _get_fernet() -> Fernet:
    """
    从环境变量 MODEL_KEY_SECRET 获取 Fernet 密钥。
    若未配置则使用固定 fallback(仅开发环境, 生产必须设置)。
    """
    raw = os.getenv("MODEL_KEY_SECRET", "")
    if raw:
        # 支持直接传入 base64url 编码的 32 字节密钥
        key = raw.encode()
    else:
        # fallback：从 JWT_SECRET_KEY 派生，保证长度为 32 字节
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


# ── CRUD ─────────────────────────────────────────

def get_models(db: Session, user_id: int) -> list[ModelProvider]:
    """获取当前用户的所有模型"""
    return db.query(ModelProvider).filter(ModelProvider.user_id == user_id).all()


def get_model(db: Session, user_id: int, model_id: int) -> Optional[ModelProvider]:
    """查询单个模型，同时验证归属"""
    return (
        db.query(ModelProvider)
        .filter(ModelProvider.id == model_id, ModelProvider.user_id == user_id)
        .first()
    )


def create_model(db: Session, user_id: int, model_name: str, model_key: str, base_url: str) -> ModelProvider:
    """
    注册新模型，model_key 加密后存储

    :raises ValueError: model_key 或 base_url 为空
    """
    model = ModelProvider(
        user_id=user_id,
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
    """
    修改模型信息, model_key 若提供则重新加密存储

    :return: 更新后的 ModelProvider, 不存在或不属于该用户返回 None
    """
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
    """
    删除模型

    :return: True 删除成功, False 不存在或不属于该用户
    """
    model = get_model(db, user_id, model_id)
    if model is None:
        return False
    db.delete(model)
    db.commit()
    return True


def get_decrypted_key(db: Session, user_id: int, model_id: int) -> Optional[str]:
    """
    供 AI 服务内部使用：获取解密后的 model_key
    不对外暴露为 API 接口
    """
    model = get_model(db, user_id, model_id)
    if model is None or not model.model_key_encrypted:
        return None
    return _decrypt(model.model_key_encrypted)
