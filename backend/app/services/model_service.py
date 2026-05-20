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


def validate_model_connection(base_url: str, model_key: str, model_name: str = "") -> Optional[str]:
    """
    验证 LLM API 连通性。注册前调用，失败时返回具体错误原因。

    :param base_url: API 地址（如 https://api.deepseek.com）
    :param model_key: API Key
    :param model_name: 模型名称（用于测试调用）
    :return: None 表示验证通过，否则返回错误描述字符串
    """
    import httpx

    # 1. 基本格式校验
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        return "Base URL 格式错误：必须以 http:// 或 https:// 开头"

    if "/api_keys" in base_url or "/dashboard" in base_url or "/platform" in base_url:
        return "Base URL 错误：请填写 API 接口地址（如 https://api.deepseek.com），而非管理后台网页地址"

    # 2. 尝试调用 /v1/models 端点验证连通性和 API Key
    test_url = base_url.rstrip("/") + "/v1/models"
    headers = {"Authorization": f"Bearer {model_key}"}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(test_url, headers=headers)

        if resp.status_code == 200:
            return None  # 验证通过

        if resp.status_code == 401:
            return "API Key 无效：认证失败（401），请检查 Key 是否正确、是否已过期"

        if resp.status_code == 403:
            return "API Key 权限不足（403），请检查 Key 的权限设置"

        if resp.status_code == 404:
            # /v1/models 不存在，可能是非标准接口，尝试 /v1/chat/completions
            return None  # 放行，部分服务不支持 /v1/models 但能正常使用

        # 其他错误码
        body = resp.text[:200]
        return f"API 返回异常状态码 {resp.status_code}：{body}"

    except httpx.ConnectError:
        return f"无法连接到 {base_url}：请检查 URL 是否正确，网络是否可达"

    except httpx.TimeoutException:
        return f"连接超时：{base_url} 在 10 秒内无响应，请检查 URL 是否正确"

    except Exception as e:
        return f"连接验证失败：{type(e).__name__}: {str(e)}"


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


def activate_model(db: Session, user_id: int, model_id: int) -> Optional[ModelProvider]:
    """
    激活指定模型，同时停用其他所有模型（单活模式）。
    """
    model = get_model(db, user_id, model_id)
    if model is None:
        return None

    # 先停用所有模型
    db.query(ModelProvider).update({ModelProvider.is_active: False})
    # 激活目标模型
    model.is_active = True
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
