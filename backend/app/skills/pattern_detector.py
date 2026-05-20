"""
PatternDetectorSkill - 情绪/行为模式检测 Skill
===============================================

分析指定时间窗口（默认 7 天）内跨日记的情绪和行为模式。
识别反复出现的情绪主题、行为趋势和周期性规律。

Requirements: 20.1
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 情绪相关关键词分组
_EMOTION_PATTERNS = {
    "焦虑": ("焦虑", "紧张", "担心", "不安", "害怕", "恐惧", "忐忑", "慌"),
    "低落": ("难过", "伤心", "低落", "沮丧", "失落", "消沉", "郁闷", "心累"),
    "愤怒": ("生气", "愤怒", "烦躁", "恼火", "不满", "气愤", "火大"),
    "积极": ("开心", "高兴", "快乐", "幸福", "满足", "感恩", "兴奋", "期待"),
    "孤独": ("孤独", "寂寞", "孤单", "没人理", "一个人", "被忽视"),
    "压力": ("压力", "崩溃", "喘不过气", "太多了", "忙不过来", "累死了"),
}

# 行为模式关键词
_BEHAVIOR_PATTERNS = {
    "睡眠问题": ("失眠", "睡不着", "熬夜", "早醒", "睡眠", "做噩梦", "睡得晚"),
    "社交回避": ("不想出门", "不想见人", "拒绝", "取消约会", "宅", "社恐"),
    "运动习惯": ("跑步", "健身", "运动", "散步", "游泳", "瑜伽", "锻炼"),
    "饮食异常": ("没胃口", "暴食", "不想吃", "吃太多", "节食", "外卖"),
    "工作倦怠": ("不想上班", "摸鱼", "没动力", "拖延", "效率低", "厌倦"),
    "积极行动": ("学习", "读书", "早起", "计划", "目标", "进步", "坚持"),
}


class PatternDetectorSkill(BaseSkill):
    """
    情绪/行为模式检测 Skill。

    分析 7 天窗口内的日记条目，识别反复出现的情绪主题和行为趋势。
    当检测到显著模式时，生成结构化的模式报告。
    """

    metadata = SkillMetadata(
        name="pattern_detector",
        description="分析指定时间窗口内跨日记的情绪和行为模式，识别反复主题和趋势",
        category="analysis",
        token_cost_estimate=300,
        requires_db=True,
        requires_network=False,
        priority=1.3,
    )

    # 默认分析窗口（天）
    DEFAULT_WINDOW_DAYS = 7
    # 模式出现次数阈值：超过此值认为是显著模式
    PATTERN_THRESHOLD = 2

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行模式检测。

        分析用户近 7 天的日记条目，识别情绪和行为模式。

        context 需包含:
            - user_id: int
            - diary_content: str (当前日记内容)
            - recent_diaries: List[dict] (可选，近期日记列表，
              每项包含 content, date, mood_score 等字段)

        kwargs:
            - window_days: int (可选，分析窗口天数，默认 7)

        Returns:
            模式分析结果文本
        """
        user_id = context.get("user_id")
        diary_content = context.get("diary_content", "")
        recent_diaries = context.get("recent_diaries") or kwargs.get("recent_diaries")
        window_days = kwargs.get("window_days", self.DEFAULT_WINDOW_DAYS)

        if not user_id:
            return "模式检测失败：缺少用户信息"

        # 如果没有提供近期日记，尝试从数据库获取
        if not recent_diaries:
            recent_diaries = self._fetch_recent_diaries(user_id, window_days)

        if not recent_diaries:
            return f"过去 {window_days} 天内没有足够的日记数据进行模式分析。"

        # 将当前日记也纳入分析
        all_contents = [d.get("content", "") for d in recent_diaries]
        if diary_content and diary_content not in all_contents:
            all_contents.append(diary_content)

        # 检测情绪模式
        emotion_patterns = self._detect_emotion_patterns(all_contents)
        # 检测行为模式
        behavior_patterns = self._detect_behavior_patterns(all_contents)

        # 生成报告
        return self._format_report(
            emotion_patterns, behavior_patterns, len(all_contents), window_days
        )

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：
        - retrospective_review 意图: 0.9 (回顾复盘强烈需要模式分析)
        - habit_tracking 意图: 0.85 (习惯追踪需要识别行为模式)
        - emotional_support 且内容较长: 0.5 (可能需要识别情绪趋势)
        - 包含模式相关关键词: 0.7
        - pure_record: 0.2
        """
        if intent == "retrospective_review":
            return 0.9

        if intent == "habit_tracking":
            return 0.85

        # 包含模式/趋势相关关键词
        pattern_keywords = (
            "最近", "这几天", "一直", "总是", "又", "老是", "每次",
            "反复", "规律", "趋势", "变化", "模式",
        )
        if any(kw in diary_content for kw in pattern_keywords):
            return 0.7

        if intent == "emotional_support" and len(diary_content) > 100:
            return 0.5

        return 0.2

    def _fetch_recent_diaries(
        self, user_id: int, window_days: int
    ) -> List[dict]:
        """
        从数据库获取用户近期日记。

        Args:
            user_id: 用户 ID
            window_days: 时间窗口天数

        Returns:
            日记列表，每项包含 content, date 等字段
        """
        try:
            from app.core.database import SessionLocal
            from app.models.diary import DiaryEntry

            start_date = datetime.now() - timedelta(days=window_days)

            with SessionLocal() as db:
                entries = (
                    db.query(DiaryEntry)
                    .filter(
                        DiaryEntry.UID == user_id,
                        DiaryEntry.created_at >= start_date,
                    )
                    .order_by(DiaryEntry.created_at.desc())
                    .all()
                )

                return [
                    {
                        "content": entry.content or "",
                        "date": str(entry.created_at),
                        "nid": entry.NID,
                    }
                    for entry in entries
                ]
        except Exception as e:
            logger.error("获取近期日记失败 (user_id=%d): %s", user_id, e)
            return []

    def _detect_emotion_patterns(
        self, contents: List[str]
    ) -> dict[str, int]:
        """
        检测情绪模式。

        统计各情绪类别在日记中出现的频次。

        Args:
            contents: 日记内容列表

        Returns:
            情绪类别 -> 出现次数 的映射（仅包含超过阈值的）
        """
        emotion_counts: dict[str, int] = {}

        for content in contents:
            # 每篇日记中每个情绪类别最多计一次
            for category, keywords in _EMOTION_PATTERNS.items():
                if any(kw in content for kw in keywords):
                    emotion_counts[category] = emotion_counts.get(category, 0) + 1

        # 过滤出显著模式
        return {
            k: v for k, v in emotion_counts.items()
            if v >= self.PATTERN_THRESHOLD
        }

    def _detect_behavior_patterns(
        self, contents: List[str]
    ) -> dict[str, int]:
        """
        检测行为模式。

        统计各行为类别在日记中出现的频次。

        Args:
            contents: 日记内容列表

        Returns:
            行为类别 -> 出现次数 的映射（仅包含超过阈值的）
        """
        behavior_counts: dict[str, int] = {}

        for content in contents:
            for category, keywords in _BEHAVIOR_PATTERNS.items():
                if any(kw in content for kw in keywords):
                    behavior_counts[category] = behavior_counts.get(category, 0) + 1

        return {
            k: v for k, v in behavior_counts.items()
            if v >= self.PATTERN_THRESHOLD
        }

    def _format_report(
        self,
        emotion_patterns: dict[str, int],
        behavior_patterns: dict[str, int],
        diary_count: int,
        window_days: int,
    ) -> str:
        """
        格式化模式分析报告。

        Args:
            emotion_patterns: 检测到的情绪模式
            behavior_patterns: 检测到的行为模式
            diary_count: 分析的日记总数
            window_days: 分析窗口天数

        Returns:
            结构化的模式报告文本
        """
        lines: List[str] = []
        lines.append(f"📊 过去 {window_days} 天模式分析（基于 {diary_count} 篇日记）：")

        if not emotion_patterns and not behavior_patterns:
            lines.append("未检测到显著的重复模式。")
            return "\n".join(lines)

        if emotion_patterns:
            lines.append("\n🎭 情绪模式：")
            # 按频次降序排列
            sorted_emotions = sorted(
                emotion_patterns.items(), key=lambda x: x[1], reverse=True
            )
            for category, count in sorted_emotions:
                frequency = f"{count}/{diary_count} 篇日记"
                lines.append(f"  • {category}：出现 {frequency}")

        if behavior_patterns:
            lines.append("\n🔄 行为模式：")
            sorted_behaviors = sorted(
                behavior_patterns.items(), key=lambda x: x[1], reverse=True
            )
            for category, count in sorted_behaviors:
                frequency = f"{count}/{diary_count} 篇日记"
                lines.append(f"  • {category}：出现 {frequency}")

        return "\n".join(lines)
