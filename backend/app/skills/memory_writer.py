"""
MemoryWriterSkill - 情景记忆写入 Skill
========================================

在每次 AI 分析完成后，评估交互的重要性并将重要交互结果
持久化到 Episodic Memory（Redis Sorted Set）。

重要性评估基于以下因素：
- 情感强度（强情感交互更值得记忆）
- 意图类型（emotional_support 和 retrospective_review 更重要）
- 内容长度（较长的日记通常包含更多有价值信息）
- 是否包含关键事件或人物

Requirements: 20.4
"""

import logging
import time

from app.memory.episodic import EpisodicMemory
from app.schemas.memory import EpisodicEntry
from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 重要性评估权重
_INTENT_IMPORTANCE = {
    "emotional_support": 0.3,
    "retrospective_review": 0.25,
    "habit_tracking": 0.2,
    "pure_record": 0.1,
}

# 情感关键词（用于评估情感强度）
_EMOTION_KEYWORDS = (
    "开心", "难过", "焦虑", "生气", "愤怒", "伤心", "高兴", "烦躁",
    "压力", "崩溃", "抑郁", "孤独", "幸福", "感动", "失望", "绝望",
    "兴奋", "紧张", "害怕", "恐惧", "委屈", "迷茫", "疲惫", "释然",
    "满足", "感恩", "自豪", "温暖",
)

# 事件/人物关键词（暗示重要交互）
_EVENT_KEYWORDS = (
    "第一次", "终于", "决定", "发现", "改变", "突然", "意外",
    "重要", "关键", "转折", "里程碑", "成功", "失败",
)


def _estimate_importance(diary_content: str, intent: str) -> float:
    """
    估算交互的重要性分数。

    综合考虑意图类型、情感强度、内容长度和关键事件。
    返回值范围 [0.0, 1.0]。
    """
    score = 0.0

    # 1. 意图类型基础分
    score += _INTENT_IMPORTANCE.get(intent, 0.1)

    # 2. 情感强度（情感关键词越多，越重要）
    emotion_count = sum(1 for kw in _EMOTION_KEYWORDS if kw in diary_content)
    emotion_bonus = min(0.3, emotion_count * 0.08)
    score += emotion_bonus

    # 3. 内容长度（较长内容通常更有价值）
    content_len = len(diary_content)
    if content_len > 300:
        score += 0.15
    elif content_len > 150:
        score += 0.1
    elif content_len > 50:
        score += 0.05

    # 4. 关键事件/人物
    event_count = sum(1 for kw in _EVENT_KEYWORDS if kw in diary_content)
    event_bonus = min(0.2, event_count * 0.07)
    score += event_bonus

    # 限制在 [0.0, 1.0]
    return max(0.0, min(1.0, score))


def _extract_emotion_label(diary_content: str) -> str:
    """
    从日记内容中提取主要情感标签。

    返回检测到的第一个情感关键词，若无则返回 "neutral"。
    """
    for kw in _EMOTION_KEYWORDS:
        if kw in diary_content:
            return kw
    return "neutral"


def _generate_event_summary(diary_content: str) -> str:
    """
    生成事件摘要。

    取日记内容的前 100 个字符作为事件描述。
    """
    content = diary_content.strip()
    if len(content) <= 100:
        return content
    return content[:100] + "..."


