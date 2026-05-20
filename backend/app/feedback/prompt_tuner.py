"""
PromptTuner — 动态 Prompt 构建器
=================================

基于用户学习到的偏好构建动态 Prompt 片段，注入到 Empathy_Agent 和 Insight_Agent 的系统提示中。

核心功能：
1. 从 StylePreference 表读取 Thompson Sampling 参数，采样选择最优风格
2. 构建动态 Prompt 片段：response_length（短/中/长）、style、directness（0.0-1.0）
3. 偏好变化下次请求立即生效（每次请求实时读取数据库）
4. 新用户默认偏好：中等长度、共情型风格、0.5 直接度

Requirements: 13.1, 13.2, 13.3, 13.4
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.style_preference import StylePreference

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量与类型定义                                                 ║
# ╚══════════════════════════════════════════════════════════════╝

class ResponseLength(str, Enum):
    """回应长度偏好。"""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class AgentType(str, Enum):
    """支持注入动态 Prompt 的 Agent 类型。"""
    EMPATHY = "empathy"
    INSIGHT = "insight"


# Thompson Sampling 支持的风格列表
SUPPORTED_STYLES = ["empathetic", "practical", "philosophical", "humorous"]

# 默认偏好向量（新用户或参数加载失败时使用）
DEFAULT_STYLE = "empathetic"
DEFAULT_RESPONSE_LENGTH = ResponseLength.MEDIUM
DEFAULT_DIRECTNESS = 0.5


@dataclass
class UserPreference:
    """
    用户偏好向量，由 PromptTuner 从数据库实时构建。

    Attributes:
        response_length: 回应长度偏好（短/中/长）
        style: 由 Thompson Sampling 选择的回应风格
        directness: 直接程度 0.0（委婉）到 1.0（直接）
    """
    response_length: ResponseLength
    style: str
    directness: float


# ╔══════════════════════════════════════════════════════════════╗
# ║  风格描述映射                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

# 各风格在 Empathy Agent 中的提示描述
_EMPATHY_STYLE_PROMPTS = {
    "empathetic": "温暖共情、理解接纳，让用户感受到被理解和支持。用柔和的语言确认用户的情绪。",
    "practical": "务实关怀、在表达理解的同时给出具体可操作的建议。语言简洁有力。",
    "philosophical": "富有哲思、引导用户从更宏观的角度看待当下经历，同时保持温暖和理解。",
    "humorous": "轻松幽默、用温和的方式化解情绪紧张，但绝不轻视用户的感受。",
}

# 各风格在 Insight Agent 中的提示描述
_INSIGHT_STYLE_PROMPTS = {
    "empathetic": "在分析模式和趋势时，先共情再给出洞察。语言温暖，建议具有关怀感。",
    "practical": "直接指出模式和趋势，给出具体可执行的行动建议。数据驱动，结论明确。",
    "philosophical": "从更深层的角度解读行为模式，引导用户思考背后的动机和价值观。",
    "humorous": "用轻松的方式呈现分析结果，让洞察更容易被接受。但保持专业性。",
}

# 回应长度的提示描述
_LENGTH_PROMPTS = {
    ResponseLength.SHORT: "请保持回应简洁精炼，控制在 50-100 字以内。直击要点，不做过多展开。",
    ResponseLength.MEDIUM: "请将回应控制在适中长度（100-200 字），平衡深度和简洁。",
    ResponseLength.LONG: "可以适当展开回应（200-350 字），提供更丰富的分析和建议。",
}

# 直接度的提示描述
_DIRECTNESS_PROMPTS = {
    "low": "语言风格偏委婉含蓄，多用引导性提问而非直接陈述，给用户留出自我反思的空间。",
    "medium": "语言风格适中，在温和表达和直接建议之间取得平衡。",
    "high": "语言风格偏直接坦率，清晰指出观察到的问题和建议，不绕弯子。",
}


# ╔══════════════════════════════════════════════════════════════╗
# ║  Thompson Sampling 采样逻辑                                    ║
# ╚══════════════════════════════════════════════════════════════╝

def _sample_style_from_preferences(preferences: list[StylePreference]) -> str:
    """
    使用 Thompson Sampling 从用户的风格偏好中采样选择最优风格。

    对每种风格的 Beta(alpha, beta) 分布采样，选择采样值最高的风格。

    Args:
        preferences: 用户的 StylePreference 记录列表

    Returns:
        选中的风格名称

    Requirements: 12.2
    """
    if not preferences:
        return DEFAULT_STYLE

    # 构建风格 -> (alpha, beta) 映射
    style_params = {}
    for pref in preferences:
        style_params[pref.style] = (pref.alpha, pref.beta)

    # 确保所有支持的风格都有参数（新用户可能只有部分记录）
    for style in SUPPORTED_STYLES:
        if style not in style_params:
            style_params[style] = (1.0, 1.0)  # 均匀先验

    # Thompson Sampling：从每种风格的 Beta 分布采样
    best_style = DEFAULT_STYLE
    best_sample = -1.0

    for style, (alpha, beta) in style_params.items():
        sample = np.random.beta(alpha, beta)
        if sample > best_sample:
            best_sample = sample
            best_style = style

    return best_style


def _infer_response_length(preferences: list[StylePreference]) -> ResponseLength:
    """
    根据用户反馈历史推断回应长度偏好。

    逻辑：
    - 如果用户对某种风格的正向反馈（alpha）远大于负向反馈（beta），
      说明用户对当前长度满意，保持中等。
    - 如果总体 beta 较高（负向反馈多），可能需要调整长度。
    - 新用户默认中等长度。

    当前实现使用简单启发式，后续可扩展为独立的 Thompson Sampling 维度。

    Returns:
        ResponseLength 枚举值
    """
    if not preferences:
        return DEFAULT_RESPONSE_LENGTH

    # 计算总体正负反馈比
    total_alpha = sum(p.alpha for p in preferences)
    total_beta = sum(p.beta for p in preferences)

    # 新用户（几乎没有反馈）使用默认值
    total_feedback = total_alpha + total_beta - 2 * len(preferences)  # 减去初始先验
    if total_feedback < 5:
        return DEFAULT_RESPONSE_LENGTH

    # 正向反馈占比高 → 用户满意当前设置，保持中等
    # 负向反馈占比高 → 可能需要调整（但方向不确定，保持中等）
    # 这里保持简单：默认中等，后续可通过专门的 length 反馈维度优化
    return DEFAULT_RESPONSE_LENGTH


def _infer_directness(preferences: list[StylePreference]) -> float:
    """
    根据用户偏好的风格推断直接度。

    逻辑：
    - practical 风格偏好高 → 直接度偏高
    - empathetic 风格偏好高 → 直接度偏低
    - philosophical 风格偏好高 → 直接度中等偏低
    - humorous 风格偏好高 → 直接度中等

    Returns:
        0.0-1.0 的直接度值
    """
    if not preferences:
        return DEFAULT_DIRECTNESS

    # 风格对应的直接度权重
    style_directness = {
        "empathetic": 0.3,
        "practical": 0.8,
        "philosophical": 0.4,
        "humorous": 0.5,
    }

    # 加权平均：用每种风格的 alpha/(alpha+beta) 作为权重
    weighted_sum = 0.0
    weight_total = 0.0

    for pref in preferences:
        if pref.style in style_directness:
            # alpha/(alpha+beta) 表示该风格的"成功率"估计
            success_rate = pref.alpha / (pref.alpha + pref.beta)
            directness_value = style_directness[pref.style]
            weighted_sum += success_rate * directness_value
            weight_total += success_rate

    if weight_total == 0:
        return DEFAULT_DIRECTNESS

    return round(min(1.0, max(0.0, weighted_sum / weight_total)), 2)


# ╔══════════════════════════════════════════════════════════════╗
# ║  PromptTuner 核心类                                            ║
# ╚══════════════════════════════════════════════════════════════╝

class PromptTuner:
    """
    动态 Prompt 构建器。

    每次分析请求时，从数据库实时读取用户的 StylePreference 参数，
    通过 Thompson Sampling 选择风格，构建动态 Prompt 片段注入到
    Empathy_Agent 和 Insight_Agent 的系统提示中。

    偏好变化下次请求立即生效（无缓存，每次实时查询）。

    Usage:
        tuner = PromptTuner(db_session)
        prompt_fragment = tuner.build_dynamic_prompt(user_id=1, agent_type="empathy")
        # 将 prompt_fragment 注入到 Agent 的系统提示中

    Requirements: 13.1, 13.2, 13.3, 13.4
    """

    def __init__(self, db: Session):
        """
        初始化 PromptTuner。

        Args:
            db: SQLAlchemy 数据库会话，用于查询 StylePreference 表
        """
        self._db = db

    def get_user_preference(self, user_id: int) -> UserPreference:
        """
        获取用户的当前偏好向量。

        从数据库实时读取 StylePreference 记录，通过 Thompson Sampling
        选择风格，推断长度和直接度偏好。

        新用户或参数加载失败时返回默认偏好向量。

        Args:
            user_id: 用户 ID

        Returns:
            UserPreference 偏好向量

        Requirements: 13.1, 13.3, 13.4
        """
        try:
            preferences = (
                self._db.query(StylePreference)
                .filter(StylePreference.user_id == user_id)
                .all()
            )

            if not preferences:
                # 新用户：返回默认偏好
                logger.debug("用户 %d 无风格偏好记录，使用默认偏好", user_id)
                return UserPreference(
                    response_length=DEFAULT_RESPONSE_LENGTH,
                    style=DEFAULT_STYLE,
                    directness=DEFAULT_DIRECTNESS,
                )

            # Thompson Sampling 选择风格
            style = _sample_style_from_preferences(preferences)

            # 推断长度和直接度
            response_length = _infer_response_length(preferences)
            directness = _infer_directness(preferences)

            logger.debug(
                "用户 %d 偏好: style=%s, length=%s, directness=%.2f",
                user_id, style, response_length.value, directness,
            )

            return UserPreference(
                response_length=response_length,
                style=style,
                directness=directness,
            )

        except Exception as e:
            # 参数加载失败时使用默认偏好（Requirements: 23.4）
            logger.warning(
                "加载用户 %d 偏好失败，使用默认偏好: %s", user_id, e
            )
            return UserPreference(
                response_length=DEFAULT_RESPONSE_LENGTH,
                style=DEFAULT_STYLE,
                directness=DEFAULT_DIRECTNESS,
            )

    def build_dynamic_prompt(
        self,
        user_id: int,
        agent_type: str,
    ) -> str:
        """
        构建动态 Prompt 片段，用于注入到 Agent 系统提示中。

        每次调用实时从数据库读取偏好，确保偏好变化下次请求立即生效。

        Args:
            user_id: 用户 ID
            agent_type: Agent 类型，"empathy" 或 "insight"

        Returns:
            动态 Prompt 片段字符串，可直接拼接到系统提示中

        Requirements: 13.1, 13.2, 13.3
        """
        preference = self.get_user_preference(user_id)
        return self._format_prompt_fragment(preference, agent_type)

    def _format_prompt_fragment(
        self,
        preference: UserPreference,
        agent_type: str,
    ) -> str:
        """
        将偏好向量格式化为 Prompt 片段。

        Args:
            preference: 用户偏好向量
            agent_type: Agent 类型

        Returns:
            格式化的 Prompt 片段
        """
        parts = ["\n## 用户偏好适配指令\n"]

        # 1. 风格指令
        if agent_type == AgentType.EMPATHY:
            style_prompts = _EMPATHY_STYLE_PROMPTS
        elif agent_type == AgentType.INSIGHT:
            style_prompts = _INSIGHT_STYLE_PROMPTS
        else:
            style_prompts = _EMPATHY_STYLE_PROMPTS

        style_desc = style_prompts.get(
            preference.style,
            style_prompts[DEFAULT_STYLE],
        )
        parts.append(f"### 回应风格\n{style_desc}")

        # 2. 长度指令
        length_desc = _LENGTH_PROMPTS.get(
            preference.response_length,
            _LENGTH_PROMPTS[DEFAULT_RESPONSE_LENGTH],
        )
        parts.append(f"\n### 回应长度\n{length_desc}")

        # 3. 直接度指令
        directness_level = self._directness_to_level(preference.directness)
        directness_desc = _DIRECTNESS_PROMPTS.get(
            directness_level,
            _DIRECTNESS_PROMPTS["medium"],
        )
        parts.append(f"\n### 表达直接度\n{directness_desc}")

        return "\n".join(parts)

    @staticmethod
    def _directness_to_level(directness: float) -> str:
        """
        将 0.0-1.0 的直接度数值映射为描述级别。

        Args:
            directness: 0.0-1.0 的直接度值

        Returns:
            "low" | "medium" | "high"
        """
        if directness < 0.35:
            return "low"
        elif directness > 0.65:
            return "high"
        else:
            return "medium"


# ╔══════════════════════════════════════════════════════════════╗
# ║  便捷函数                                                      ║
# ╚══════════════════════════════════════════════════════════════╝

def build_dynamic_prompt_for_agent(
    db: Session,
    user_id: int,
    agent_type: str,
) -> str:
    """
    便捷函数：为指定 Agent 构建动态 Prompt 片段。

    这是 PromptTuner 的简化调用入口，适合在 Agent 节点函数中直接使用。

    Args:
        db: 数据库会话
        user_id: 用户 ID
        agent_type: "empathy" 或 "insight"

    Returns:
        动态 Prompt 片段字符串

    Usage:
        from app.feedback.prompt_tuner import build_dynamic_prompt_for_agent
        prompt_fragment = build_dynamic_prompt_for_agent(db, user_id, "empathy")
        system_prompt = base_prompt + prompt_fragment

    Requirements: 13.1, 13.2
    """
    tuner = PromptTuner(db)
    return tuner.build_dynamic_prompt(user_id, agent_type)


def get_default_preference() -> UserPreference:
    """
    获取默认偏好向量（新用户或降级时使用）。

    Returns:
        默认 UserPreference

    Requirements: 13.4
    """
    return UserPreference(
        response_length=DEFAULT_RESPONSE_LENGTH,
        style=DEFAULT_STYLE,
        directness=DEFAULT_DIRECTNESS,
    )


__all__ = [
    "PromptTuner",
    "UserPreference",
    "ResponseLength",
    "AgentType",
    "build_dynamic_prompt_for_agent",
    "get_default_preference",
    "SUPPORTED_STYLES",
    "DEFAULT_STYLE",
    "DEFAULT_RESPONSE_LENGTH",
    "DEFAULT_DIRECTNESS",
]
