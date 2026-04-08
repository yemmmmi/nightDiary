"""
标签服务层
封装标签的增删改查业务逻辑
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.tag import Tag


def get_tags(db: Session, sort_by_usage: bool = True) -> list[Tag]:
    """
    获取所有标签列表

    :param db: 数据库会话
    :param sort_by_usage: True 时按引用次数倒序，False 时按创建时间倒序
    :return: Tag 列表
    """
    order = desc(Tag.usage_count) if sort_by_usage else desc(Tag.create_time)
    return db.query(Tag).order_by(order).all()


def get_tag(db: Session, tag_id: int) -> Optional[Tag]:
    """按 ID 查询单个标签"""
    return db.query(Tag).filter(Tag.id == tag_id).first()


def create_tag(db: Session, tag_name: str, color: str, creator: str) -> Tag:
    """
    创建标签，校验名称唯一性

    :param db: 数据库会话
    :param tag_name: 标签名（已通过 schema 校验长度）
    :param color: 颜色值
    :param creator: 创建者用户名
    :return: 新创建的 Tag 对象
    :raises ValueError: 标签名已存在
    """
    existing = db.query(Tag).filter(Tag.tag_name == tag_name).first()
    if existing:
        raise ValueError("标签名已存在")

    tag = Tag(tag_name=tag_name, color=color, creator=creator)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def update_tag(
    db: Session,
    tag_id: int,
    tag_name: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[Tag]:
    """
    修改标签属性

    :param db: 数据库会话
    :param tag_id: 标签 ID
    :param tag_name: 新标签名（可选）
    :param color: 新颜色（可选）
    :return: 更新后的 Tag，若不存在返回 None
    :raises ValueError: 新标签名已被其他标签使用
    """
    tag = get_tag(db, tag_id)
    if tag is None:
        return None

    if tag_name is not None:
        conflict = db.query(Tag).filter(Tag.tag_name == tag_name, Tag.id != tag_id).first()
        if conflict:
            raise ValueError("标签名已存在")
        tag.tag_name = tag_name

    if color is not None:
        tag.color = color

    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int) -> bool:
    """
    删除标签

    :param db: 数据库会话
    :param tag_id: 标签 ID
    :return: True 表示删除成功，False 表示标签不存在
    """
    tag = get_tag(db, tag_id)
    if tag is None:
        return False
    db.delete(tag)
    db.commit()
    return True
