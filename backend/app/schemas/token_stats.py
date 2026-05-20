"""
Token 消费统计相关 Pydantic Schema
============================

数据流向：
- TokenStats: 后端 → 前端（聚合统计数据）
- AnalysisHistory: 后端 → 前端（分页分析记录）
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class DailyTokenStat(BaseModel):
    """单日 Token 统计。"""
    date: str  # YYYY-MM-DD
    total_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    output_tokens: int = 0


class TokenStats(BaseModel):
    """
    聚合 Token 统计响应。
    GET /api/analysis/stats 端点返回数据。
    """
    total_tokens: int = 0  # 总消耗 Token
    total_paid_tokens: int = 0  # 总付费 Token (cache_miss + output)
    average_tokens_per_analysis: float = 0.0  # 每次分析平均 Token
    total_analyses: int = 0  # 总分析次数
    estimated_cost: float = 0.0  # 预估费用
    daily_stats: List[DailyTokenStat] = []  # 每日统计明细


class AnalysisHistoryItem(BaseModel):
    """单条分析历史记录。"""
    thk_id: int
    diary_nid: int
    date: Optional[datetime] = None
    diary_snippet: str = ""  # 日记前 30 字
    total_tokens: Optional[int] = None
    cache_hit_tokens: Optional[int] = None
    cache_miss_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    agent_mode: Optional[str] = None  # chain | agent | multi_agent
    activated_agents: Optional[str] = None  # JSON list of agent names

    model_config = {"from_attributes": True}


class AnalysisHistory(BaseModel):
    """
    分页分析历史响应。
    GET /api/analysis/history 端点返回数据。
    """
    items: List[AnalysisHistoryItem] = []
    total: int = 0  # 总记录数
    page: int = 1
    page_size: int = 20
