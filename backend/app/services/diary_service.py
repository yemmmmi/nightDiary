"""
日记服务层
封装日记条目的增删改查业务逻辑，所有操作均验证用户归属。
日记的增删改操作会同步更新 Chroma 向量库，保持 MySQL 和向量库的数据一致性。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.diary import DiaryEntry
from app.models.tag import Tag
from app.services import vector_service

logger = logging.getLogger(__name__)


def create_entry(
    db: Session,
    uid: int,
    content: str,
    is_open: bool = False,
    weather: Optional[str] = None,
) -> DiaryEntry:
    if not content or not content.strip():
        raise ValueError("日记内容不能为空")

    entry = DiaryEntry(
        UID=uid,
        content=content,
        is_open=is_open,
        weather=weather,
        date=datetime.utcnow().date(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # 同步写入 Chroma
    try:
        date_str = entry.create_time.strftime("%Y-%m-%d") if entry.create_time else ""
        vector_service.add_diary(user_id=uid, nid=entry.NID, content=content, date_str=date_str)
    except Exception as exc:
        logger.warning("Chroma 同步写入失败: %s", exc)

    return entry


def get_entries(
    db: Session,
    uid: int,
    skip: int = 0,
    limit: int = 20,
) -> list[DiaryEntry]:
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.UID == uid)
        .order_by(desc(DiaryEntry.create_time))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_entry(db: Session, uid: int, nid: int) -> Optional[DiaryEntry]:
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.NID == nid, DiaryEntry.UID == uid)
        .first()
    )


def update_entry(
    db: Session,
    uid: int,
    nid: int,
    content: Optional[str] = None,
    is_open: Optional[bool] = None,
    tag_ids: Optional[List[int]] = None,
) -> Optional[DiaryEntry]:
    entry = get_entry(db, uid, nid)
    if entry is None:
        return None

    if content is not None:
        if not content or not content.strip():
            raise ValueError("日记内容不能为空")
        entry.content = content

    if is_open is not None:
        entry.is_open = is_open

    if tag_ids is not None:
        old_tags = set(entry.tags)
        new_tags_list = db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        new_tags = set(new_tags_list)

        for tag in (old_tags - new_tags):
            tag.usage_count = max(0, tag.usage_count - 1)
        for tag in (new_tags - old_tags):
            tag.usage_count = tag.usage_count + 1

        entry.tags = new_tags_list

    db.commit()
    db.refresh(entry)

    if content is not None:
        try:
            date_str = entry.create_time.strftime("%Y-%m-%d") if entry.create_time else ""
            tags_str = "、".join(f"#{t.tag_name}" for t in (entry.tags or []) if t.tag_name)
            vector_service.update_diary(user_id=uid, nid=nid, content=entry.content or "", date_str=date_str, tags_str=tags_str)
        except Exception as exc:
            logger.warning("Chroma 同步更新失败: %s", exc)

    return entry


def delete_entry(db: Session, uid: int, nid: int) -> bool:
    entry = get_entry(db, uid, nid)
    if entry is None:
        return False

    db.delete(entry)
    db.commit()

    try:
        vector_service.delete_diary(user_id=uid, nid=nid)
    except Exception as exc:
        logger.warning("Chroma 同步删除失败: %s", exc)

    return True


def get_recent_7days(db: Session, uid: int) -> list[DiaryEntry]:
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.UID == uid, DiaryEntry.create_time >= seven_days_ago)
        .order_by(desc(DiaryEntry.create_time))
        .all()
    )
