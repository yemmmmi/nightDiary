"""
天气查询服务 — 基于高德地图 API + Redis 缓存
流程：地址 → geocode 获取 adcode → weather 接口获取天气
缓存策略：每个用户的天气结果缓存到 Redis(weather:{uid}, TTL=1h),
         登录时异步预热缓存, 创建日记时优先读缓存。
"""

import os
import logging
import httpx

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com/v3"
WEATHER_CACHE_TTL = 3600  # 1 小时


async def _geocode(address: str, api_key: str) -> str | None:
    """
    地理编码：将地址转换为高德 adcode(行政区划编码)
    :return: adcode 字符串，失败返回 None
    """
    url = f"{AMAP_BASE}/geocode/geo"
    params = {"address": address, "key": api_key, "output": "JSON"}

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != "1" or not data.get("geocodes"):
        logger.warning("geocode 未找到结果，地址：%s", address)
        return None

    return data["geocodes"][0].get("adcode")


async def _fetch_weather_from_api(address: str) -> str:
    """
    直接调用高德 API 获取天气（不走缓存）。
    """
    if not address or not address.strip():
        return "未设置地址"

    api_key = os.getenv("WEATHER_API_KEY", "")
    if not api_key:
        logger.error("WEATHER_API_KEY 未配置")
        return "天气服务未配置"

    try:
        adcode = await _geocode(address.strip(), api_key)
        if not adcode:
            return "地址无法识别"

        url = f"{AMAP_BASE}/weather/weatherInfo"
        params = {"city": adcode, "key": api_key, "extensions": "base", "output": "JSON"}

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1" or not data.get("lives"):
            logger.warning("天气接口返回异常：%s", data)
            return "天气获取失败"

        live = data["lives"][0]
        weather = live.get("weather", "未知")
        temperature = live.get("temperature", "--")
        humidity = live.get("humidity", "--")
        winddirection = live.get("winddirection", "")
        windpower = live.get("windpower", "")

        parts = [f"{weather} {temperature}°C", f"湿度 {humidity}%"]
        if winddirection and windpower:
            parts.append(f"{winddirection}风 {windpower}级")

        return " ".join(parts)

    except httpx.TimeoutException:
        logger.warning("天气查询超时，地址：%s", address)
        return "天气查询超时"
    except Exception as exc:
        logger.error("天气查询失败，地址：%s, 错误: %s", address, exc)
        return "天气获取失败"


async def get_weather(address: str, user_id: int | None = None) -> str:
    """
    获取天气，优先读 Redis 缓存。

    缓存 Key: weather:{user_id}
    缓存 TTL: 1 小时

    :param address: 用户地址
    :param user_id: 用户 ID(有则走缓存逻辑)
    :return: 天气描述字符串
    """
    redis_client = get_redis()

    # 有 user_id 且 Redis 可用时，尝试读缓存
    if user_id and redis_client:
        cache_key = f"weather:{user_id}"
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug("天气缓存命中: uid=%d", user_id)
                return cached
        except Exception as e:
            logger.warning("读取天气缓存失败: uid=%d, error=%s", user_id, e)

    # 缓存未命中，调用 API
    result = await _fetch_weather_from_api(address)

    # 回填缓存（包括"未设置地址"等无效结果，用短 TTL 避免重复判断）
    if user_id and redis_client:
        try:
            # 有效天气结果缓存 1 小时，无效结果缓存 5 分钟
            if result not in ("未设置地址", "天气服务未配置", "地址无法识别"):
                ttl = WEATHER_CACHE_TTL
            else:
                ttl = 300  # 5 分钟后重试
            await redis_client.set(f"weather:{user_id}", result, ex=ttl)
            logger.debug("天气缓存已写入: uid=%d, ttl=%ds, result=%s", user_id, ttl, result[:20])
        except Exception as e:
            logger.warning("写入天气缓存失败: uid=%d, error=%s", user_id, e)

    return result


async def preheat_weather_for_user(user_id: int, address: str) -> dict:
    """
    检查缓存并按需预热，返回结构化结果。
    供前端 POST /weather/preheat 接口调用。

    :return: {"status": "hit"|"refreshed"|"no_address"|"error", "weather": str|None}
    """
    # 地址为空或纯空白 → no_address
    if not address or not address.strip():
        return {"status": "no_address", "weather": None}

    redis_client = get_redis()

    # 有 Redis 时检查缓存
    if redis_client:
        cache_key = f"weather:{user_id}"
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug("天气缓存命中(preheat_for_user): uid=%d", user_id)
                return {"status": "hit", "weather": cached}
        except Exception as e:
            logger.warning("读取天气缓存失败(preheat_for_user): uid=%d, error=%s", user_id, e)

    # 缓存未命中，调用 API
    try:
        result = await _fetch_weather_from_api(address)
    except Exception as exc:
        logger.error("天气 API 调用异常(preheat_for_user): uid=%d, error=%s", user_id, exc)
        return {"status": "error", "weather": None}

    # API 返回的错误字符串视为失败，不写入缓存
    error_results = ("未设置地址", "天气服务未配置", "地址无法识别", "天气获取失败", "天气查询超时")
    if result in error_results:
        return {"status": "error", "weather": None}

    # 写入缓存
    if redis_client:
        try:
            await redis_client.set(f"weather:{user_id}", result, ex=WEATHER_CACHE_TTL)
            logger.info("天气缓存预热完成(preheat_for_user): uid=%d", user_id)
        except Exception as e:
            logger.warning("天气缓存写入失败(preheat_for_user): uid=%d, error=%s", user_id, e)

    return {"status": "refreshed", "weather": result}


async def preheat_weather_cache(user_id: int, address: str) -> None:
    """
    登录时预热天气缓存(fire-and-forget)。
    在后台异步调用天气 API 并写入 Redis, 不阻塞登录响应。
    """
    if not address or not address.strip():
        return

    redis_client = get_redis()
    if not redis_client:
        return

    # 先检查缓存是否已存在且未过期
    cache_key = f"weather:{user_id}"
    try:
        existing = await redis_client.get(cache_key)
        if existing:
            logger.debug("天气缓存仍有效，跳过预热: uid=%d", user_id)
            return
    except Exception:
        pass

    # 调用 API 并缓存
    result = await _fetch_weather_from_api(address)
    if result not in ("未设置地址", "天气服务未配置", "地址无法识别"):
        try:
            await redis_client.set(cache_key, result, ex=WEATHER_CACHE_TTL)
            logger.info("天气缓存预热完成: uid=%d", user_id)
        except Exception as e:
            logger.warning("天气缓存预热写入失败: uid=%d, error=%s", user_id, e)
