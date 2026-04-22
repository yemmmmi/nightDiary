"""
天气相关响应模型
"""

from typing import Literal, Optional
from pydantic import BaseModel


class WeatherPreheatResponse(BaseModel):
    status: Literal["hit", "refreshed", "no_address", "error"]
    weather: Optional[str] = None
