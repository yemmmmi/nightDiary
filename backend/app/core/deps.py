"""
FastAPI 依赖注入模块
提供 get_current_user 依赖，用于受保护路由的身份验证
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# HTTPBearer 会自动从请求头 Authorization: Bearer <token> 中提取 token
# auto_error=False 表示未提供 token 时不自动报错，由我们手动处理
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI 依赖函数：从 Authorization Bearer header 提取并验证 JWT token
    解码 token 后查询数据库，返回对应的 User 对象
    token 未提供、无效、过期，或用户不存在时均抛出 HTTPException 401
    """
    # 未提供 Authorization header 或格式不正确
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 解码 token（内部会在无效/过期时抛出 401）
    payload = decode_access_token(credentials.credentials)

    # 从 payload 中提取用户 ID（存储为字符串）
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭据无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 查询数据库确认用户存在
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭据无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.UID == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭据无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
