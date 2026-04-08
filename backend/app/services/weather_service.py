"""
天气查询服务
使用 wttr.in 免费天气 API，根据地址字符串获取当日天气
无需 API Key，支持中文城市名
"""

import logging
import httpx

logger = logging.getLogger(__name__)

# 天气状态码映射（wttr.in weatherCode）
WEATHER_CODE_MAP = {
    113: "晴", 116: "局部多云", 119: "多云", 122: "阴",
    143: "雾", 176: "局部小雨", 179: "局部小雪", 182: "局部冻雨",
    185: "局部冻雨", 200: "局部雷雨", 227: "吹雪", 230: "暴风雪",
    248: "雾", 260: "冻雾", 263: "局部小雨", 266: "小雨",
    281: "冻毛毛雨", 284: "大冻毛毛雨", 293: "局部小雨", 296: "小雨",
    299: "中雨", 302: "中雨", 305: "局部大雨", 308: "大雨",
    311: "小冻雨", 314: "中冻雨", 317: "小雨夹雪", 320: "中雨夹雪",
    323: "局部小雪", 326: "局部小雪", 329: "局部中雪", 332: "中雪",
    335: "局部大雪", 338: "大雪", 350: "冰雹", 353: "局部小雨",
    356: "中到大雨", 359: "暴雨", 362: "小雨夹雪", 365: "中到大雨夹雪",
    368: "小雪", 371: "中到大雪", 374: "小冰雹", 377: "中到大冰雹",
    386: "局部雷雨", 389: "中到大雷雨", 392: "局部小雪伴雷", 395: "中到大雪伴雷",
}


async def get_weather(address: str) -> str:
    """
    根据地址获取当日天气描述字符串。

    :param address: 城市名或地址，支持中英文（如 "北京", "Shanghai"）
    :return: 天气描述字符串，如 "晴 22°C"；失败时返回 "天气获取失败"
    """
    if not address or not address.strip():
        return "未设置地址"

    url = f"https://wttr.in/{address.strip()}?format=j1&lang=zh"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        current = data["current_condition"][0]
        temp_c = current["temp_C"]
        weather_code = int(current["weatherCode"])
        desc = WEATHER_CODE_MAP.get(weather_code, current.get("weatherDesc", [{}])[0].get("value", "未知"))
        feels_like = current["FeelsLikeC"]

        return f"{desc} {temp_c}°C（体感 {feels_like}°C）"

    except httpx.TimeoutException:
        logger.warning("天气查询超时，地址：%s", address)
        return "天气查询超时"
    except Exception as exc:
        logger.error("天气查询失败，地址：%s，错误：%s", address, exc)
        return "天气获取失败"
