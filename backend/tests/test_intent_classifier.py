"""
IntentClassifier 单元测试
=========================

测试两级分类器的规则层和 LLM 层行为。
"""

import pytest
from unittest.mock import MagicMock, patch

from app.agents.intent_classifier import IntentClassifier
from app.schemas.memory import IntentResult


class TestRuleLayer:
    """规则层测试：高置信度场景无 LLM 调用。"""

    def setup_method(self):
        """每个测试方法前创建分类器（无 LLM）。"""
        self.classifier = IntentClassifier(llm=None)

    def test_empty_content_returns_pure_record(self):
        """空内容应返回 pure_record，置信度 1.0。"""
        result = self.classifier.classify("")
        assert result.intent_category == "pure_record"
        assert result.confidence == 1.0
        assert result.need_retrieval is False
        assert result.need_analysis is False

    def test_strong_temporal_phrase_triggers_retrieval(self):
        """显式时间回溯短语应触发 need_retrieval，高置信度。"""
        result = self.classifier.classify("之前写过类似的心情，感觉和那次一样低落")
        assert result.need_retrieval is True
        assert result.confidence > 0.9

    def test_multiple_strong_temporal_keywords(self):
        """多个强时间关键词应触发 retrieval。"""
        result = self.classifier.classify("昨天加班到很晚，前天也是这样")
        assert result.need_retrieval is True
        assert result.confidence > 0.9

    def test_single_strong_temporal_keyword_medium_confidence(self):
        """单个强时间关键词，中等置信度（不超过 0.9）。"""
        result = self.classifier.classify("昨天去了趟超市买了些日用品回来整理了一下房间")
        assert result.need_retrieval is True
        # 单个强关键词 score=0.85, 不超过阈值
        assert result.confidence <= 0.9

    def test_weather_keywords_trigger_need_weather(self):
        """天气关键词应触发 need_weather。"""
        result = self.classifier.classify("今天天气真好，阳光明媚，心情不错")
        assert result.need_weather is True

    def test_strong_emotion_triggers_analysis(self):
        """强烈情感表达应触发 need_analysis。"""
        result = self.classifier.classify("今天真的太累了，感觉快要崩溃了，焦虑得睡不着")
        assert result.need_analysis is True
        assert result.confidence > 0.9

    def test_analysis_keywords_trigger_analysis(self):
        """分析/反思关键词应触发 need_analysis。"""
        result = self.classifier.classify("为什么我总是无法坚持计划？需要好好反思一下")
        assert result.need_analysis is True
        assert result.confidence > 0.9

    def test_pure_record_short_daily(self):
        """纯日常短记录应分类为 pure_record。"""
        result = self.classifier.classify("今天吃了火锅")
        assert result.intent_category == "pure_record"
        assert result.confidence > 0.9
        assert result.need_retrieval is False
        assert result.need_analysis is False

    def test_retrospective_review_combined_signals(self):
        """同时包含回溯和分析信号应分类为 retrospective_review。"""
        result = self.classifier.classify("上次制定的目标为什么没有完成？需要总结一下规律")
        assert result.intent_category == "retrospective_review"
        assert result.need_retrieval is True
        assert result.need_analysis is True

    def test_result_structure_correct(self):
        """结果应为 IntentResult 实例，包含所有必要字段。"""
        result = self.classifier.classify("今天是普通的一天")
        assert isinstance(result, IntentResult)
        assert hasattr(result, "need_retrieval")
        assert hasattr(result, "need_weather")
        assert hasattr(result, "need_analysis")
        assert hasattr(result, "confidence")
        assert hasattr(result, "intent_category")
        assert 0.0 <= result.confidence <= 1.0


class TestLLMLayer:
    """LLM 层测试：模糊场景调用 LLM。"""

    def test_rule_high_confidence_skips_llm(self):
        """规则层置信度 > 0.9 时不调用 LLM。"""
        mock_llm = MagicMock()
        classifier = IntentClassifier(llm=mock_llm)

        # 强烈时间回溯短语 → 规则层高置信度
        result = classifier.classify("之前写过类似的情况，和那次感受很像")
        mock_llm.invoke.assert_not_called()
        assert result.confidence > 0.9

    def test_ambiguous_content_calls_llm(self):
        """模糊内容应调用 LLM 层。"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"intent_category": "emotional_support", "need_retrieval": false, "need_weather": false, "need_analysis": true, "confidence": 0.85}'
        mock_llm.invoke.return_value = mock_response

        classifier = IntentClassifier(llm=mock_llm)
        result = classifier.classify("工作中遇到了一些问题，不知道该不该跳槽")

        mock_llm.invoke.assert_called_once()
        assert result.intent_category == "emotional_support"
        assert result.need_analysis is True
        assert result.confidence == 0.85

    def test_llm_failure_falls_back_to_rule_result(self):
        """LLM 调用失败时回退到规则层结果。"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API timeout")

        classifier = IntentClassifier(llm=mock_llm)
        result = classifier.classify("最近状态一般般")

        # 应返回有效结果（规则层的低置信度结果）
        assert isinstance(result, IntentResult)
        assert result.confidence >= 0.0

    def test_llm_invalid_json_falls_back(self):
        """LLM 返回无效 JSON 时回退到规则层结果。"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "这是一篇关于情感的日记..."  # 非 JSON
        mock_llm.invoke.return_value = mock_response

        classifier = IntentClassifier(llm=mock_llm)
        result = classifier.classify("心情有些复杂，说不上来")

        assert isinstance(result, IntentResult)
        assert result.confidence >= 0.0

    def test_llm_response_with_markdown_code_block(self):
        """LLM 返回带 markdown 代码块包裹的 JSON 也能正确解析。"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '```json\n{"intent_category": "habit_tracking", "need_retrieval": true, "need_weather": false, "need_analysis": true, "confidence": 0.8}\n```'
        mock_llm.invoke.return_value = mock_response

        classifier = IntentClassifier(llm=mock_llm)
        result = classifier.classify("这周的运动计划完成情况如何")

        assert result.intent_category == "habit_tracking"
        assert result.need_retrieval is True
        assert result.need_analysis is True
