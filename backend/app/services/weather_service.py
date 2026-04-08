"""
天气查询服务 — 基于高德地图 API
流程：地址 → geocode 获取 adcode → weather 接口获取天气
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com/v3"


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

    # adcode 在 geocodes[0].adcode
    return data["geocodes"][0].get("adcode")


async def get_weather(address: str) -> str:
    """
    根据地址获取当日天气描述。

    :param address: 城市名或详细地址，如 "北京" / "上海市浦东新区"
    :return: 天气描述字符串，如 "晴 22°C 湿度 45%"；失败时返回简短提示
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
        weather = live.get("weather", "未知")       # 晴、多云、小雨…
        temperature = live.get("temperature", "--") # 摄氏度
        humidity = live.get("humidity", "--")        # 湿度 %
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
        logger.error("天气查询失败，地址：%s，错误：%s", address, exc)
        return "天气获取失败"
