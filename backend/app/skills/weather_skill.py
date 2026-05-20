"""
WeatherSkill - 天气查询 Skill
==============================

将 ai_service.py 中的 get_weather_info 工具封装为 BaseSkill 实现。
支持 Redis 缓存优化 + 高德地图 API 查询。
"""

import logging
import os
from datetime import datetime
from typing import Optional

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 天气相关关键词
_WEATHER_KEYWORDS = (
    "天气", "下雨", "下雪", "晴", "阴天", "刮风", "气温", "温度",
    "冷", "热", "潮湿", "闷", "凉", "暖", "雾", "霾",
    "出门", "散步", "跑步", "户外", "淋雨", "打伞",
)


class WeatherSkill(BaseSkill):
    """
    天气查询 Skill。

    封装天气获取逻辑：Redis 缓存 + 高德地图 API。
    当日记提及天气相关话题或需要地理上下文时激活。
    """

    metadata = SkillMetadata(
        name="get_weather_info",
        description="查询用户所在城市的天气信息，支持缓存优化",
        category="external",
        token_cost_estimate=50,
        requires_db=True,
        requires_network=True,
        priority=0.8,
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行天气查询。

        context 需包含:
            - user_id: int
            - db: SQLAlchemy Session
        """
        user_id = context.get("user_id")
        db = context.get("db")

        if not user_id or not db:
            return "天气查询失败：缺少必要上下文"

        try:
            from app.models.user import User
            from app.services.ai_service import should_use_cache, _fetch_weather_from_api

            user = db.query(User).filter(User.UID == user_id).first()
            if user is None:
                return "天气查询失败，未查询到用户。"

            address = user.address
            if not address or not address.strip():
                return "未设置地址。"

            last_time = user.last_time
            now = datetime.now()
            cache_key = f"weather:{user_id}"

            # 判断是否应使用缓存
            if should_use_cache(last_time, now):
                try:
                    import redis as sync_redis
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                    r = sync_redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                    cached = r.get(cache_key)
                    if cached:
                        return cached
                except Exception as exc:
                    logger.warning("Redis 缓存读取失败，回退 API: %s", exc)

            # 调用高德 API
            result = _fetch_weather_from_api(address)

            if result:
                try:
                    import redis as sync_redis
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                    r = sync_redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                    r.setex(cache_key, 3600, result)
                except Exception as exc:
                    logger.warning("Redis 缓存回填失败: %s", exc)
                return result
            else:
                try:
                    import redis as sync_redis
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                    r = sync_redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                    r.setex(cache_key, 300, "天气获取失败")
                except Exception as exc:
                    logger.warning("Redis 缓存回填失败: %s", exc)
                return "天气获取失败"

        except Exception as exc:
            logger.error("WeatherSkill 执行失败: %s", exc)
            return "天气查询失败"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：
        - 内容包含天气相关关键词: 0.9
        - emotional_support 意图 (天气可增强共情): 0.5
        - pure_record 意图: 0.3 (可作为补充信息)
        - 其他: 0.15
        """
        # 包含天气相关关键词
        if any(kw in diary_content for kw in _WEATHER_KEYWORDS):
            return 0.9

        if intent == "emotional_support":
            return 0.5

        if intent == "pure_record":
            return 0.3

        return 0.15