class MemoryWriterSkill(BaseSkill):
    """
    情景记忆写入 Skill。

    在每次分析完成后评估交互重要性，将重要交互持久化到 Episodic Memory。
    仅当重要性分数 > 0.5 时才写入（由 EpisodicMemory.store() 内部控制）。

    Requirements: 20.4
    """

    metadata = SkillMetadata(
        name="memory_writer",
        description="分析后将重要交互结果持久化到 Episodic Memory，维护交互记忆连续性",
        category="memory",
        token_cost_estimate=30,
        requires_db=False,
        requires_network=False,
        priority=0.8,  # 较低优先级，在其他分析完成后执行
    )

    def __init__(self, episodic_memory: EpisodicMemory | None = None):
        """
        初始化 MemoryWriterSkill。

        Args:
            episodic_memory: EpisodicMemory 实例，若为 None 则在执行时创建。
        """
        self._episodic_memory = episodic_memory

    @property
    def episodic_memory(self) -> EpisodicMemory:
        """获取 EpisodicMemory 实例，支持延迟初始化。"""
        if self._episodic_memory is None:
            self._episodic_memory = EpisodicMemory()
        return self._episodic_memory

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行记忆写入。

        评估当前交互的重要性，若超过阈值则持久化到 Episodic Memory。

        context 需包含:
            - diary_content: str (日记内容)
            - user_id: int (用户 ID)
            - intent: str (分类意图)
            - diary_nid: int (日记 NID，可选)
            - empathy_response: str (AI 共情回应，可选)
            - insight_response: str (AI 洞察回应，可选)

        Returns:
            写入结果描述文本。
        """
        diary_content = context.get("diary_content", "")
        user_id = context.get("user_id")
        intent = context.get("intent", "pure_record")
        diary_nid = context.get("diary_nid", 0)
        ai_suggestion = kwargs.get("ai_suggestion", "") or context.get(
            "empathy_response", ""
        ) or context.get("insight_response", "")

        if not user_id:
            return "记忆写入跳过：缺少用户信息"

        if not diary_content:
            return "记忆写入跳过：无日记内容"

        # 评估重要性
        importance = _estimate_importance(diary_content, intent)

        if importance <= EpisodicMemory.IMPORTANCE_THRESHOLD:
            logger.debug(
                "MemoryWriterSkill 跳过写入：importance=%.2f <= %.2f (user_id=%s)",
                importance, EpisodicMemory.IMPORTANCE_THRESHOLD, user_id,
            )
            return f"交互重要性较低（{importance:.2f}），未写入记忆。"

        # 构建 EpisodicEntry
        entry = EpisodicEntry(
            event=_generate_event_summary(diary_content),
            emotion=_extract_emotion_label(diary_content),
            ai_suggestion=ai_suggestion[:200] if ai_suggestion else "",
            user_feedback="none",
            timestamp=time.time(),
            diary_nids=[diary_nid] if diary_nid else [],
            importance=importance,
        )

        # 异步写入需要在事件循环中执行
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已在异步上下文中，创建 task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, self.episodic_memory.store(user_id, entry)
                    )
                    stored = future.result(timeout=5)
            else:
                stored = loop.run_until_complete(
                    self.episodic_memory.store(user_id, entry)
                )
        except RuntimeError:
            # 没有事件循环时创建新的
            stored = asyncio.run(self.episodic_memory.store(user_id, entry))
        except Exception as e:
            logger.error("MemoryWriterSkill 写入失败: %s", e)
            return f"记忆写入失败（降级跳过）: {e}"

        if stored:
            logger.info(
                "MemoryWriterSkill 成功写入 (user_id=%s, importance=%.2f)",
                user_id, importance,
            )
            return (
                f"交互已写入情景记忆（重要性: {importance:.2f}，"
                f"情感: {entry.emotion}）。"
            )
        else:
            return f"交互重要性不足或 Redis 不可用，未写入记忆。"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：

        记忆写入应在分析完成后执行，激活概率基于预估重要性：
        - emotional_support 意图: 0.9 (情感交互通常值得记忆)
        - retrospective_review 意图: 0.85
        - habit_tracking 意图: 0.7
        - 内容较长 (> 100 字符): 0.6
        - pure_record 且内容短: 0.3
        """
        if intent == "emotional_support":
            return 0.9

        if intent == "retrospective_review":
            return 0.85

        if intent == "habit_tracking":
            return 0.7

        if len(diary_content) > 100:
            return 0.6

        return 0.3
