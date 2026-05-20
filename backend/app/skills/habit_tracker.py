"""
HabitTrackerSkill - 习惯追踪 Skill
====================================

监控用户提及的目标和习惯，追踪进度并提供督促反馈。
通过分析日记内容中的习惯/目标相关描述，识别用户正在坚持或放弃的习惯。

Requirements: 20.2
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 习惯/目标相关关键词
_HABIT_KEYWORDS = (
    "坚持", "习惯", "目标", "计划", "打卡", "连续", "第.*天",
    "每天", "每周", "日常", "养成", "保持", "继续",
)

# 正向进度关键词
_POSITIVE_PROGRESS = (
    "坚持了", "完成了", "做到了", "成功", "进步", "提升",
    "达成", "突破", "保持住", "没有放弃", "继续",
)

# 负向/中断关键词
_NEGATIVE_PROGRESS = (
    "放弃", "中断", "没做到", "忘了", "偷懒", "失败",
    "没坚持", "断了", "没有完成", "拖延", "算了",
)

# 常见习惯类别及其关键词
_HABIT_CATEGORIES = {
    "运动健身": ("跑步", "健身", "运动", "散步", "游泳", "瑜伽", "锻炼", "步数", "公里"),
    "早起早睡": ("早起", "早睡", "起床", "闹钟", "熬夜", "作息", "睡觉时间"),
    "阅读学习": ("读书", "阅读", "学习", "看书", "课程", "背单词", "英语"),
    "饮食健康": ("饮食", "少吃", "健康饮食", "不吃零食", "喝水", "戒糖", "减肥"),
    "冥想正念": ("冥想", "正念", "静坐", "呼吸练习", "放松"),
    "写作记录": ("写日记", "记录", "写作", "复盘", "总结"),
    "社交联系": ("联系朋友", "打电话", "约人", "社交", "聚会"),
    "工作效率": ("番茄钟", "专注", "效率", "任务", "清单", "GTD"),
}


class HabitTrackerSkill(BaseSkill):
    """
    习惯追踪 Skill。

    监控用户在日记中提及的目标和习惯，追踪进度并提供问责反馈。
    通过关键词匹配和上下文分析，识别用户正在坚持或放弃的习惯。
    """

    metadata = SkillMetadata(
        name="habit_tracker",
        description="追踪用户提及的目标和习惯，监控进度并提供督促反馈",
        category="analysis",
        token_cost_estimate=250,
        requires_db=True,
        requires_network=False,
        priority=1.2,
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行习惯追踪分析。

        分析当前日记和近期日记中的习惯/目标提及，
        识别进度状态并生成反馈。

        context 需包含:
            - user_id: int
            - diary_content: str (当前日记内容)
            - recent_diaries: List[dict] (可选，近期日记列表)

        kwargs:
            - window_days: int (可选，分析窗口天数，默认 7)

        Returns:
            习惯追踪分析结果文本
        """
        user_id = context.get("user_id")
        diary_content = context.get("diary_content", "")
        recent_diaries = context.get("recent_diaries") or kwargs.get("recent_diaries")
        window_days = kwargs.get("window_days", 7)

        if not user_id:
            return "习惯追踪失败：缺少用户信息"

        # 如果没有提供近期日记，尝试从数据库获取
        if not recent_diaries:
            recent_diaries = self._fetch_recent_diaries(user_id, window_days)

        # 分析当前日记中的习惯提及
        current_habits = self._identify_habits(diary_content)

        # 分析近期日记中的习惯趋势
        habit_history = self._analyze_habit_history(recent_diaries)

        # 检测当前日记的进度信号
        progress_signal = self._detect_progress_signal(diary_content)

        # 生成反馈报告
        return self._format_feedback(
            current_habits, habit_history, progress_signal,
            diary_content, len(recent_diaries), window_days
        )

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：
        - habit_tracking 意图: 0.95 (专门的习惯追踪场景)
        - 包含习惯/目标关键词: 0.8
        - retrospective_review 意图: 0.6 (回顾时可能涉及习惯进度)
        - 包含常见习惯类别关键词: 0.65
        - emotional_support: 0.2
        - pure_record: 0.15
        """
        if intent == "habit_tracking":
            return 0.95

        # 包含习惯/目标关键词
        if any(kw in diary_content for kw in _HABIT_KEYWORDS):
            return 0.8

        # 包含常见习惯类别关键词
        for category, keywords in _HABIT_CATEGORIES.items():
            if any(kw in diary_content for kw in keywords):
                return 0.65

        if intent == "retrospective_review":
            return 0.6

        if intent == "emotional_support":
            return 0.2

        return 0.15

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

    def _identify_habits(self, content: str) -> List[str]:
        """
        识别文本中提及的习惯类别。

        Args:
            content: 日记内容

        Returns:
            识别到的习惯类别名称列表
        """
        identified: List[str] = []
        for category, keywords in _HABIT_CATEGORIES.items():
            if any(kw in content for kw in keywords):
                identified.append(category)
        return identified

    def _analyze_habit_history(
        self, recent_diaries: List[dict]
    ) -> dict[str, dict]:
        """
        分析近期日记中的习惯出现历史。

        Args:
            recent_diaries: 近期日记列表

        Returns:
            习惯类别 -> {count: 出现次数, positive: 正向次数, negative: 负向次数}
        """
        history: dict[str, dict] = {}

        for diary in recent_diaries:
            content = diary.get("content", "")
            if not content:
                continue

            for category, keywords in _HABIT_CATEGORIES.items():
                if any(kw in content for kw in keywords):
                    if category not in history:
                        history[category] = {
                            "count": 0, "positive": 0, "negative": 0
                        }
                    history[category]["count"] += 1

                    # 检测该条日记中该习惯的进度方向
                    if any(kw in content for kw in _POSITIVE_PROGRESS):
                        history[category]["positive"] += 1
                    if any(kw in content for kw in _NEGATIVE_PROGRESS):
                        history[category]["negative"] += 1

        return history

    def _detect_progress_signal(self, content: str) -> str:
        """
        检测当前日记中的进度信号。

        Args:
            content: 当前日记内容

        Returns:
            "positive" | "negative" | "neutral"
        """
        positive_count = sum(
            1 for kw in _POSITIVE_PROGRESS if kw in content
        )
        negative_count = sum(
            1 for kw in _NEGATIVE_PROGRESS if kw in content
        )

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _format_feedback(
        self,
        current_habits: List[str],
        habit_history: dict[str, dict],
        progress_signal: str,
        diary_content: str,
        diary_count: int,
        window_days: int,
    ) -> str:
        """
        格式化习惯追踪反馈。

        Args:
            current_habits: 当前日记中识别到的习惯
            habit_history: 近期习惯历史统计
            progress_signal: 当前进度信号
            diary_content: 当前日记内容
            diary_count: 近期日记总数
            window_days: 分析窗口天数

        Returns:
            结构化的习惯追踪反馈文本
        """
        lines: List[str] = []
        lines.append(f"🎯 习惯追踪报告（过去 {window_days} 天，{diary_count} 篇日记）：")

        # 当前日记中的习惯提及
        if current_habits:
            lines.append(f"\n📝 今日提及的习惯：{', '.join(current_habits)}")

            # 进度反馈
            if progress_signal == "positive":
                lines.append("  ✅ 检测到正向进度信号，继续保持！")
            elif progress_signal == "negative":
                lines.append("  ⚠️ 检测到中断/放弃信号，不要气馁，重新开始也是一种坚持。")

        # 习惯历史趋势
        if habit_history:
            lines.append("\n📈 近期习惯趋势：")
            sorted_habits = sorted(
                habit_history.items(),
                key=lambda x: x[1]["count"],
                reverse=True,
            )
            for category, stats in sorted_habits:
                count = stats["count"]
                positive = stats["positive"]
                negative = stats["negative"]

                # 计算坚持率
                if count > 0:
                    consistency = f"{count}/{diary_count} 篇日记提及"
                else:
                    consistency = "无记录"

                status_icon = "🟢" if positive > negative else (
                    "🔴" if negative > positive else "🟡"
                )
                lines.append(f"  {status_icon} {category}：{consistency}")

                if positive > 0:
                    lines.append(f"      正向记录 {positive} 次")
                if negative > 0:
                    lines.append(f"      中断记录 {negative} 次")
        elif not current_habits:
            lines.append("\n暂未检测到明确的习惯或目标提及。")
            lines.append("💡 提示：在日记中记录你的目标和习惯进度，我可以帮你追踪。")

        return "\n".join(lines)
