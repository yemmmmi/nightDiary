"""
EpisodicMemory 单元测试
========================

测试情景记忆的 store / retrieve_relevant / evict_lowest 功能。
使用 fakeredis 模拟 Redis。
"""

import time
import pytest
import fakeredis
import fakeredis.aioredis

from app.memory.episodic import EpisodicMemory
from app.schemas.memory import EpisodicEntry


@pytest.fixture
def redis_client():
    """创建 fakeredis 异步客户端（每个测试独立的 server）。"""
    server = fakeredis.FakeServer()
    return fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)


@pytest.fixture
def memory(redis_client):
    """创建使用 fakeredis 的 EpisodicMemory 实例。"""
    return EpisodicMemory(redis_client=redis_client)


def make_entry(
    importance: float = 0.7,
    timestamp: float = None,
    event: str = "测试事件",
    emotion: str = "happy",
) -> EpisodicEntry:
    """辅助函数：创建测试用 EpisodicEntry。"""
    return EpisodicEntry(
        event=event,
        emotion=emotion,
        ai_suggestion="建议",
        user_feedback="none",
        timestamp=timestamp or time.time(),
        diary_nids=[1],
        importance=importance,
    )


class TestStore:
    """测试 store() 方法。"""

    @pytest.mark.asyncio
    async def test_store_high_importance(self, memory, redis_client):
        """重要性 > 0.5 时应存储成功。"""
        entry = make_entry(importance=0.8)
        result = await memory.store(user_id=1, entry=entry)
        assert result is True

        # 验证 Redis 中存在数据
        key = "memory:episodic:1"
        count = await redis_client.zcard(key)
        assert count == 1

    @pytest.mark.asyncio
    async def test_store_low_importance_skipped(self, memory, redis_client):
        """重要性 <= 0.5 时应跳过存储。"""
        entry = make_entry(importance=0.3)
        result = await memory.store(user_id=1, entry=entry)
        assert result is False

        key = "memory:episodic:1"
        count = await redis_client.zcard(key)
        assert count == 0

    @pytest.mark.asyncio
    async def test_store_exact_threshold_skipped(self, memory, redis_client):
        """重要性恰好等于 0.5 时应跳过存储。"""
        entry = make_entry(importance=0.5)
        result = await memory.store(user_id=1, entry=entry)
        assert result is False

    @pytest.mark.asyncio
    async def test_store_redis_unavailable(self):
        """Redis 不可用时应优雅降级，返回 False。"""
        memory = EpisodicMemory(redis_client=None)
        # 确保 get_redis() 也返回 None
        memory._redis = None
        entry = make_entry(importance=0.9)
        result = await memory.store(user_id=1, entry=entry)
        assert result is False


class TestRetrieveRelevant:
    """测试 retrieve_relevant() 方法。"""

    @pytest.mark.asyncio
    async def test_retrieve_returns_top_k(self, memory):
        """应按 importance * decay 排序返回 top 5。"""
        now = time.time()
        # 存储多个条目，重要性不同
        for i in range(8):
            entry = make_entry(
                importance=0.6 + i * 0.05,
                timestamp=now - i * 3600,  # 每条间隔 1 小时
                event=f"事件{i}",
            )
            await memory.store(user_id=1, entry=entry)

        results = await memory.retrieve_relevant(user_id=1, now=now)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_retrieve_respects_decay(self, memory):
        """较老的记忆应因时间衰减得分更低。"""
        now = time.time()
        # 新的记忆，importance=0.6
        new_entry = make_entry(importance=0.6, timestamp=now, event="新事件")
        # 旧的记忆，importance=0.7，但很旧
        old_entry = make_entry(
            importance=0.7,
            timestamp=now - 30 * 24 * 3600,  # 30 天前
            event="旧事件",
        )
        await memory.store(user_id=1, entry=new_entry)
        await memory.store(user_id=1, entry=old_entry)

        results = await memory.retrieve_relevant(user_id=1, now=now)
        # 新事件应排在前面（衰减后综合得分更高）
        assert results[0].event == "新事件"

    @pytest.mark.asyncio
    async def test_retrieve_empty_when_no_data(self, memory):
        """无数据时应返回空列表。"""
        results = await memory.retrieve_relevant(user_id=999)
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_redis_unavailable(self):
        """Redis 不可用时应返回空列表。"""
        memory = EpisodicMemory(redis_client=None)
        memory._redis = None
        results = await memory.retrieve_relevant(user_id=1)
        assert results == []


class TestEvictLowest:
    """测试 evict_lowest() 方法。"""

    @pytest.mark.asyncio
    async def test_evict_when_over_limit(self, memory, redis_client):
        """超过 100 条时应驱逐重要性最低的条目。"""
        now = time.time()
        key = "memory:episodic:1"

        # 直接往 Redis 插入 102 条（绕过 store 的阈值检查）
        for i in range(102):
            entry = EpisodicEntry(
                event=f"事件{i}",
                emotion="neutral",
                ai_suggestion="建议",
                timestamp=now + i,
                diary_nids=[i],
                importance=0.51 + i * 0.001,  # 0.510 ~ 0.612
            )
            await redis_client.zadd(key, {entry.model_dump_json(): entry.timestamp})

        count_before = await redis_client.zcard(key)
        assert count_before == 102

        evicted = await memory.evict_lowest(user_id=1)
        assert evicted == 2

        count_after = await redis_client.zcard(key)
        assert count_after == 100

    @pytest.mark.asyncio
    async def test_no_eviction_within_limit(self, memory, redis_client):
        """未超过 100 条时不应驱逐。"""
        now = time.time()
        key = "memory:episodic:1"

        for i in range(50):
            entry = EpisodicEntry(
                event=f"事件{i}",
                emotion="neutral",
                ai_suggestion="建议",
                timestamp=now + i,
                diary_nids=[i],
                importance=0.6,
            )
            await redis_client.zadd(key, {entry.model_dump_json(): entry.timestamp})

        evicted = await memory.evict_lowest(user_id=1)
        assert evicted == 0

    @pytest.mark.asyncio
    async def test_evict_removes_lowest_importance(self, memory, redis_client):
        """驱逐应移除重要性最低的条目。"""
        now = time.time()
        key = "memory:episodic:1"

        # 插入 101 条，其中第 0 条重要性最低
        for i in range(101):
            importance = 0.9 if i > 0 else 0.51  # 第 0 条最低
            entry = EpisodicEntry(
                event=f"事件{i}",
                emotion="neutral",
                ai_suggestion="建议",
                timestamp=now + i,
                diary_nids=[i],
                importance=importance,
            )
            await redis_client.zadd(key, {entry.model_dump_json(): entry.timestamp})

        await memory.evict_lowest(user_id=1)

        # 验证剩余条目都是高重要性的
        members = await redis_client.zrangebyscore(key, "-inf", "+inf")
        assert len(members) == 100
        for m in members:
            entry = EpisodicEntry.model_validate_json(m)
            assert entry.importance == 0.9
