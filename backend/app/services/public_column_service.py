"""
公开日记专栏服务层
封装公开专栏的业务逻辑和 Redis 缓存策略：
- Cache-Aside 旁路缓存
- 缓存穿透防护（空值缓存）
- 缓存击穿防护（分布式锁）
- 缓存雪崩防护（随机 TTL 偏移）
- Redis 不可用时优雅降级
"""

import json
import random
import asyncio
import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

import redis.asyncio as aioredis

from app.models.diary import DiaryEntry
from app.models.user import User
from app.core.distributed_lock import RedisDistributedLock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部辅助：序列化 / 反序列化
# ---------------------------------------------------------------------------

def _serialize_list_item(entry: DiaryEntry, author_name: str) -> dict:
    """将 DiaryEntry 转换为列表项字典（摘要 ≤ 200 字符）"""
    content = entry.content or ""
    return {
        "NID": entry.NID,
        "author_name": author_name,
        "content_summary": content[:200],
        "publish_time": entry.publish_time.isoformat() if entry.publish_time else None,
        "tags": [
            {
                "id": tag.id,
                "tag_name": tag.tag_name,
                "color": tag.color,
                "creator": tag.creator,
                "usage_count": tag.usage_count,
                "create_time": tag.create_time.isoformat() if tag.create_time else None,
            }
            for tag in (entry.tags or [])
        ],
    }


def _serialize_detail(entry: DiaryEntry, author_name: str) -> dict:
    """将 DiaryEntry 转换为详情字典"""
    return {
        "NID": entry.NID,
        "author_name": author_name,
        "content": entry.content or "",
        "date": entry.date.isoformat() if entry.date else None,
        "weather": entry.weather,
        "publish_time": entry.publish_time.isoformat() if entry.publish_time else None,
        "tags": [
            {
                "id": tag.id,
                "tag_name": tag.tag_name,
                "color": tag.color,
                "creator": tag.creator,
                "usage_count": tag.usage_count,
                "create_time": tag.create_time.isoformat() if tag.create_time else None,
            }
            for tag in (entry.tags or [])
        ],
    }


# ---------------------------------------------------------------------------
# 5.6 缓存失效方法
# ---------------------------------------------------------------------------

async def invalidate_diary_cache(
    redis_client: Optional[aioredis.Redis],
    nid: int,
) -> None:
    """
    删除指定日记的详情缓存。
    失败时仅记录日志，不抛出异常，依赖 TTL 过期保证最终一致性。
    """
    if redis_client is None:
        return
    try:
        await redis_client.delete(f"column:detail:{nid}")
        logger.debug("已删除详情缓存: column:detail:%s", nid)
    except Exception as e:
        logger.warning("删除详情缓存失败: nid=%s, error=%s", nid, e)


async def invalidate_list_cache(
    redis_client: Optional[aioredis.Redis],
) -> None:
    """
    使用 SCAN 扫描并删除所有列表缓存 key（column:list:*）。
    失败时仅记录日志，不抛出异常。
    """
    if redis_client is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor, match="column:list:*", count=100
            )
            if keys:
                await redis_client.delete(*keys)
            if cursor == 0:
                break
        logger.debug("已删除所有列表缓存 column:list:*")
    except Exception as e:
        logger.warning("删除列表缓存失败: error=%s", e)


# ---------------------------------------------------------------------------
# 5.2 发布日记到公开专栏
# ---------------------------------------------------------------------------

async def publish_diary(
    db: Session,
    redis_client: Optional[aioredis.Redis],
    user_id: int,
    nid: int,
) -> dict:
    """
    将日记发布到公开专栏。

    验证流程：
    1. 日记存在且属于当前用户
    2. 日记 is_open 为 True
    3. 日记尚未发布到专栏

    成功后删除列表缓存和该 NID 的空值缓存。
    """
    # 查询日记
    entry = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()

    # 验证日记存在且属于当前用户
    if entry is None or entry.UID != user_id:
        raise ValueError("日记不存在或无权访问")

    # 验证日记为公开状态
    if not entry.is_open:
        raise ValueError("仅公开日记可发布到专栏")

    # 验证未重复发布
    if entry.published_to_column:
        raise ValueError("该日记已在专栏中")

    # 更新发布状态
    entry.published_to_column = True
    entry.publish_time = datetime.utcnow()
    db.commit()

    # 删除列表缓存和空值缓存（Redis 降级：不可用时跳过）
    if redis_client is not None:
        try:
            await invalidate_list_cache(redis_client)
            await redis_client.delete(f"column:null:{nid}")
        except Exception as e:
            logger.warning("发布后清除缓存失败: nid=%s, error=%s", nid, e)

    return {"message": "发布成功", "nid": nid}


# ---------------------------------------------------------------------------
# 5.3 从公开专栏下架日记
# ---------------------------------------------------------------------------

async def unpublish_diary(
    db: Session,
    redis_client: Optional[aioredis.Redis],
    user_id: int,
    nid: int,
) -> dict:
    """
    将日记从公开专栏下架。

    验证流程：
    1. 日记存在且属于当前用户
    2. 日记已发布到专栏
    """
    # 查询日记
    entry = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()

    # 验证日记存在且属于当前用户
    if entry is None or entry.UID != user_id:
        raise ValueError("日记不存在或无权访问")

    # 验证已在专栏中
    if not entry.published_to_column:
        raise ValueError("该日记不在专栏中")

    # 更新状态
    entry.published_to_column = False
    entry.publish_time = None
    db.commit()

    # 删除详情缓存和列表缓存（Redis 降级：不可用时跳过）
    if redis_client is not None:
        try:
            await invalidate_diary_cache(redis_client, nid)
            await invalidate_list_cache(redis_client)
        except Exception as e:
            logger.warning("下架后清除缓存失败: nid=%s, error=%s", nid, e)

    return {"message": "下架成功", "nid": nid}


