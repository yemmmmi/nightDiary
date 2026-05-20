"""
SentimentSkill - 情感分析 Skill
================================

将 ai_service.py 中的 analyze_sentiment 工具封装为 BaseSkill 实现。
使用 LLM 对日记文本进行结构化情感分析。
"""

import logging
from typing import Optional

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 强情感关键词（暗示需要情感分析）
_EMOTION_KEYWORDS = (
    "开心", "难过", "焦虑", "生气", "愤怒", "伤心", "高兴", "烦躁",
    "压力", "崩溃", "抑郁", "孤独", "幸福", "感动", "失望", "无聊",
    "兴奋", "紧张", "害怕", "恐惧", "羞愧", "内疚", "嫉妒", "委屈",
    "绝望", "迷茫", "疲惫", "心累", "释然", "满足", "感恩",
)


class SentimentSkill(BaseSkill):
    """
    情感分析 Skill。

    封装 LLM 情感分析逻辑，返回情感倾向、强度和关键情感词。
    当日记内容包含明显情感表达时高概率激活。
    """

    metadata = SkillMetadata(
        name="analyze_sentiment",
        description="分析文本情感倾向、强度和关键情感词，用于精准理解用户情绪状态",
        category="analysis",
        token_cost_estimate=150,
        requires_db=False,
        requires_network=True,
        priority=1.2,
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行情感分析。

        context 需包含:
            - diary_content: str (待分析文本)
            - llm: ChatOpenAI 实例 (可选，不提供时尝试从 context 获取)
        """
        text = kwargs.get("text") or context.get("diary_content", "")

        if not text or not text.strip():
            return "无法分析空内容"

        llm = context.get("llm")
        if not llm:
            return "情感分析暂时不可用：缺少 LLM 实例"

        try:
            prompt = f"""请对以下文本进行情感分析，严格按照以下格式输出：
情感倾向：[正面/负面/中性]
情感强度：[1-5]（1=很弱，5=很强）
关键情感词：[词1, 词2, ...]（最多5个）

文本：{text}"""
            response = llm.invoke(prompt)
            return response.content
        except Exception as exc:
            logger.error("SentimentSkill 执行失败: %s", exc)
            return "情感分析暂时不可用"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：
        - emotional_support 意图: 0.9 (情感支持场景必须理解情感)
        - 包含强情感关键词: 0.85
        - retrospective_review 意图: 0.6 (回顾时分析情感趋势有价值)
        - pure_record 意图且内容较长: 0.4
        - 其他: 0.15
        """
        if intent == "emotional_support":
            return 0.9

        # 包含强情感关键词
        emotion_count = sum(1 for kw in _EMOTION_KEYWORDS if kw in diary_content)
        if emotion_count >= 2:
            return 0.85
        if emotion_count == 1:
            return 0.7

        if intent == "retrospective_review":
            return 0.6

        if intent == "pure_record" and len(diary_content) > 80:
            return 0.4

        return 0.15
