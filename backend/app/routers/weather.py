"""
天气路由
GET /weather/today — 根据当前用户的 address 字段返回今日天气
"""

from fastapi import APIRouter, Depends
from app.core.deps import get_current_user
from app.models.user import User
from app.services.weather_service import get_weather, preheat_weather_for_user
from app.schemas.weather import WeatherPreheatResponse

router = APIRouter()


@router.post("/preheat", summary="天气缓存预热", response_model=WeatherPreheatResponse)
async def preheat_weather(current_user: User = Depends(get_current_user)):
    """
    前端登录后调用，检查并预热天气缓存。
    返回: {status: "hit"|"refreshed"|"no_address"|"error", weather: str|None}
    """
    result = await preheat_weather_for_user(current_user.UID, current_user.address or "")
    return result


@router.get("/today", summary="获取今日天气")
async def today_weather(current_user: User = Depends(get_current_user)):
    """
    根据当前登录用户的 address 字段查询今日天气。
    前端打开网站后调用此接口，将结果展示在页面上。
    """
    weather = await get_weather(current_user.address or "")
    return {
        "address": current_user.address or "未设置",
        "weather": weather,
    }