# ---------------------------------------------------------------------------
# 5.4 获取公开日记列表（Cache-Aside + 雪崩防护）
# ---------------------------------------------------------------------------

async def get_public_entries(
    db: Session,
    redis_client: Optional[aioredis.Redis],
    skip: int = 0,
    limit: int = 20,
) -> List[dict]:
    """
    获取公开专栏日记列表，支持分页。

    缓存策略：
    - Cache-Aside：先查 Redis，命中则直接返回
    - 未命中：查 DB，结果写入 Redis
    - TTL = 300 + random(0, 120)，防止缓存雪崩
    - Redis 不可用时降级为直接查 DB
    """
    cache_key = f"column:list:{skip}:{limit}"

    # 尝试读取缓存
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                logger.debug("列表缓存命中: %s", cache_key)
                return json.loads(cached)
        except Exception as e:
            logger.warning("读取列表缓存失败，降级查 DB: error=%s", e)

    # 缓存未命中或 Redis 不可用，查询数据库
    entries = (
        db.query(DiaryEntry)
        .options(joinedload(DiaryEntry.user), joinedload(DiaryEntry.tags))
        .filter(DiaryEntry.published_to_column == True)
        .order_by(desc(DiaryEntry.publish_time))
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 构建列表数据
    result = []
    for entry in entries:
        author_name = entry.user.user_name if entry.user else "未知用户"
        result.append(_serialize_list_item(entry, author_name))

    # 回填缓存（Redis 降级：不可用时跳过）
    if redis_client is not None:
        try:
            ttl = 300 + random.randint(0, 120)
            await redis_client.set(cache_key, json.dumps(result, ensure_ascii=False), ex=ttl)
            logger.debug("列表缓存已写入: %s, ttl=%ds", cache_key, ttl)
        except Exception as e:
            logger.warning("写入列表缓存失败: error=%s", e)

    return result


# ---------------------------------------------------------------------------
# 5.5 获取公开日记详情（Cache-Aside + 穿透防护 + 击穿防护）
# ---------------------------------------------------------------------------

async def get_public_entry_detail(
    db: Session,
    redis_client: Optional[aioredis.Redis],
    nid: int,
) -> Optional[dict]:
    """
    获取公开日记详情。

    缓存策略：
    1. 查 Redis 详情缓存，命中则返回
    2. 查 Redis 空值标记（穿透防护），命中则返回 None
    3. 尝试获取分布式锁（击穿防护）
       - 获取成功：查 DB → 回填缓存或写空值标记 → 释放锁
       - 获取失败：等待 200ms 后重试读缓存，仍未命中返回 None
    4. TTL = 600 + random(0, 60)，防止缓存雪崩
    5. Redis 不可用时降级为直接查 DB
    """
    cache_key = f"column:detail:{nid}"
    null_key = f"column:null:{nid}"
    lock_key = f"column:lock:detail:{nid}"

    # ---------- Redis 可用时走缓存逻辑 ----------
    if redis_client is not None:
        try:
            # 1. 查详情缓存
            cached = await redis_client.get(cache_key)
            if cached is not None:
                logger.debug("详情缓存命中: %s", cache_key)
                return json.loads(cached)

            # 2. 查空值标记（穿透防护）
            null_flag = await redis_client.get(null_key)
            if null_flag is not None:
                logger.debug("空值缓存命中: %s", null_key)
                return None

            # 3. 尝试获取分布式锁（击穿防护）
            lock_value = await RedisDistributedLock.acquire(
                redis_client, lock_key, timeout=5
            )

            if lock_value is not None:
                # 获取锁成功：查 DB 并回填缓存
                try:
                    data = _query_detail_from_db(db, nid)
                    if data is not None:
                        ttl = 600 + random.randint(0, 60)
                        await redis_client.set(
                            cache_key,
                            json.dumps(data, ensure_ascii=False),
                            ex=ttl,
                        )
                        logger.debug("详情缓存已写入: %s, ttl=%ds", cache_key, ttl)
                    else:
                        # 写空值标记（穿透防护）
                        await redis_client.set(null_key, "NULL", ex=60)
                        logger.debug("空值缓存已写入: %s", null_key)
                    return data
                finally:
                    await RedisDistributedLock.release(
                        redis_client, lock_key, lock_value
                    )
            else:
                # 获取锁失败：等待后重试读缓存
                await asyncio.sleep(0.2)
                cached = await redis_client.get(cache_key)
                if cached is not None:
                    return json.loads(cached)
                return None

        except Exception as e:
            logger.warning("详情缓存操作失败，降级查 DB: nid=%s, error=%s", nid, e)

    # ---------- Redis 不可用时直接查 DB ----------
    return _query_detail_from_db(db, nid)


def _query_detail_from_db(db: Session, nid: int) -> Optional[dict]:
    """从数据库查询已发布的公开日记详情"""
    entry = (
        db.query(DiaryEntry)
        .options(joinedload(DiaryEntry.user), joinedload(DiaryEntry.tags))
        .filter(DiaryEntry.NID == nid, DiaryEntry.published_to_column == True)
        .first()
    )
    if entry is None:
        return None
    author_name = entry.user.user_name if entry.user else "未知用户"
    return _serialize_detail(entry, author_name)
