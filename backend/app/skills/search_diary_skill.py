"""
SearchDiarySkill - 日记语义搜索 Skill
=====================================

将 ai_service.py 中的 search_diary 工具封装为 BaseSkill 实现。
基于 Chroma 向量检索 + 多维度过滤（日期范围、标签、关键词）。
"""

import logging
from typing import Optional

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 触发日记搜索的时间回溯关键词
_TEMPORAL_KEYWORDS = (
    "昨天", "前天", "上周", "上个月", "去年", "之前", "以前", "过去",
    "前几天", "前段时间", "那天", "那时", "那次", "上次", "曾经",
    "一直", "又", "还是", "老是", "总是", "每次", "再次", "重复",
    "和之前一样", "跟上次", "像上回",
)


class SearchDiarySkill(BaseSkill):
    """
    日记语义搜索 Skill。

    封装 RAG 检索逻辑：Chroma 向量语义搜索 + 多维度过滤。
    当日记内容包含时间回溯关键词时高概率激活。
    """

    metadata = SkillMetadata(
        name="search_diary",
        description="搜索用户历史日记，支持关键词语义搜索和日期/标签多维过滤",
        category="retrieval",
        token_cost_estimate=200,
        requires_db=True,
        requires_network=False,
        priority=1.5,
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行日记语义搜索。

        context 需包含:
            - user_id: int
            - query: str (搜索关键词)
            - start_date: str (可选, YYYY-MM-DD)
            - end_date: str (可选, YYYY-MM-DD)
            - tag: str (可选, 标签名)
        """
        user_id = context.get("user_id")
        query = kwargs.get("query", "") or context.get("diary_content", "")
        start_date = kwargs.get("start_date", "")
        end_date = kwargs.get("end_date", "")
        tag = kwargs.get("tag", "")

        if not user_id:
            return "搜索失败：缺少用户信息"

        try:
            from app.services.vector_service import search_similar_diaries
            from app.services.ai_service import filter_diary_results, format_diary_result

            # Chroma 语义检索
            results = search_similar_diaries(
                user_id=user_id,
                query=query or "",
                top_k=10,
            )

            # 多维度过滤
            results = filter_diary_results(
                results, start_date=start_date, end_date=end_date, tag=tag
            )

            # 取前 5 条
            results = results[:5]

            if not results:
                conditions = []
                if query:
                    conditions.append(query)
                if start_date:
                    conditions.append(f"从{start_date}")
                if end_date:
                    conditions.append(f"到{end_date}")
                if tag:
                    conditions.append(f"标签:{tag}")
                conditions_str = "、".join(conditions) if conditions else "指定条件"
                return f"未找到与「{conditions_str}」匹配的历史日记。"

            lines = [format_diary_result(item) for item in results]
            return "\n".join(lines)

        except Exception as exc:
            logger.error("SearchDiarySkill 执行失败: %s", exc)
            return "日记搜索暂时不可用"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：
        - retrospective_review 意图: 0.95 (强烈需要检索历史)
        - habit_tracking 意图: 0.8 (需要对比历史数据)
        - 包含时间回溯关键词: 0.85
        - emotional_support 且内容较长: 0.4 (可能需要参考历史)
        - 其他: 0.1
        """
        if intent == "retrospective_review":
            return 0.95

        if intent == "habit_tracking":
            return 0.8

        # 包含时间回溯关键词
        if any(kw in diary_content for kw in _TEMPORAL_KEYWORDS):
            return 0.85

        if intent == "emotional_support" and len(diary_content) > 100:
            return 0.4

        return 0.1
