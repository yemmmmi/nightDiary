# -*- coding: utf-8 -*-
"""
Property-Based Tests for ReAct Agent Tool Enhancement
Uses hypothesis + pytest

Feature: react-tool-enhancement
"""

from datetime import datetime, timedelta
from typing import Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.ai_service import should_use_cache


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

st_datetime = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2030, 12, 31))
st_timedelta_under_30min = st.timedeltas(min_value=timedelta(seconds=0), max_value=timedelta(minutes=30) - timedelta(seconds=1))
st_timedelta_at_least_30min = st.timedeltas(min_value=timedelta(minutes=30), max_value=timedelta(days=365))


# =========================================================================
# Property 1: 缓存决策与时间阈值一致性
# =========================================================================


class TestProperty1CacheDecisionConsistency:
    """
    # Feature: react-tool-enhancement, Property 1: 缓存决策与时间阈值一致性
    **Validates: Requirements 1.1, 1.2, 1.3**
    """

    @given(now=st_datetime)
    @settings(max_examples=100, deadline=None)
    def test_none_last_time_returns_false(self, now: datetime):
        """last_time 为 None 时，应返回 False（调用 API）"""
        result = should_use_cache(None, now)
        assert result is False

    @given(last_time=st_datetime, delta=st_timedelta_under_30min)
    @settings(max_examples=100, deadline=None)
    def test_within_threshold_returns_true(self, last_time: datetime, delta: timedelta):
        """now - last_time < 30 分钟时，应返回 True（使用缓存）"""
        now = last_time + delta
        result = should_use_cache(last_time, now)
        assert result is True

    @given(last_time=st_datetime, delta=st_timedelta_at_least_30min)
    @settings(max_examples=100, deadline=None)
    def test_at_or_beyond_threshold_returns_false(self, last_time: datetime, delta: timedelta):
        """now - last_time >= 30 分钟时，应返回 False（调用 API）"""
        now = last_time + delta
        result = should_use_cache(last_time, now)
        assert result is False


# =========================================================================
# Task 2.2: 单元测试 — 天气工具缓存与回退逻辑
# Validates: Requirements 1.4, 1.5, 1.6
# =========================================================================

from unittest.mock import MagicMock, patch, PropertyMock
from types import SimpleNamespace

from app.services.ai_service import create_weather_tool


def _make_fake_user(address: Optional[str] = "北京市", last_time: Optional[datetime] = None):
    """创建一个模拟 User 对象，包含 address 和 last_time 字段。"""
    return SimpleNamespace(UID=1, address=address, last_time=last_time)


def _build_weather_tool(fake_user, user_id: int = 1):
    """
    构建天气工具并注入 mock db。
    返回 (tool, mock_db) 以便测试中进一步断言。
    """
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = fake_user
    tool = create_weather_tool(mock_db, user_id)
    return tool, mock_db


class TestWeatherToolCacheHit:
    """测试 Redis 缓存命中时直接返回 (Requirement 1.4)"""

    @patch("redis.Redis.from_url")
    @patch("app.services.ai_service._fetch_weather_from_api")
    def test_cache_hit_returns_cached_value(self, mock_api, mock_redis_from_url):
        """当 should_use_cache=True 且 Redis 有缓存时，直接返回缓存值，不调用 API。"""
        # last_time 设为 5 分钟前 → should_use_cache 返回 True
        fake_user = _make_fake_user(
            address="北京市",
            last_time=datetime.now() - timedelta(minutes=5),
        )
        tool, _ = _build_weather_tool(fake_user)

        # 模拟 Redis 返回缓存数据
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = "晴 25°C 湿度40%"
        mock_redis_from_url.return_value = mock_redis_instance

        result = tool.invoke("")

        assert result == "晴 25°C 湿度40%"
        mock_api.assert_not_called()


class TestWeatherToolRedisFallback:
    """测试 Redis 不可用时回退 API (Requirement 1.5)"""

    @patch("redis.Redis.from_url")
    @patch("app.services.ai_service._fetch_weather_from_api")
    def test_redis_exception_falls_back_to_api(self, mock_api, mock_redis_from_url):
        """Redis 连接异常时，应回退调用高德 API 并返回结果。"""
        fake_user = _make_fake_user(
            address="上海市",
            last_time=datetime.now() - timedelta(minutes=5),
        )
        tool, _ = _build_weather_tool(fake_user)

        # Redis 读取时抛出异常
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.side_effect = Exception("Redis connection refused")
        mock_redis_from_url.return_value = mock_redis_instance

        # API 返回正常结果
        mock_api.return_value = "多云 22°C 湿度60%"

        result = tool.invoke("")

        assert result == "多云 22°C 湿度60%"
        mock_api.assert_called_once_with("上海市")

    @patch("redis.Redis.from_url")
    @patch("app.services.ai_service._fetch_weather_from_api")
    def test_cache_miss_falls_back_to_api(self, mock_api, mock_redis_from_url):
        """Redis 缓存未命中（返回 None）时，应回退调用高德 API。"""
        fake_user = _make_fake_user(
            address="广州市",
            last_time=datetime.now() - timedelta(minutes=10),
        )
        tool, _ = _build_weather_tool(fake_user)

        # Redis 返回 None（缓存未命中）
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None
        mock_redis_from_url.return_value = mock_redis_instance

        mock_api.return_value = "阴 18°C 湿度75%"

        result = tool.invoke("")

        assert result == "阴 18°C 湿度75%"
        mock_api.assert_called_once_with("广州市")


class TestWeatherToolApiBackfill:
    """测试 API 成功后回填 Redis，TTL=3600 (Requirement 1.6)"""

    @patch("redis.Redis.from_url")
    @patch("app.services.ai_service._fetch_weather_from_api")
    def test_api_success_backfills_redis_with_ttl_3600(self, mock_api, mock_redis_from_url):
        """API 成功获取天气后，应将结果写入 Redis 并设置 TTL=3600s。"""
        # last_time 超过 30 分钟 → should_use_cache 返回 False → 直接调 API
        fake_user = _make_fake_user(
            address="深圳市",
            last_time=datetime.now() - timedelta(minutes=60),
        )
        tool, _ = _build_weather_tool(fake_user)

        mock_api.return_value = "晴 30°C 湿度50%"

        # 模拟 Redis 实例（用于回填）
        mock_redis_instance = MagicMock()
        mock_redis_from_url.return_value = mock_redis_instance

        result = tool.invoke("")

        assert result == "晴 30°C 湿度50%"
        mock_api.assert_called_once_with("深圳市")
        # 验证回填 Redis 时使用了 TTL=3600
        mock_redis_instance.setex.assert_called_once_with("weather:1", 3600, "晴 30°C 湿度50%")


class TestWeatherToolNoAddress:
    """测试用户未设置地址时返回提示"""

    def test_address_none_returns_hint(self):
        """用户 address 为 None 时，返回未设置地址提示。"""
        fake_user = _make_fake_user(address=None)
        tool, _ = _build_weather_tool(fake_user)

        result = tool.invoke("")

        assert "未设置地址" in result

    def test_address_empty_string_returns_hint(self):
        """用户 address 为空字符串时，返回未设置地址提示。"""
        fake_user = _make_fake_user(address="")
        tool, _ = _build_weather_tool(fake_user)

        result = tool.invoke("")

        assert "未设置地址" in result

    def test_address_whitespace_only_returns_hint(self):
        """用户 address 仅含空白字符时，返回未设置地址提示。"""
        fake_user = _make_fake_user(address="   ")
        tool, _ = _build_weather_tool(fake_user)

        result = tool.invoke("")

        assert "未设置地址" in result
