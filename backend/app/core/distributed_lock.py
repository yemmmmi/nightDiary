"""
Redis 分布式锁模块
基于 Redis SET NX EX 实现分布式锁，使用 Lua 脚本原子释放
用于缓存击穿防护，防止多个请求同时回源数据库
"""

import uuid
import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Lua 脚本：原子检查并释放锁
# 仅当锁的值与传入值匹配时才删除，防止误释放其他客户端的锁
_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class RedisDistributedLock:
    """基于 Redis SET NX EX 的分布式锁"""

    @staticmethod
    async def acquire(
        redis_client: aioredis.Redis,
        key: str,
        timeout: int = 5,
    ) -> Optional[str]:
        """
        尝试获取分布式锁。

        使用 SET key uuid_value NX EX timeout 原子操作：
        - NX：仅当 key 不存在时设置（互斥）
        - EX：设置过期时间，防止死锁

        Args:
            redis_client: Redis 异步客户端实例
            key: 锁的 Redis Key
            timeout: 锁的过期时间（秒），默认 5 秒

        Returns:
            成功时返回 UUID lock_value，失败时返回 None
        """
        lock_value = str(uuid.uuid4())
        try:
            acquired = await redis_client.set(
                key, lock_value, nx=True, ex=timeout
            )
            if acquired:
                logger.debug("分布式锁获取成功: key=%s, value=%s, timeout=%ds", key, lock_value, timeout)
                return lock_value
            else:
                logger.debug("分布式锁获取失败（已被占用）: key=%s", key)
                return None
        except Exception as e:
            logger.error("分布式锁获取异常: key=%s, error=%s", key, e)
            return None

    @staticmethod
    async def release(
        redis_client: aioredis.Redis,
        key: str,
        lock_value: str,
    ) -> bool:
        """
        原子释放分布式锁。

        使用 Lua 脚本确保仅当锁的值与传入值匹配时才删除，
        防止误释放其他客户端持有的锁。

        Args:
            redis_client: Redis 异步客户端实例
            key: 锁的 Redis Key
            lock_value: 获取锁时返回的 UUID 值

        Returns:
            释放成功返回 True，失败返回 False
        """
        try:
            result = await redis_client.eval(
                _RELEASE_LOCK_SCRIPT, 1, key, lock_value
            )
            if result:
                logger.debug("分布式锁释放成功: key=%s", key)
                return True
            else:
                logger.warning("分布式锁释放失败（值不匹配或已过期）: key=%s", key)
                return False
        except Exception as e:
            logger.error("分布式锁释放异常: key=%s, error=%s", key, e)
            return False
