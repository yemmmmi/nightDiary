"""
记忆系统相关 Pydantic Schema
============================

数据结构：
- EpisodicEntry: Redis Sorted Set 中的情景记忆条目
- UserProfile: 长期记忆用户画像 JSON 结构
- IntentResult: 意图分类器输出结果
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class EpisodicEntry(BaseModel):
    """
    情景记忆条目。
    存储在 Redis Sorted Set 中，key 为 "memory:episodic:{user_id}"，score 为时间戳。
    """
    event: str  # 事件描述
    emotion: str  # 情感标签
    ai_suggestion: str  # AI 建议摘要
    user_feedback: str = "none"  # positive | negative | none
    timestamp: float  # Unix timestamp
    diary_nids: List[int] = []  # 关联日记 ID
    importance: float = Field(default=0.5, ge=0.0, le=1.0)  # 重要性评分


class EmotionBaseline(BaseModel):
    """情绪基线子结构。"""
    average_sentiment: float = 0.0  # 平均情感值
    volatility: float = 0.0  # 波动性
    dominant_emotion: str = "neutral"  # 主导情绪


class ImportantPerson(BaseModel):
    """重要人物子结构。"""
    name: str
    relation: str  # 关系
    sentiment: float = 0.0  # 情感倾向


class UserProfile(BaseModel):
    """
    长期记忆用户画像。
    以 JSON 形式存储在 User.long_term_profile 字段中。
    """
    personality_tags: List[str] = []  # 性格标签
    emotion_baseline: EmotionBaseline = Field(default_factory=EmotionBaseline)
    important_people: List[ImportantPerson] = []  # 重要人物
    recurring_topics: List[str] = []  # 反复出现的话题
    preferred_response_style: str = "empathetic"  # 偏好回应风格


class IntentResult(BaseModel):
    """
    意图分类器输出结果。
    两级分类器（规则层 + LLM 层）的统一输出格式。
    """
    need_retrieval: bool = False  # 是否需要检索历史日记
    need_weather: bool = False  # 是否需要天气信息
    need_analysis: bool = False  # 是否需要深度分析
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)  # 分类置信度
    intent_category: Optional[str] = None  # pure_record | emotional_support | retrospective_review | habit_tracking
