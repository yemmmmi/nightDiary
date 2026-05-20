"""
IntentClassifier — 两级意图分类器
==================================

替代 ai_service.py 中的 _TEMPORAL_KEYWORDS 硬编码关键词匹配逻辑。

架构：
┌─────────────────────────────────────────────────┐
│                 IntentClassifier                  │
├─────────────────────────────────────────────────┤
│  Layer 1: Rule-based (高置信度场景)               │
│  - 显式时间回溯词组合 → need_retrieval            │
│  - 明确天气相关表达 → need_weather                │
│  - 强烈情感/复杂反思 → need_analysis              │
│  - 置信度 > 0.9 时直接返回，零 LLM Token 消耗     │
├─────────────────────────────────────────────────┤
│  Layer 2: LLM-based (模糊场景)                    │
│  - 规则层置信度 <= 0.9 时调用 LLM                 │
│  - 结构化输出 IntentResult                        │
│  - 单次 LLM 调用完成分类                          │
└─────────────────────────────────────────────────┘

Requirements: 15.1, 15.2, 15.3, 15.5
"""

import logging
import re
from typing import Optional

from langchain_openai import ChatOpenAI

from app.schemas.memory import IntentResult

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  规则层关键词与模式定义                                        ║
# ╚══════════════════════════════════════════════════════════════╝

# 时间回溯关键词（高权重 — 强烈暗示需要检索历史日记）
_TEMPORAL_STRONG = (
    "昨天", "前天", "上周", "上个月", "去年", "前几天", "前段时间",
    "那天", "那时", "那次", "上次", "曾经",
)

# 时间回溯关键词（中权重 — 暗示重复/延续模式）
_TEMPORAL_MEDIUM = (
    "又", "还是", "老是", "总是", "每次", "再次", "重复",
    "一直", "和之前一样", "跟上次", "像上回",
)

# 时间回溯短语（组合词，高置信度）
_TEMPORAL_PHRASES = (
    "之前写过", "以前提到", "上次说", "之前也是",
    "和前几天一样", "跟上次一样", "像上回一样",
)

# 天气相关关键词
_WEATHER_KEYWORDS = (
    "天气", "气温", "下雨", "下雪", "阴天", "晴天", "大风",
    "闷热", "寒冷", "潮湿", "雾霾", "温度",
)

# 强烈情感表达（暗示需要深度分析）
_STRONG_EMOTION_PATTERNS = (
    "崩溃", "绝望", "痛苦", "焦虑", "抑郁", "失眠",
    "不想活", "没意思", "受不了", "快疯了", "撑不住",
    "太难了", "好累", "心碎", "无助", "恐惧",
)

# 反思/分析关键词（暗示需要洞察分析）
_ANALYSIS_KEYWORDS = (
    "为什么", "怎么办", "该怎样", "如何改变", "规律",
    "总结", "回顾", "反思", "复盘", "模式",
    "习惯", "进步", "目标", "计划",
)

