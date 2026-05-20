"""
SummaryGeneratorSkill - 结构化周报/月报摘要生成 Skill
=====================================================

当用户明确请求时，生成结构化的周报或月报摘要。

摘要包含以下结构化部分：
1. 📊 主导情绪：本周/月最突出的情绪状态
2. 📌 关键事件：影响情绪的重要事件（2-3个）
3. 📈 趋势方向：情绪变化趋势（上升/下降/波动/稳定）
4. 💡 个性化建议：基于分析的具体可操作建议（2-3条）

Requirements: 20.6
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 周报/月报关键词
_REPORT_KEYWORDS_WEEKLY = [
    "周报", "这周", "本周", "一周", "过去七天", "过去7天", "weekly",
    "这一周", "上周总结", "本周总结", "周总结",
]
_REPORT_KEYWORDS_MONTHLY = [
    "月报", "这个月", "本月", "一个月", "过去三十天", "过去30天", "monthly",
    "这一个月", "上月总结", "本月总结", "月总结",
]

# 摘要生成系统提示词
_SUMMARY_SYSTEM_PROMPT = """你是一位专业的心理洞察分析师，正在为用户生成{report_type}摘要。

请基于用户提供的日记数据，生成结构化报告，严格包含以下四个部分：

📊 主导情绪
分析本{period}最突出的情绪状态，说明出现频率和强度。

📌 关键事件
列出影响情绪的 2-3 个重要事件，简要描述每个事件及其情绪影响。

📈 趋势方向
判断情绪变化趋势（上升/下降/波动/稳定），并简要说明依据。

💡 个性化建议
基于以上分析，给出 2-3 条具体可操作的建议。建议必须与用户实际情况相关，避免泛泛的鼓励。

