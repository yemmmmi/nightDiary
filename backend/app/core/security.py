"""
安全工具模块
提供密码哈希/验证和 JWT token 生成/解码功能
直接使用 bcrypt 库，避免 passlib 与新版 bcrypt 的兼容问题
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希，返回哈希字符串"""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    """
    生成 JWT access token
    过期时间从环境变量 JWT_EXPIRE_MINUTES 读取，默认 1440 分钟（24 小时）
    """
    secret_key = os.getenv("JWT_SECRET_KEY", "fallback_secret_change_in_production")
    expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """
    解码并验证 JWT token
    token 过期或签名无效时抛出 HTTPException 401
    """
    secret_key = os.getenv("JWT_SECRET_KEY", "fallback_secret_change_in_production")

    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭据无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
