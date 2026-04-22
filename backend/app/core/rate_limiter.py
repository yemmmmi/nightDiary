"""
基于 Redis 滑动窗口的 IP 限流模块

使用 Redis Sorted Set 实现滑动窗口算法：
- Score = 请求时间戳（毫秒）
- Member = 请求时间戳（毫秒）
- 每次请求先清理窗口外的旧记录，再统计窗口内请求数

支持 Redis 不可用时的优雅降级：捕获异常，记录 WARNING 日志，放行请求。
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """限流检查结果"""
    allowed: bool
    remaining: int
    reset_time: int  # Unix 时间戳（秒）


class RateLimiter:
    """基于 Redis Sorted Set 滑动窗口的 IP 限流器"""

    @staticmethod
    async def check(
        redis_client: aioredis.Redis,
        client_ip: str,
        limit: int = 60,
        window: int = 60,
    ) -> RateLimitResult:
        """
        检查客户端 IP 是否超过限流阈值。

        算法步骤：
        1. 获取当前时间戳（毫秒）
        2. ZREMRANGEBYSCORE 移除窗口外的旧记录
        3. ZCARD 统计当前窗口内的请求数
        4. 若 count >= limit，返回不允许
        5. ZADD 添加当前时间戳
        6. EXPIRE 设置 Key 过期时间
        7. 返回允许及剩余次数

        Args:
            redis_client: Redis 异步客户端实例
            client_ip: 客户端 IP 地址
            limit: 窗口内允许的最大请求数，默认 60
            window: 滑动窗口大小（秒），默认 60

        Returns:
            RateLimitResult 包含 allowed、remaining、reset_time
        """
        key = f"ratelimit:{client_ip}"
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - window * 1000
        reset_time = int(time.time()) + window

        # 移除窗口外的旧记录
        await redis_client.zremrangebyscore(key, 0, window_start_ms)

        # 统计当前窗口内的请求数
        count = await redis_client.zcard(key)

        if count >= limit:
            remaining = 0
            return RateLimitResult(allowed=False, remaining=remaining, reset_time=reset_time)

        # 添加当前请求时间戳
        await redis_client.zadd(key, {str(now_ms): now_ms})

        # 设置 Key 过期时间，防止无限增长
        await redis_client.expire(key, window)

        remaining = limit - count - 1
        return RateLimitResult(allowed=True, remaining=remaining, reset_time=reset_time)


async def check_rate_limit(
    request: Request,
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
) -> dict:
    """
    FastAPI 依赖函数：检查请求是否超过限流阈值。

    从 Request 获取客户端 IP（支持 X-Forwarded-For 代理头），
    调用 RateLimiter 检查限流，超限时抛出 HTTPException(429)。

    Redis 不可用时降级放行：捕获异常，记录 WARNING 日志，允许请求通过。

    Args:
        request: FastAPI Request 对象
        redis_client: Redis 客户端实例（可能为 None）

    Returns:
        包含限流信息的字典，用于在路由中设置响应头

    Raises:
        HTTPException: 429 状态码，当请求超过限流阈值时
    """
    limit = 60
    window = 60

    # 获取客户端 IP，优先使用 X-Forwarded-For 头（代理场景）
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # Redis 不可用时降级放行
    if redis_client is None:
        logger.warning("Redis 不可用，限流器降级放行: ip=%s", client_ip)
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(limit),
            "X-RateLimit-Reset": str(int(time.time()) + window),
        }

    try:
        result = await RateLimiter.check(redis_client, client_ip, limit, window)

        rate_limit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_time),
        }

        if not result.allowed:
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
                headers=rate_limit_headers,
            )

        return rate_limit_headers

    except HTTPException:
        # 重新抛出 429 异常，不要被下面的通用 except 捕获
        raise
    except Exception as e:
        # Redis 异常时降级放行
        logger.warning("Redis 限流检查异常，降级放行: ip=%s, error=%s", client_ip, e)
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(limit),
            "X-RateLimit-Reset": str(int(time.time()) + window),
        }
