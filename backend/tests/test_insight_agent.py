"""
Insight Agent 单元测试
======================

测试 Insight Agent 的核心逻辑：
- 情绪偏离检测
- 周报/月报类型检测
- 上下文摘要构建
- Worker 节点函数返回正确的部分状态更新
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.agents.insight_agent import (
    _build_context_summary,
    _detect_emotion_deviation,
    _detect_report_type,
    insight_agent,
    EMOTION_DEVIATION_THRESHOLD,
)
from app.schemas.memory import EmotionBaseline


# ╔══════════════════════════════════════════════════════════════╗
# ║  _detect_report_type 测试                                     ║
# ╚══════════════════════════════════════════════════════════════╝


class TestDetectReportType:
    """测试周报/月报类型检测。"""

    def test_weekly_keywords(self):
        assert _detect_report_type("帮我生成本周周报") == "weekly"
        assert _detect_report_type("这周的情绪总结") == "weekly"
        assert _detect_report_type("过去七天的回顾") == "weekly"
        assert _detect_report_type("一周总结") == "weekly"

    def test_monthly_keywords(self):
        assert _detect_report_type("帮我生成月报") == "monthly"
        assert _detect_report_type("这个月的情绪变化") == "monthly"
        assert _detect_report_type("本月总结") == "monthly"
        assert _detect_report_type("过去三十天的回顾") == "monthly"

    def test_monthly_takes_priority_over_weekly(self):
        # 月报关键词优先检测
        assert _detect_report_type("本月的一周总结") == "monthly"

    def test_no_report_keywords(self):
        assert _detect_report_type("今天心情不错") is None
        assert _detect_report_type("工作压力很大") is None
        assert _detect_report_type("") is None


# ╔══════════════════════════════════════════════════════════════╗
# ║  _detect_emotion_deviation 测试                               ║
# ╚══════════════════════════════════════════════════════════════╝


class TestDetectEmotionDeviation:
    """测试情绪偏离检测。"""

    def test_no_episodic_context_returns_none(self):
        baseline = EmotionBaseline(average_sentiment=0.0)
        result = _detect_emotion_deviation("今天很难过", baseline, [])
        assert result is None

    def test_significant_negative_deviation(self):
        baseline = EmotionBaseline(average_sentiment=0.3)
        # 多条负面情绪记忆
        episodic = [
            {"emotion": "焦虑", "importance": 0.8},
            {"emotion": "悲伤", "importance": 0.7},
            {"emotion": "沮丧", "importance": 0.9},
        ]
        result = _detect_emotion_deviation("今天很难过", baseline, episodic)
        assert result is not None
        assert result["direction"] == "lower"
        assert result["magnitude"] >= EMOTION_DEVIATION_THRESHOLD

    def test_significant_positive_deviation(self):
        baseline = EmotionBaseline(average_sentiment=-0.3)
        # 多条正面情绪记忆
        episodic = [
            {"emotion": "开心", "importance": 0.8},
            {"emotion": "满足", "importance": 0.7},
            {"emotion": "感恩", "importance": 0.9},
        ]
        result = _detect_emotion_deviation("今天很开心", baseline, episodic)
        assert result is not None
        assert result["direction"] == "higher"
        assert result["magnitude"] >= EMOTION_DEVIATION_THRESHOLD

    def test_no_significant_deviation(self):
        baseline = EmotionBaseline(average_sentiment=0.0)
        # 中性情绪
        episodic = [
            {"emotion": "平常", "importance": 0.5},
            {"emotion": "一般", "importance": 0.5},
        ]
        result = _detect_emotion_deviation("今天还行", baseline, episodic)
        assert result is None

    def test_mixed_emotions_no_deviation(self):
        baseline = EmotionBaseline(average_sentiment=0.0)
        # 正负混合，均值接近 0
        episodic = [
            {"emotion": "开心", "importance": 0.5},
            {"emotion": "焦虑", "importance": 0.5},
        ]
        result = _detect_emotion_deviation("今天有好有坏", baseline, episodic)
        assert result is None


# ╔══════════════════════════════════════════════════════════════╗
# ║  _build_context_summary 测试                                  ║
# ╚══════════════════════════════════════════════════════════════╝


class TestBuildContextSummary:
    """测试上下文摘要构建。"""

    def test_empty_context(self):
        result = _build_context_summary("", [], {})
        assert result == "（暂无历史上下文）"

    def test_with_retrieval_context(self):
        result = _build_context_summary("历史日记内容", [], {})
        assert "历史日记摘要" in result
        assert "历史日记内容" in result

    def test_with_episodic_context(self):
        episodic = [
            {"event": "和朋友聚餐", "emotion": "开心", "ai_suggestion": "保持社交"},
            {"event": "加班到很晚", "emotion": "疲惫", "ai_suggestion": "注意休息"},
        ]
        result = _build_context_summary("", episodic, {})
        assert "近期重要记忆" in result
        assert "和朋友聚餐" in result
        assert "开心" in result

    def test_with_long_term_profile(self):
        profile = {
            "recurring_topics": ["工作压力", "睡眠"],
            "personality_tags": ["内向", "敏感"],
            "emotion_baseline": {"dominant_emotion": "平静"},
        }
        result = _build_context_summary("", [], profile)
        assert "用户画像" in result
        assert "工作压力" in result
        assert "内向" in result
        assert "平静" in result

    def test_combined_context(self):
        episodic = [{"event": "考试", "emotion": "焦虑", "ai_suggestion": ""}]
        profile = {"recurring_topics": ["学习"]}
        result = _build_context_summary("检索结果", episodic, profile)
        assert "历史日记摘要" in result
        assert "近期重要记忆" in result
        assert "用户画像" in result


# ╔══════════════════════════════════════════════════════════════╗
# ║  insight_agent Worker 节点函数测试                              ║
# ╚══════════════════════════════════════════════════════════════╝


class TestInsightAgentNode:
    """测试 insight_agent Worker 节点函数。"""

    @patch("app.agents.insight_agent._build_llm")
    @patch("app.agents.insight_agent._query_domain_knowledge")
    def test_returns_insight_response(self, mock_domain, mock_llm):
        """测试正常情况下返回 insight_response 字段。"""
        mock_domain.return_value = ""
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(
            content="你最近的焦虑情绪与工作压力相关。建议：每天花10分钟做深呼吸练习。"
        )
        mock_llm.return_value = mock_llm_instance

        state = {
            "diary_content": "今天工作压力很大，感觉喘不过气来",
            "user_id": 1,
            "diary_nid": 100,
            "intent": "retrospective_review",
            "retrieval_context": "上周也提到了工作压力",
            "episodic_context": [
                {"event": "加班", "emotion": "疲惫", "importance": 0.7, "ai_suggestion": ""},
            ],
            "long_term_profile": {
                "emotion_baseline": {
                    "average_sentiment": 0.1,
                    "volatility": 0.3,
                    "dominant_emotion": "平静",
                },
                "recurring_topics": ["工作"],
            },
        }

        result = insight_agent(state)

        assert "insight_response" in result
        assert result["insight_response"] != ""
        mock_llm_instance.invoke.assert_called_once()

    @patch("app.agents.insight_agent._build_llm")
    @patch("app.agents.insight_agent._query_domain_knowledge")
    def test_report_mode_uses_report_prompt(self, mock_domain, mock_llm):
        """测试周报模式使用报告系统提示词。"""
        mock_domain.return_value = ""
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(
            content="📊 主导情绪：焦虑\n📌 关键事件：项目截止\n📈 趋势：上升\n💡 建议：..."
        )
        mock_llm.return_value = mock_llm_instance

        state = {
            "diary_content": "帮我生成本周周报",
            "user_id": 1,
            "diary_nid": 101,
            "intent": "retrospective_review",
            "retrieval_context": "",
            "episodic_context": [],
            "long_term_profile": {},
        }

        result = insight_agent(state)

        assert "insight_response" in result
        # 验证 LLM 被调用时使用了报告提示词
        call_args = mock_llm_instance.invoke.call_args[0][0]
        system_msg = call_args[0]
        assert "周报" in system_msg.content

    @patch("app.agents.insight_agent._build_llm")
    @patch("app.agents.insight_agent._query_domain_knowledge")
    def test_llm_failure_returns_empty_with_error(self, mock_domain, mock_llm):
        """测试 LLM 调用失败时返回空响应和错误信息。"""
        mock_domain.return_value = ""
        mock_llm.side_effect = RuntimeError("LLM_API_KEY 未配置")

        state = {
            "diary_content": "今天心情不好",
            "user_id": 1,
            "diary_nid": 102,
            "intent": "emotional_support",
            "retrieval_context": "",
            "episodic_context": [],
            "long_term_profile": {},
        }

        result = insight_agent(state)

        assert result["insight_response"] == ""
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "Insight Agent LLM 调用失败" in result["errors"][0]

    @patch("app.agents.insight_agent._build_llm")
    @patch("app.agents.insight_agent._query_domain_knowledge")
    def test_emotion_deviation_included_in_prompt(self, mock_domain, mock_llm):
        """测试情绪偏离信息被包含在 LLM 提示中。"""
        mock_domain.return_value = ""
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(content="分析结果")
        mock_llm.return_value = mock_llm_instance

        state = {
            "diary_content": "今天特别难过",
            "user_id": 1,
            "diary_nid": 103,
            "intent": "emotional_support",
            "retrieval_context": "",
            "episodic_context": [
                {"event": "失恋", "emotion": "悲伤", "importance": 0.9, "ai_suggestion": ""},
                {"event": "争吵", "emotion": "愤怒", "importance": 0.8, "ai_suggestion": ""},
                {"event": "失眠", "emotion": "焦虑", "importance": 0.7, "ai_suggestion": ""},
            ],
            "long_term_profile": {
                "emotion_baseline": {
                    "average_sentiment": 0.4,
                    "volatility": 0.2,
                    "dominant_emotion": "平静",
                },
            },
        }

        result = insight_agent(state)

        # 验证 LLM 调用中包含情绪偏离提醒
        call_args = mock_llm_instance.invoke.call_args[0][0]
        user_msg = call_args[1]
        assert "情绪偏离提醒" in user_msg.content
        assert "低于" in user_msg.content

    @patch("app.agents.insight_agent._build_llm")
    @patch("app.agents.insight_agent._query_domain_knowledge")
    def test_domain_knowledge_included(self, mock_domain, mock_llm):
        """测试领域知识被包含在 LLM 提示中。"""
        mock_domain.return_value = "【专业知识参考】\n认知行为疗法建议..."
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(content="分析结果")
        mock_llm.return_value = mock_llm_instance

        state = {
            "diary_content": "最近总是焦虑",
            "user_id": 1,
            "diary_nid": 104,
            "intent": "retrospective_review",
            "retrieval_context": "",
            "episodic_context": [],
            "long_term_profile": {},
        }

        result = insight_agent(state)

        # 验证领域知识被传递给 LLM
        call_args = mock_llm_instance.invoke.call_args[0][0]
        user_msg = call_args[1]
        assert "专业知识参考" in user_msg.content
        assert "认知行为疗法" in user_msg.content
