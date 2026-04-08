"""
日记服务层
封装日记条目的增删查业务逻辑，所有操作均验证用户归属
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.diary import DiaryEntry


def create_entry(
    db: Session,
    user_id: int,
    content: str,
    mood: Optional[str] = None,
    is_public: bool = False,
    weather: Optional[str] = None,
) -> DiaryEntry:
    """
    创建日记条目

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param content: 日记正文，不能为空或纯空白
    :param mood: 心情，可为空
    :param is_public: 是否公开，默认 False
    :param weather: 天气，由路由层自动抓取后传入
    :return: 新创建的 DiaryEntry 对象
    :raises ValueError: 当 content 为空或纯空白时
    """
    if not content or not content.strip():
        raise ValueError("日记内容不能为空")

    entry = DiaryEntry(
        user_id=user_id,
        content=content,
        mood=mood,
        is_public=is_public,
        weather=weather,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entries(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20,
) -> list[DiaryEntry]:
    """
    查询当前用户的日记列表，按创建时间倒序排列

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param skip: 跳过条数（分页偏移）
    :param limit: 返回条数上限，默认 20
    :return: DiaryEntry 列表
    """
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user_id)
        .order_by(desc(DiaryEntry.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_entry(
    db: Session,
    user_id: int,
    entry_id: int,
) -> Optional[DiaryEntry]:
    """
    查询单篇日记，同时验证归属（user_id 必须匹配）

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param entry_id: 日记 ID
    :return: DiaryEntry 对象，若不存在或不属于该用户则返回 None
    """
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.id == entry_id, DiaryEntry.user_id == user_id)
        .first()
    )


def delete_entry(
    db: Session,
    user_id: int,
    entry_id: int,
) -> bool:
    """
    删除日记条目，验证归属后执行删除

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param entry_id: 日记 ID
    :return: True 表示删除成功，False 表示条目不存在或不属于该用户
    """
    entry = get_entry(db, user_id, entry_id)
    if entry is None:
        return False

    db.delete(entry)
    db.commit()
    return True


def get_recent_7days(
    db: Session,
    user_id: int,
) -> list[DiaryEntry]:
    """
    查询当前用户最近 7 天内的日记，供 AI 分析使用

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :return: 最近 7 天内的 DiaryEntry 列表，按创建时间倒序
    """
    # 计算 7 天前的时间边界
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    return (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == user_id,
            DiaryEntry.created_at >= seven_days_ago,
        )
        .order_by(desc(DiaryEntry.created_at))
        .all()
    )
