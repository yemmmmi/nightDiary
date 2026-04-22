"""
Redis 异步连接管理模块
使用 redis.asyncio 连接池管理 Redis 连接
连接字符串从环境变量 REDIS_URL 读取
"""

import os
import logging
from typing import Optional

import redis.asyncio as aioredis
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

logger = logging.getLogger(__name__)

# 全局 Redis 客户端实例
_redis_client: Optional[aioredis.Redis] = None

# 从环境变量读取 Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_POOL_SIZE = int(os.getenv("REDIS_POOL_SIZE", "10"))


async def init_redis() -> None:
    """
    初始化 Redis 异步连接池并验证连接可用性。
    应在 FastAPI lifespan 启动时调用。
    """
    global _redis_client
    try:
        _redis_client = aioredis.from_url(
            REDIS_URL,
            max_connections=REDIS_POOL_SIZE,
            decode_responses=True,
        )
        # ping 验证连接可用性
        await _redis_client.ping()
        logger.info("Redis 连接池初始化成功: %s (pool_size=%d)", REDIS_URL, REDIS_POOL_SIZE)
    except Exception as e:
        logger.error("Redis 连接池初始化失败: %s", e)
        _redis_client = None


async def close_redis() -> None:
    """
    优雅关闭 Redis 连接池，释放资源。
    应在 FastAPI lifespan 关闭时调用。
    """
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis 连接池已关闭")
        except Exception as e:
            logger.warning("Redis 连接池关闭时出错: %s", e)
        finally:
            _redis_client = None


def get_redis() -> Optional[aioredis.Redis]:
    """
    FastAPI 依赖注入函数，返回 Redis 客户端实例。
    若 Redis 不可用则返回 None, 支持优雅降级。
    """
    return _redis_client