# 纯记录信号词（高置信度判断为 pure_record）
_PURE_RECORD_SIGNALS = (
    "今天吃了", "今天去了", "今天看了", "今天做了",
    "记录一下", "流水账", "日常",
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  IntentClassifier 类                                          ║
# ╚══════════════════════════════════════════════════════════════╝

class IntentClassifier:
    """
    两级意图分类器：规则层(高置信度) + LLM 层(模糊场景)。

    - 规则层通过关键词组合和模式匹配快速分类，置信度 > 0.9 时跳过 LLM
    - LLM 层处理规则层无法高置信度判断的模糊场景
    """

    CONFIDENCE_THRESHOLD = 0.9

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        初始化分类器。

        :param llm: LLM 实例，用于模糊场景的 LLM 层分类。为 None 时仅使用规则层。
        """
        self._llm = llm

    def classify(self, content: str) -> IntentResult:
        """
        对日记内容进行意图分类。

        流程：
        1. 规则层快速判断 → 置信度 > 0.9 则直接返回
        2. 否则调用 LLM 层进行精细分类

        :param content: 日记文本内容
        :return: IntentResult 包含 need_retrieval, need_weather, need_analysis, confidence, intent_category
        """
        if not content or not content.strip():
            return IntentResult(
                need_retrieval=False,
                need_weather=False,
                need_analysis=False,
                confidence=1.0,
                intent_category="pure_record",
            )

        # Layer 1: 规则层
        rule_result = self._rule_classify(content)
        if rule_result.confidence > self.CONFIDENCE_THRESHOLD:
            logger.debug(
                "IntentClassifier 规则层命中: category=%s, confidence=%.2f",
                rule_result.intent_category, rule_result.confidence,
            )
            return rule_result

        # Layer 2: LLM 层
        if self._llm is not None:
            try:
                llm_result = self._llm_classify(content, rule_result)
                logger.debug(
                    "IntentClassifier LLM 层: category=%s, confidence=%.2f",
                    llm_result.intent_category, llm_result.confidence,
                )
                return llm_result
            except Exception as exc:
                logger.warning("IntentClassifier LLM 层调用失败，回退规则层结果: %s", exc)
                return rule_result

        # 无 LLM 可用时返回规则层结果
        return rule_result

    # ──────────────────────────────────────────────────────────
    # Layer 1: 规则层
    # ──────────────────────────────────────────────────────────

    def _rule_classify(self, content: str) -> IntentResult:
        """
        基于规则的快速分类。

        评分逻辑：
        - 匹配强时间回溯关键词 → 高分 retrieval 信号
        - 匹配天气关键词 → weather 信号
        - 匹配强烈情感/分析关键词 → analysis 信号
        - 综合各维度分数确定 intent_category 和 confidence
        """
        need_retrieval = False
        need_weather = False
        need_analysis = False
        confidence = 0.5  # 默认中等置信度

        retrieval_score = 0.0
        weather_score = 0.0
        analysis_score = 0.0

        # --- 检测时间回溯信号 ---
        # 短语匹配（最高权重）
        for phrase in _TEMPORAL_PHRASES:
            if phrase in content:
                retrieval_score = max(retrieval_score, 0.95)
                break

        # 强时间关键词
        strong_temporal_count = sum(1 for kw in _TEMPORAL_STRONG if kw in content)
        if strong_temporal_count >= 2:
            retrieval_score = max(retrieval_score, 0.95)
        elif strong_temporal_count == 1:
            retrieval_score = max(retrieval_score, 0.85)

        # 中等时间关键词
        medium_temporal_count = sum(1 for kw in _TEMPORAL_MEDIUM if kw in content)
        if medium_temporal_count >= 2:
            retrieval_score = max(retrieval_score, 0.80)
        elif medium_temporal_count == 1:
            retrieval_score = max(retrieval_score, 0.60)

        # --- 检测天气信号 ---
        weather_count = sum(1 for kw in _WEATHER_KEYWORDS if kw in content)
        if weather_count >= 2:
            weather_score = 0.95
        elif weather_count == 1:
            weather_score = 0.75

        # --- 检测分析/情感信号 ---
        emotion_count = sum(1 for kw in _STRONG_EMOTION_PATTERNS if kw in content)
        analysis_kw_count = sum(1 for kw in _ANALYSIS_KEYWORDS if kw in content)

        if emotion_count >= 2:
            analysis_score = max(analysis_score, 0.95)
        elif emotion_count == 1:
            analysis_score = max(analysis_score, 0.80)

        if analysis_kw_count >= 2:
            analysis_score = max(analysis_score, 0.92)
        elif analysis_kw_count == 1:
            analysis_score = max(analysis_score, 0.70)

        # --- 检测纯记录信号 ---
        pure_record_count = sum(1 for sig in _PURE_RECORD_SIGNALS if sig in content)
        is_short = len(content.strip()) < 50
        pure_record_score = 0.0
        if pure_record_count >= 1 and is_short:
            pure_record_score = 0.95
        elif pure_record_count >= 1:
            pure_record_score = 0.80
        elif is_short and retrieval_score < 0.5 and analysis_score < 0.5:
            pure_record_score = 0.75

        # --- 综合判断 ---
        need_retrieval = retrieval_score >= 0.75
        need_weather = weather_score >= 0.75
        need_analysis = analysis_score >= 0.75

        # 确定 intent_category 和 confidence
        max_score = max(retrieval_score, analysis_score, pure_record_score)

        if pure_record_score >= 0.9 and retrieval_score < 0.75 and analysis_score < 0.75:
            intent_category = "pure_record"
            confidence = pure_record_score
        elif retrieval_score >= 0.9 and analysis_score >= 0.9:
            intent_category = "retrospective_review"
            confidence = min(retrieval_score, analysis_score)
        elif retrieval_score >= 0.75 and analysis_score >= 0.75:
            intent_category = "retrospective_review"
            confidence = (retrieval_score + analysis_score) / 2
        elif analysis_score >= 0.9:
            intent_category = "emotional_support"
            confidence = analysis_score
        elif retrieval_score >= 0.9:
            intent_category = "retrospective_review"
            confidence = retrieval_score
        elif retrieval_score >= 0.75:
            intent_category = "retrospective_review"
            confidence = retrieval_score
        elif analysis_score >= 0.75:
            intent_category = "emotional_support"
            confidence = analysis_score
        else:
            # 模糊场景 — 低置信度，交给 LLM 层
            intent_category = "pure_record"
            confidence = max(pure_record_score, 0.5)

        return IntentResult(
            need_retrieval=need_retrieval,
            need_weather=need_weather,
            need_analysis=need_analysis,
            confidence=confidence,
            intent_category=intent_category,
        )

    # ──────────────────────────────────────────────────────────
    # Layer 2: LLM 层
    # ──────────────────────────────────────────────────────────

    _LLM_CLASSIFY_PROMPT = """你是一个日记意图分类器。请分析以下日记内容，判断用户的写作意图。

日记内容：{content}

请严格按以下 JSON 格式输出（不要输出其他内容）：
{{
  "intent_category": "pure_record|emotional_support|retrospective_review|habit_tracking",
  "need_retrieval": true/false,
  "need_weather": true/false,
  "need_analysis": true/false,
  "confidence": 0.0-1.0
}}

分类标准：
- pure_record: 纯粹记录日常，无特殊情感或回顾需求
- emotional_support: 表达强烈情绪，需要情感支持和安慰
- retrospective_review: 提及过去经历，想要回顾对比或复盘
- habit_tracking: 关注习惯、目标、行为模式的追踪

判断 need_retrieval: 内容是否提到过去的事件或想要查看历史
判断 need_weather: 内容是否与天气相关或需要天气上下文
判断 need_analysis: 内容是否需要深度情感/行为分析"""

    def _llm_classify(self, content: str, rule_hint: IntentResult) -> IntentResult:
        """
        调用 LLM 进行精细分类。

        :param content: 日记内容
        :param rule_hint: 规则层的初步判断，作为参考
        :return: IntentResult
        """
        import json

        prompt = self._LLM_CLASSIFY_PROMPT.format(content=content[:500])  # 截取前 500 字，控制 Token

        response = self._llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # 尝试解析 JSON 输出
        try:
            # 清理可能的 markdown 代码块包裹
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            data = json.loads(cleaned)

            return IntentResult(
                need_retrieval=bool(data.get("need_retrieval", rule_hint.need_retrieval)),
                need_weather=bool(data.get("need_weather", rule_hint.need_weather)),
                need_analysis=bool(data.get("need_analysis", rule_hint.need_analysis)),
                confidence=min(1.0, max(0.0, float(data.get("confidence", 0.7)))),
                intent_category=data.get("intent_category", rule_hint.intent_category),
            )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("LLM 分类输出解析失败，回退规则层结果: %s | 原始输出: %s", exc, response_text[:200])
            # 解析失败时，提升规则层置信度作为 fallback
            return IntentResult(
                need_retrieval=rule_hint.need_retrieval,
                need_weather=rule_hint.need_weather,
                need_analysis=rule_hint.need_analysis,
                confidence=max(rule_hint.confidence, 0.6),
                intent_category=rule_hint.intent_category,
            )