要求：
- 语言温和、有洞察力
- 建议必须具体可执行
- 总长度控制在 300-500 字
- 如果日记数据不足，诚实说明并基于已有数据给出分析
"""


def _detect_report_type(diary_content: str) -> Optional[str]:
    """
    检测用户是否请求周报或月报。

    Args:
        diary_content: 日记内容

    Returns:
        "weekly" | "monthly" | None
    """
    content_lower = diary_content.lower()
    for keyword in _REPORT_KEYWORDS_MONTHLY:
        if keyword in content_lower:
            return "monthly"
    for keyword in _REPORT_KEYWORDS_WEEKLY:
        if keyword in content_lower:
            return "weekly"
    return None


def _get_time_range(report_type: str) -> Tuple[datetime, datetime]:
    """
    根据报告类型计算时间范围。

    Args:
        report_type: "weekly" 或 "monthly"

    Returns:
        (start_date, end_date) 元组
    """
    now = datetime.now()
    if report_type == "monthly":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=7)
    return start, now


def _fetch_diary_entries(user_id: int, start_date: datetime, end_date: datetime) -> List[dict]:
    """
    从数据库获取指定时间范围内的日记条目。

    Args:
        user_id: 用户 ID
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        日记条目列表，每条包含 date, content, weather 字段
    """
    try:
        from app.core.database import SessionLocal
        from app.models.diary import DiaryEntry

        db = SessionLocal()
        try:
            entries = (
                db.query(DiaryEntry)
                .filter(
                    DiaryEntry.UID == user_id,
                    DiaryEntry.date >= start_date.date(),
                    DiaryEntry.date <= end_date.date(),
                )
                .order_by(DiaryEntry.date.asc())
                .all()
            )

            results = []
            for entry in entries:
                if entry.content and len(entry.content.strip()) > 0:
                    results.append({
                        "date": str(entry.date) if entry.date else "",
                        "content": entry.content,
                        "weather": entry.weather or "",
                    })
            return results
        finally:
            db.close()
    except Exception as e:
        logger.error("获取日记条目失败 (user_id=%d): %s", user_id, e)
        return []


def _fetch_episodic_memories(user_id: int, start_timestamp: float) -> List[dict]:
    """
    从 Episodic Memory 获取指定时间范围内的记忆条目。

    同步包装异步调用，用于 Skill 执行上下文。

    Args:
        user_id: 用户 ID
        start_timestamp: 起始时间戳

    Returns:
        记忆条目列表
    """
    try:
        import asyncio
        from app.memory.episodic import EpisodicMemory

        memory = EpisodicMemory()
        # 尝试在已有事件循环中运行，或创建新的
        try:
            loop = asyncio.get_running_loop()
            # 如果已在异步上下文中，无法直接 await，返回空列表
            # Skill 的 execute 是同步的，通常不在异步上下文中
            return []
        except RuntimeError:
            pass

        # 没有运行中的事件循环，创建新的
        loop = asyncio.new_event_loop()
        try:
            entries = loop.run_until_complete(
                memory.retrieve_relevant(user_id=user_id, top_k=10)
            )
            # 过滤时间范围内的条目
            return [
                entry.model_dump()
                for entry in entries
                if entry.timestamp >= start_timestamp
            ]
        finally:
            loop.close()
    except Exception as e:
        logger.debug("获取情景记忆失败，降级跳过: %s", e)
        return []


def _build_diary_summary_text(
    diary_entries: List[dict],
    episodic_memories: List[dict],
) -> str:
    """
    将日记条目和记忆条目格式化为 LLM 可分析的文本。

    Args:
        diary_entries: 日记条目列表
        episodic_memories: 情景记忆条目列表

    Returns:
        格式化的摘要文本
    """
    parts = []

    if diary_entries:
        diary_lines = []
        for entry in diary_entries:
            date_str = entry.get("date", "")
            content = entry.get("content", "")
            # 截取前 200 字符避免过长
            if len(content) > 200:
                content = content[:200] + "..."
            weather = entry.get("weather", "")
            line = f"[{date_str}]"
            if weather:
                line += f" ({weather})"
            line += f" {content}"
            diary_lines.append(line)
        parts.append("【日记记录】\n" + "\n".join(diary_lines))

    if episodic_memories:
        memory_lines = []
        for mem in episodic_memories:
            event = mem.get("event", "")
            emotion = mem.get("emotion", "")
            if event:
                line = f"- {event}"
                if emotion:
                    line += f"（情绪: {emotion}）"
                memory_lines.append(line)
        if memory_lines:
            parts.append("【重要记忆】\n" + "\n".join(memory_lines))

    if not parts:
        return "（该时间段内暂无日记数据）"

    return "\n\n".join(parts)


def _build_llm() -> ChatOpenAI:
    """构建 LLM 实例。"""
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("SummaryGeneratorSkill: LLM_API_KEY 未配置")

    kwargs = {
        "api_key": api_key,
        "model": model,
        "temperature": 0.5,
        "max_tokens": 800,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)


class SummaryGeneratorSkill(BaseSkill):
    """
    结构化周报/月报摘要生成 Skill。

    当用户明确请求周报或月报时激活，生成包含主导情绪、关键事件、
    趋势方向和个性化建议的结构化报告。

    Requirements: 20.6
    """

    metadata = SkillMetadata(
        name="summary_generator",
        description="生成结构化周报/月报摘要，包含主导情绪、关键事件、趋势方向和个性化建议",
        category="generation",
        token_cost_estimate=500,
        requires_db=True,
        requires_network=True,
        priority=1.8,
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行摘要生成。

        context 需包含:
            - user_id: int
            - diary_content: str (包含报告请求的日记内容)

        Returns:
            结构化的周报/月报摘要文本
        """
        user_id = context.get("user_id")
        diary_content = context.get("diary_content", "")

        if not user_id:
            return "摘要生成失败：缺少用户信息"

        # 1. 检测报告类型
        report_type = _detect_report_type(diary_content)
        if not report_type:
            # 默认生成周报
            report_type = "weekly"

        # 2. 计算时间范围
        start_date, end_date = _get_time_range(report_type)

        # 3. 获取日记数据
        diary_entries = _fetch_diary_entries(user_id, start_date, end_date)

        # 4. 获取情景记忆（降级容错）
        episodic_memories = _fetch_episodic_memories(
            user_id, start_date.timestamp()
        )

        # 5. 构建数据文本
        data_text = _build_diary_summary_text(diary_entries, episodic_memories)

        # 6. 构建 LLM 提示
        period = "周" if report_type == "weekly" else "月"
        report_type_label = "周报" if report_type == "weekly" else "月报"
        system_prompt = _SUMMARY_SYSTEM_PROMPT.format(
            report_type=report_type_label, period=period
        )

        user_message = (
            f"请为我生成{report_type_label}摘要。\n\n"
            f"时间范围：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}\n"
            f"共 {len(diary_entries)} 篇日记\n\n"
            f"{data_text}"
        )

        # 7. 调用 LLM 生成摘要
        try:
            llm = _build_llm()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
            response = llm.invoke(messages)
            summary = response.content.strip()

            logger.info(
                "SummaryGeneratorSkill 完成 (user_id=%d, type=%s, entries=%d)",
                user_id, report_type, len(diary_entries),
            )
            return summary

        except Exception as e:
            logger.error("SummaryGeneratorSkill LLM 调用失败: %s", e)
            # 降级：返回基于数据的简要统计
            if diary_entries:
                return (
                    f"摘要生成暂时不可用（LLM 服务异常）。\n"
                    f"本{period}共记录 {len(diary_entries)} 篇日记，"
                    f"时间范围：{start_date.strftime('%Y-%m-%d')} 至 "
                    f"{end_date.strftime('%Y-%m-%d')}。"
                )
            return "摘要生成暂时不可用"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：

        - 包含周报/月报关键词: 0.95 (明确请求报告)
        - retrospective_review 意图 + 内容暗示总结: 0.7
        - retrospective_review 意图: 0.4
        - 其他: 0.05 (几乎不激活)
        """
        # 明确包含报告关键词 → 高概率激活
        content_lower = diary_content.lower()
        for keyword in _REPORT_KEYWORDS_MONTHLY + _REPORT_KEYWORDS_WEEKLY:
            if keyword in content_lower:
                return 0.95

        # 回顾复盘意图 + 总结相关词汇
        if intent == "retrospective_review":
            summary_hints = ["总结", "回顾", "复盘", "盘点", "梳理"]
            if any(hint in diary_content for hint in summary_hints):
                return 0.7
            return 0.4

        return 0.05
