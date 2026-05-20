"""
情景记忆模块 - EpisodicMemory
==============================

基于 Redis Sorted Set 实现的情景记忆存储。
- Key pattern: "memory:episodic:{user_id}"
- Score: Unix timestamp
- Member: JSON string of EpisodicEntry

功能：
- store(): 重要性 > 0.5 时持久化到 Redis
- retrieve_relevant(): 按 importance * 时间衰减因子排序，返回 top 5
- evict_lowest(): 条目数 > 100 时驱逐重要性最低的条目

Redis 不可用时优雅降级：跳过记忆操作，不影响核心分析。
"""

import json
import time
import logging
from typing import List, Optional

import redis.asyncio as aioredis

from app.schemas.memory import EpisodicEntry
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """情景记忆，基于 Redis Sorted Set"""

    KEY_PATTERN = "memory:episodic:{user_id}"
    MAX_ENTRIES = 100
    IMPORTANCE_THRESHOLD = 0.5
    # 时间衰减半衰期（秒），7 天
    DECAY_HALF_LIFE = 7 * 24 * 3600

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        """
        初始化 EpisodicMemory。

        Args:
            redis_client: Redis 客户端实例，若为 None 则通过 get_redis() 获取。
        """
        self._redis = redis_client

    @property
    def redis(self) -> Optional[aioredis.Redis]:
        """获取 Redis 客户端，支持延迟初始化。"""
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def _key(self, user_id: int) -> str:
        """生成 Redis key。"""
        return self.KEY_PATTERN.format(user_id=user_id)

    def _compute_decay(self, timestamp: float, now: Optional[float] = None) -> float:
        """
        计算时间衰减因子。

        使用指数衰减: decay = 0.5 ^ (elapsed / half_life)
        衰减因子范围 (0, 1]，越近的记忆衰减越小。
        """
        if now is None:
            now = time.time()
        elapsed = max(0.0, now - timestamp)
        return 0.5 ** (elapsed / self.DECAY_HALF_LIFE)

    async def store(self, user_id: int, entry: EpisodicEntry) -> bool:
        """
        存储情景记忆条目。

        仅当 importance > 0.5 时才持久化到 Redis。
        存储后检查条目总数，超出 MAX_ENTRIES 时自动驱逐。

        Args:
            user_id: 用户 ID
            entry: 情景记忆条目

        Returns:
            True 表示成功存储，False 表示跳过（重要性不足或 Redis 不可用）
        """
        if entry.importance <= self.IMPORTANCE_THRESHOLD:
            logger.debug(
                "跳过存储：importance=%.2f <= %.2f (user_id=%d)",
                entry.importance, self.IMPORTANCE_THRESHOLD, user_id
            )
            return False

        client = self.redis
        if client is None:
            logger.warning("Redis 不可用，跳过情景记忆存储 (user_id=%d)", user_id)
            return False

        try:
            key = self._key(user_id)
            member = entry.model_dump_json()
            # score 为 Unix timestamp
            await client.zadd(key, {member: entry.timestamp})
            logger.debug("情景记忆已存储 (user_id=%d, importance=%.2f)", user_id, entry.importance)

            # 检查是否需要驱逐
            await self.evict_lowest(user_id)
            return True
        except Exception as e:
            logger.error("情景记忆存储失败 (user_id=%d): %s", user_id, e)
            return False

    async def retrieve_relevant(
        self,
        user_id: int,
        query: str = "",
        top_k: int = 5,
        now: Optional[float] = None,
    ) -> List[EpisodicEntry]:
        """
        检索相关的情景记忆。

        按 importance * 时间衰减因子 综合排序，返回得分最高的 top_k 条目。

        Args:
            user_id: 用户 ID
            query: 查询文本（当前版本不做语义匹配，预留接口）
            top_k: 返回条目数
            now: 当前时间戳（用于计算衰减，默认为 time.time()）

        Returns:
            排序后的 EpisodicEntry 列表（最多 top_k 条）
        """
        client = self.redis
        if client is None:
            logger.warning("Redis 不可用，跳过情景记忆检索 (user_id=%d)", user_id)
            return []

        try:
            key = self._key(user_id)
            # 获取所有条目（member + score）
            members = await client.zrangebyscore(key, "-inf", "+inf")
            if not members:
                return []

            if now is None:
                now = time.time()

            # 解析并计算综合得分
            scored_entries: List[tuple] = []
            for member_json in members:
                try:
                    entry = EpisodicEntry.model_validate_json(member_json)
                    decay = self._compute_decay(entry.timestamp, now)
                    score = entry.importance * decay
                    scored_entries.append((score, entry))
                except Exception as e:
                    logger.warning("解析情景记忆条目失败: %s", e)
                    continue

            # 按综合得分降序排序，取 top_k
            scored_entries.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored_entries[:top_k]]
        except Exception as e:
            logger.error("情景记忆检索失败 (user_id=%d): %s", user_id, e)
            return []

    async def evict_lowest(self, user_id: int) -> int:
        """
        驱逐重要性最低的条目。

        当条目数超过 MAX_ENTRIES 时，移除重要性最低的条目直到数量等于 MAX_ENTRIES。

        Args:
            user_id: 用户 ID

        Returns:
            驱逐的条目数
        """
        client = self.redis
        if client is None:
            return 0

        try:
            key = self._key(user_id)
            count = await client.zcard(key)

            if count <= self.MAX_ENTRIES:
                return 0

            # 获取所有条目，按重要性排序找出最低的
            members = await client.zrangebyscore(key, "-inf", "+inf")
            if not members:
                return 0

            # 解析所有条目，按 importance 升序排序
            entries_with_json: List[tuple] = []
            for member_json in members:
                try:
                    entry = EpisodicEntry.model_validate_json(member_json)
                    entries_with_json.append((entry.importance, member_json))
                except Exception:
                    # 无法解析的条目视为最低重要性
                    entries_with_json.append((0.0, member_json))

            entries_with_json.sort(key=lambda x: x[0])

            # 计算需要驱逐的数量
            to_evict = count - self.MAX_ENTRIES
            evicted = 0

            for i in range(to_evict):
                _, member_json = entries_with_json[i]
                await client.zrem(key, member_json)
                evicted += 1

            if evicted > 0:
                logger.info(
                    "情景记忆驱逐完成 (user_id=%d): 驱逐 %d 条，剩余 %d 条",
                    user_id, evicted, count - evicted
                )
            return evicted
        except Exception as e:
            logger.error("情景记忆驱逐失败 (user_id=%d): %s", user_id, e)
            return 0
