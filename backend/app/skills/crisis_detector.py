"""
CrisisDetectorSkill - 危机情绪检测 Skill
==========================================

识别极端负面情绪信号并触发升级响应协议，提供支持性资源。
复用 empathy_agent.py 中的关键词检测方法（_estimate_emotion_from_content）。

当检测到情绪分数低于 CRISIS_EMOTION_THRESHOLD (-0.7) 时，
触发危机响应路径，提供心理援助热线等支持性资源。

Requirements: 20.3
"""

import logging

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 极端负面情绪阈值（与 empathy_agent.py 保持一致）
CRISIS_EMOTION_THRESHOLD = -0.7

# 极端负面关键词（权重高）
_SEVERE_NEGATIVE_KEYWORDS = (
    "想死", "不想活", "自杀", "结束生命", "活着没意思",
    "绝望", "崩溃", "撑不下去", "没有希望", "生不如死",
    "伤害自己", "自残", "割腕", "跳楼",
)

# 一般负面关键词
_NEGATIVE_KEYWORDS = (
    "难过", "痛苦", "焦虑", "抑郁", "孤独", "害怕",
    "愤怒", "失望", "无助", "悲伤", "压抑", "烦躁",
    "失眠", "哭", "崩溃", "受不了", "太累了",
)

# 危机响应支持资源
CRISIS_RESOURCES = (
    "如果你正在经历极度痛苦，请记住你并不孤单。"
    "以下资源可以提供帮助：\n"
    "• 全国心理援助热线：400-161-9995\n"
    "• 北京心理危机研究与干预中心：010-82951332\n"
    "• 生命热线：400-821-1215\n"
    "请不要独自承受，寻求专业帮助是勇敢的选择。"
)


def _estimate_emotion_from_content(content: str) -> float:
    """
    基于日记内容的关键词快速估算情绪分数。

    与 empathy_agent.py 中的同名函数逻辑一致。
    返回值范围 [-1.0, 1.0]，负值表示负面情绪。
    """
    if not content:
        return 0.0

    score = 0.0

    for word in _SEVERE_NEGATIVE_KEYWORDS:
        if word in content:
            score -= 0.4

    for word in _NEGATIVE_KEYWORDS:
        if word in content:
            score -= 0.15

    # 正面关键词（用于平衡）
    positive_keywords = (
        "开心", "快乐", "幸福", "感恩", "满足", "期待",
        "兴奋", "温暖", "感动", "自豪", "放松", "愉快",
    )
    for word in positive_keywords:
        if word in content:
            score += 0.15

    return max(-1.0, min(1.0, score))


class CrisisDetectorSkill(BaseSkill):
    """
    危机情绪检测 Skill。

    识别极端负面情绪信号（情绪分数 < -0.7），触发升级响应协议。
    提供心理援助热线等支持性资源，避免使用轻视性语言。

    Requirements: 20.3
    """

    metadata = SkillMetadata(
        name="crisis_detector",
        description="识别极端负面情绪信号并触发升级响应协议，提供支持性资源",
        category="analysis",
        token_cost_estimate=50,
        requires_db=False,
        requires_network=False,
        priority=2.0,  # 高优先级，危机检测应优先执行
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行危机情绪检测。

        分析日记内容中的情绪信号，当检测到极端负面情绪时
        返回危机响应文本（包含支持性资源）。

        context 需包含:
            - diary_content: str (日记内容)
            - user_id: int (用户 ID)

        Returns:
            危机检测结果文本。若检测到危机则包含支持资源，否则返回安全状态描述。
        """
        diary_content = context.get("diary_content", "")
        user_id = context.get("user_id")

        if not diary_content:
            return "未检测到危机信号。"

        # 估算情绪分数
        emotion_score = _estimate_emotion_from_content(diary_content)

        # 检测是否触发危机阈值
        is_crisis = emotion_score < CRISIS_EMOTION_THRESHOLD

        if is_crisis:
            logger.warning(
                "CrisisDetectorSkill 检测到极端负面情绪 "
                "(score=%.2f, threshold=%.2f, user_id=%s)",
                emotion_score, CRISIS_EMOTION_THRESHOLD, user_id,
            )

            # 识别触发的具体关键词
            triggered_severe = [
                w for w in _SEVERE_NEGATIVE_KEYWORDS if w in diary_content
            ]
            triggered_negative = [
                w for w in _NEGATIVE_KEYWORDS if w in diary_content
            ]

            # 构建危机响应
            response_parts = [
                f"⚠️ 危机情绪检测触发（情绪分数: {emotion_score:.2f}）",
            ]

            if triggered_severe:
                response_parts.append(
                    f"检测到严重负面信号关键词: {', '.join(triggered_severe)}"
                )
            if triggered_negative:
                response_parts.append(
                    f"检测到负面情绪关键词: {', '.join(triggered_negative[:5])}"
                )

            response_parts.append("")
            response_parts.append("【升级响应协议已触发】")
            response_parts.append(CRISIS_RESOURCES)

            return "\n".join(response_parts)

        # 非危机状态
        logger.debug(
            "CrisisDetectorSkill 未检测到危机 (score=%.2f, user_id=%s)",
            emotion_score, user_id,
        )
        return f"情绪状态正常（情绪分数: {emotion_score:.2f}），未检测到危机信号。"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：

        危机检测器应在以下情况高概率激活：
        - 包含严重负面关键词: 1.0 (必须激活)
        - emotional_support 意图: 0.8 (情感支持场景需要检测)
        - 包含一般负面关键词 >= 3 个: 0.7
        - 包含一般负面关键词 1-2 个: 0.4
        - 其他: 0.2 (保持基础监控)
        """
        # 包含严重负面关键词时必须激活
        if any(kw in diary_content for kw in _SEVERE_NEGATIVE_KEYWORDS):
            return 1.0

        # emotional_support 意图时高概率激活
        if intent == "emotional_support":
            return 0.8

        # 统计一般负面关键词数量
        negative_count = sum(
            1 for kw in _NEGATIVE_KEYWORDS if kw in diary_content
        )
        if negative_count >= 3:
            return 0.7
        if negative_count >= 1:
            return 0.4

        # 保持基础监控
        return 0.2
