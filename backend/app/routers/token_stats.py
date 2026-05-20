"""
Token 消费统计路由模块（Token Stats Router）
============================================

提供 Token 消费统计和分析历史的 RESTful API 接口。
所有接口均需 JWT 认证，仅返回当前用户自己的数据。

接口列表：
- GET /api/analysis/stats    — 返回聚合 Token 统计（支持时间范围和粒度参数）
- GET /api/analysis/history  — 返回分页分析记录（包含所有 Token 分解字段）

Requirements: 24.6, 24.7
"""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.analysis import Analysis
from app.models.diary import DiaryEntry
from app.models.user import User
from app.schemas.token_stats import (
    AnalysisHistory,
    AnalysisHistoryItem,
    DailyTokenStat,
    TokenStats,
)

router = APIRouter()

# 可配置的每 Token 单价（元/Token），用于估算费用
TOKEN_PRICE = 0.00002


@router.get(
    "/stats",
    response_model=TokenStats,
    summary="获取聚合 Token 统计",
    description="返回认证用户的聚合 Token 消费统计，支持时间范围和粒度参数。",
)
def get_token_stats(
    start_date: Optional[date] = Query(None, description="起始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    granularity: str = Query("daily", description="聚合粒度: daily / weekly / monthly"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenStats:
    """
    聚合 Token 统计：
    1. 根据时间范围过滤当前用户的分析记录
    2. 计算总消耗、总付费、平均 Token、分析次数、预估费用
    3. 按粒度聚合每日/每周/每月统计明细
    """
    # 默认时间范围：过去 30 天
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # 构建基础查询：当前用户的分析记录（通过 diary_entries 关联）
    base_query = (
        db.query(Analysis)
        .join(DiaryEntry, Analysis.NID == DiaryEntry.NID)
        .filter(DiaryEntry.UID == current_user.UID)
        .filter(Analysis.Thk_time >= datetime.combine(start_date, datetime.min.time()))
        .filter(Analysis.Thk_time <= datetime.combine(end_date, datetime.max.time()))
    )

    # 获取所有匹配的分析记录
    analyses = base_query.all()

    # 计算汇总统计
    total_tokens = sum((a.Token_cost or 0) for a in analyses)
    total_cache_hit = sum((a.cache_hit_tokens or 0) for a in analyses)
    total_cache_miss = sum((a.cache_miss_tokens or 0) for a in analyses)
    total_output = sum((a.output_tokens or 0) for a in analyses)
    total_paid = total_cache_miss + total_output
    total_analyses = len(analyses)
    average_tokens = total_tokens / total_analyses if total_analyses > 0 else 0.0
    estimated_cost = total_paid * TOKEN_PRICE

    # 按粒度聚合每日统计
    daily_stats = _aggregate_by_granularity(analyses, granularity)

    return TokenStats(
        total_tokens=total_tokens,
        total_paid_tokens=total_paid,
        average_tokens_per_analysis=round(average_tokens, 2),
        total_analyses=total_analyses,
        estimated_cost=round(estimated_cost, 6),
        daily_stats=daily_stats,
    )


@router.get(
    "/history",
    response_model=AnalysisHistory,
    summary="获取分页分析历史",
    description="返回认证用户的分页分析记录，包含所有 Token 分解字段。",
)
def get_analysis_history(
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(20, ge=1, le=100, description="每页记录数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisHistory:
    """
    分页分析历史：
    1. 查询当前用户的所有分析记录
    2. 按时间倒序排列
    3. 分页返回，包含日记片段和 Token 分解
    """
    # 基础查询
    base_query = (
        db.query(Analysis, DiaryEntry.content)
        .join(DiaryEntry, Analysis.NID == DiaryEntry.NID)
        .filter(DiaryEntry.UID == current_user.UID)
    )

    # 总记录数
    total = base_query.count()

    # 分页查询，按时间倒序
    records = (
        base_query
        .order_by(Analysis.Thk_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 构建响应
    items = []
    for analysis, diary_content in records:
        # 日记片段：取前 30 个字符
        snippet = (diary_content or "")[:30]
        items.append(
            AnalysisHistoryItem(
                thk_id=analysis.Thk_ID,
                diary_nid=analysis.NID,
                date=analysis.Thk_time,
                diary_snippet=snippet,
                total_tokens=analysis.Token_cost,
                cache_hit_tokens=analysis.cache_hit_tokens,
                cache_miss_tokens=analysis.cache_miss_tokens,
                output_tokens=analysis.output_tokens,
                agent_mode=analysis.agent_mode,
                activated_agents=analysis.activated_agents,
            )
        )

    return AnalysisHistory(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


def _aggregate_by_granularity(
    analyses: list, granularity: str
) -> list[DailyTokenStat]:
    """
    按粒度聚合分析记录的 Token 统计。

    - daily: 按天聚合
    - weekly: 按周聚合（ISO 周一为起始）
    - monthly: 按月聚合
    """
    from collections import defaultdict

    buckets: dict[str, dict] = defaultdict(
        lambda: {"total_tokens": 0, "cache_hit_tokens": 0, "cache_miss_tokens": 0, "output_tokens": 0}
    )

    for a in analyses:
        if a.Thk_time is None:
            continue

        dt = a.Thk_time
        if granularity == "weekly":
            # ISO 周一为起始，取该周的周一日期作为 key
            week_start = dt.date() - timedelta(days=dt.weekday())
            key = week_start.isoformat()
        elif granularity == "monthly":
            key = dt.strftime("%Y-%m-01")
        else:
            # daily (default)
            key = dt.strftime("%Y-%m-%d")

        buckets[key]["total_tokens"] += a.Token_cost or 0
        buckets[key]["cache_hit_tokens"] += a.cache_hit_tokens or 0
        buckets[key]["cache_miss_tokens"] += a.cache_miss_tokens or 0
        buckets[key]["output_tokens"] += a.output_tokens or 0

    # 按日期排序返回
    sorted_keys = sorted(buckets.keys())
    return [
        DailyTokenStat(
            date=key,
            total_tokens=buckets[key]["total_tokens"],
            cache_hit_tokens=buckets[key]["cache_hit_tokens"],
            cache_miss_tokens=buckets[key]["cache_miss_tokens"],
            output_tokens=buckets[key]["output_tokens"],
        )
        for key in sorted_keys
    ]
