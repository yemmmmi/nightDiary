"""
MemoryReaderSkill - 情景记忆读取 Skill
========================================

在每次 AI 分析开始前，从 Episodic Memory 中检索与当前日记内容
相关的历史交互记忆，为后续 Agent 提供上下文连续性。

检索策略：
- 按 importance * 时间衰减因子 综合排序
- 返回最相关的 top 5 条记录
- Redis 不可用时优雅降级（返回空上下文）

Requirements: 20.5
"""

import logging

from app.memory.episodic import EpisodicMemory
from app.schemas.memory import EpisodicEntry
from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)


def _format_episodic_entries(entries: list[EpisodicEntry]) -> str:
    """
    将情景记忆条目格式化为可读的上下文文本。

    每条记忆包含事件描述、情感标签、AI 建议和用户反馈。
    """
    if not entries:
        return ""

    lines = []
    for i, entry in enumerate(entries, 1):
        parts = [f"[记忆 {i}]"]

        if entry.event:
            parts.append(f"事件：{entry.event}")
        if entry.emotion and entry.emotion != "neutral":
            parts.append(f"情感：{entry.emotion}")
        if entry.ai_suggestion:
            parts.append(f"当时建议：{entry.ai_suggestion[:100]}")
        if entry.user_feedback and entry.user_feedback != "none":
            parts.append(f"用户反馈：{entry.user_feedback}")

        lines.append(" | ".join(parts))

    return "\n".join(lines)


class MemoryReaderSkill(BaseSkill):
    """
    情景记忆读取 Skill。

    在分析开始前检索相关的 Episodic Memory 上下文，
    为 Empathy Agent 和 Insight Agent 提供历史交互记忆，
    实现关怀的连续性。

    Requirements: 20.5
    """

    metadata = SkillMetadata(
        name="memory_reader",
        description="分析前检索相关 Episodic Memory 上下文，提供交互记忆连续性",
        category="memory",
        token_cost_estimate=20,
        requires_db=False,
        requires_network=False,
        priority=1.8,  # 较高优先级，应在其他分析 Skill 之前执行
    )

    def __init__(self, episodic_memory: EpisodicMemory | None = None):
        """
        初始化 MemoryReaderSkill。

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
        执行记忆检索。

        从 Episodic Memory 中检索与当前日记内容相关的历史交互记忆。

        context 需包含:
            - user_id: int (用户 ID)
            - diary_content: str (当前日记内容，用作查询)

        kwargs 可选:
            - top_k: int (返回条目数，默认 5)

        Returns:
            格式化的记忆上下文文本。若无相关记忆或 Redis 不可用则返回提示信息。
        """
        user_id = context.get("user_id")
        diary_content = context.get("diary_content", "")
        top_k = kwargs.get("top_k", 5)

        if not user_id:
            return "记忆检索跳过：缺少用户信息"

        # 异步检索需要在事件循环中执行
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已在异步上下文中，使用线程池
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.episodic_memory.retrieve_relevant(
                            user_id=user_id,
                            query=diary_content,
                            top_k=top_k,
                        ),
                    )
                    entries = future.result(timeout=5)
            else:
                entries = loop.run_until_complete(
                    self.episodic_memory.retrieve_relevant(
                        user_id=user_id,
                        query=diary_content,
                        top_k=top_k,
                    )
                )
        except RuntimeError:
            # 没有事件循环时创建新的
            entries = asyncio.run(
                self.episodic_memory.retrieve_relevant(
                    user_id=user_id,
                    query=diary_content,
                    top_k=top_k,
                )
            )
        except Exception as e:
            logger.error("MemoryReaderSkill 检索失败: %s", e)
            return "记忆检索失败（降级跳过），将在无历史上下文情况下继续分析。"

        if not entries:
            logger.debug(
                "MemoryReaderSkill 未找到相关记忆 (user_id=%s)", user_id
            )
            return "暂无相关历史交互记忆。"

        # 格式化记忆条目
        formatted = _format_episodic_entries(entries)

        logger.info(
            "MemoryReaderSkill 检索到 %d 条相关记忆 (user_id=%s)",
            len(entries), user_id,
        )

        return f"检索到 {len(entries)} 条相关历史交互记忆：\n{formatted}"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：

        记忆读取应在分析开始前执行，几乎所有场景都应激活：
        - emotional_support 意图: 0.95 (情感支持需要记忆连续性)
        - retrospective_review 意图: 0.9 (回顾需要历史上下文)
        - habit_tracking 意图: 0.85 (习惯追踪需要对比历史)
        - pure_record 意图: 0.5 (纯记录也可能受益于记忆上下文)
        """
        if intent == "emotional_support":
            return 0.95

        if intent == "retrospective_review":
            return 0.9

        if intent == "habit_tracking":
            return 0.85

        # pure_record 或其他
        return 0.5
