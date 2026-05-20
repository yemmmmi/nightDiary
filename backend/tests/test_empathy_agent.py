"""
Empathy Agent 单元测试
========================

测试 Empathy Agent 的核心逻辑：
- 情绪分数提取和估算
- 危机响应触发
- 情景记忆上下文格式化
- 回应长度控制
- LLM 不可用时的降级行为
- Domain Knowledge Store 查询降级

Requirements: 5.1, 5.2, 5.3, 5.4, 18.3
"""

from unittest.mock import patch, MagicMock

import pytest

from app.agents.empathy_agent import (
    _extract_emotion_score,
    _estimate_emotion_from_content,
    _format_episodic_context,
    _build_empathy_prompt,
    _generate_fallback_response,
    _query_domain_knowledge,
    empathy_agent_node,
    CRISIS_EMOTION_THRESHOLD,
    CRISIS_RESOURCES,
    RESPONSE_LENGTH,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  情绪分数提取测试                                              ║
# ╚══════════════════════════════════════════════════════════════╝

class TestExtractEmotionScore:
    """测试 _extract_emotion_score 函数。"""

    def test_extracts_from_profile(self):
        """应从 long_term_profile 中提取 average_sentiment。"""
        state = {
            "long_term_profile": {
                "emotion_baseline": {"average_sentiment": -0.3, "volatility": 0.2}
            }
        }
        assert _extract_emotion_score(state) == -0.3

    def test_returns_zero_when_no_profile(self):
        """无画像时应返回 0.0。"""
        state = {"long_term_profile": {}}
        assert _extract_emotion_score(state) == 0.0

    def test_returns_zero_when_profile_none(self):
        """画像为 None 时应返回 0.0。"""
        state = {"long_term_profile": None}
        assert _extract_emotion_score(state) == 0.0

    def test_returns_zero_when_no_baseline(self):
        """无 emotion_baseline 时应返回 0.0。"""
        state = {"long_term_profile": {"personality_tags": ["内向"]}}
        assert _extract_emotion_score(state) == 0.0


class TestEstimateEmotionFromContent:
    """测试 _estimate_emotion_from_content 函数。"""

    def test_severe_negative_keywords(self):
        """极端负面关键词应产生很低的分数。"""
        score = _estimate_emotion_from_content("我真的不想活了，太绝望了")
        assert score < CRISIS_EMOTION_THRESHOLD

    def test_moderate_negative(self):
        """一般负面关键词应产生负分但不一定触发危机。"""
        score = _estimate_emotion_from_content("今天有点难过")
        assert score < 0
        assert score > CRISIS_EMOTION_THRESHOLD

    def test_positive_content(self):
        """正面内容应产生正分。"""
        score = _estimate_emotion_from_content("今天很开心，感觉很幸福")
        assert score > 0

    def test_neutral_content(self):
        """中性内容应返回 0。"""
        score = _estimate_emotion_from_content("今天去超市买了菜")
        assert score == 0.0

    def test_empty_content(self):
        """空内容应返回 0。"""
        assert _estimate_emotion_from_content("") == 0.0

    def test_score_bounded(self):
        """分数应限制在 [-1.0, 1.0] 范围内。"""
        # 大量负面词
        content = "想死 不想活 自杀 绝望 崩溃 撑不下去 没有希望"
        score = _estimate_emotion_from_content(content)
        assert score >= -1.0
        assert score <= 1.0


# ╔══════════════════════════════════════════════════════════════╗
# ║  情景记忆格式化测试                                            ║
# ╚══════════════════════════════════════════════════════════════╝

class TestFormatEpisodicContext:
    """测试 _format_episodic_context 函数。"""

    def test_formats_entries(self):
        """应正确格式化情景记忆条目。"""
        entries = [
            {
                "event": "和朋友吵架",
                "emotion": "angry",
                "ai_suggestion": "试着冷静下来再沟通",
                "user_feedback": "positive",
            }
        ]
        result = _format_episodic_context(entries)
        assert "和朋友吵架" in result
        assert "angry" in result
        assert "试着冷静下来再沟通" in result

    def test_empty_entries(self):
        """空列表应返回空字符串。"""
        assert _format_episodic_context([]) == ""

    def test_max_five_entries(self):
        """最多使用 5 条记忆。"""
        entries = [{"event": f"事件{i}", "emotion": "neutral"} for i in range(10)]
        result = _format_episodic_context(entries)
        # 应只包含前 5 条
        assert "事件0" in result
        assert "事件4" in result
        assert "事件5" not in result

    def test_skips_empty_fields(self):
        """空字段不应出现在输出中。"""
        entries = [{"event": "", "emotion": "", "ai_suggestion": ""}]
        result = _format_episodic_context(entries)
        assert result == ""


# ╔══════════════════════════════════════════════════════════════╗
# ║  Prompt 构建测试                                              ║
# ╚══════════════════════════════════════════════════════════════╝

class TestBuildEmpathyPrompt:
    """测试 _build_empathy_prompt 函数。"""

    def test_includes_length_constraint(self):
        """Prompt 应包含回应长度约束。"""
        prompt = _build_empathy_prompt(
            diary_content="今天很累",
            intent="pure_record",
            preferred_style="empathetic",
            episodic_context="",
            domain_knowledge="",
            is_crisis=False,
        )
        assert "50" in prompt
        assert "150" in prompt

    def test_emotional_support_length(self):
        """emotional_support 意图应使用 100-300 长度。"""
        prompt = _build_empathy_prompt(
            diary_content="今天很难过",
            intent="emotional_support",
            preferred_style="empathetic",
            episodic_context="",
            domain_knowledge="",
            is_crisis=False,
        )
        assert "100" in prompt
        assert "300" in prompt

    def test_crisis_mode_instructions(self):
        """危机模式应包含特殊指导。"""
        prompt = _build_empathy_prompt(
            diary_content="不想活了",
            intent="emotional_support",
            preferred_style="empathetic",
            episodic_context="",
            domain_knowledge="",
            is_crisis=True,
        )
        assert "危机响应模式" in prompt
        assert "轻视性语言" in prompt

    def test_includes_episodic_context(self):
        """有情景记忆时应包含在 Prompt 中。"""
        prompt = _build_empathy_prompt(
            diary_content="今天又加班了",
            intent="emotional_support",
            preferred_style="empathetic",
            episodic_context="• 事件：上周也加班到很晚",
            domain_knowledge="",
            is_crisis=False,
        )
        assert "上周也加班到很晚" in prompt
        assert "之前的交互记忆" in prompt

    def test_includes_domain_knowledge(self):
        """有领域知识时应包含在 Prompt 中。"""
        prompt = _build_empathy_prompt(
            diary_content="焦虑",
            intent="emotional_support",
            preferred_style="empathetic",
            episodic_context="",
            domain_knowledge="[cbt/认知重构] 识别自动化思维并挑战其合理性",
            is_crisis=False,
        )
        assert "认知重构" in prompt
        assert "专业知识参考" in prompt

    def test_style_mapping(self):
        """不同风格应产生不同的指导文本。"""
        prompt_practical = _build_empathy_prompt(
            diary_content="test",
            intent="pure_record",
            preferred_style="practical",
            episodic_context="",
            domain_knowledge="",
            is_crisis=False,
        )
        assert "务实" in prompt_practical

        prompt_humorous = _build_empathy_prompt(
            diary_content="test",
            intent="pure_record",
            preferred_style="humorous",
            episodic_context="",
            domain_knowledge="",
            is_crisis=False,
        )
        assert "幽默" in prompt_humorous


# ╔══════════════════════════════════════════════════════════════╗
# ║  降级回应测试                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

class TestFallbackResponse:
    """测试 _generate_fallback_response 函数。"""

    def test_crisis_fallback_includes_resources(self):
        """危机降级回应应包含支持资源。"""
        response = _generate_fallback_response("emotional_support", is_crisis=True)
        assert "400-161-9995" in response
        assert "痛苦" in response

    def test_pure_record_fallback(self):
        """pure_record 降级回应应简短。"""
        response = _generate_fallback_response("pure_record", is_crisis=False)
        assert len(response) > 0
        assert len(response) <= 200

    def test_emotional_support_fallback(self):
        """emotional_support 降级回应应较长。"""
        response = _generate_fallback_response("emotional_support", is_crisis=False)
        assert len(response) > 20

    def test_unknown_intent_uses_default(self):
        """未知意图应使用默认回应。"""
        response = _generate_fallback_response("unknown_intent", is_crisis=False)
        assert len(response) > 0


# ╔══════════════════════════════════════════════════════════════╗
# ║  Domain Knowledge Store 查询测试                              ║
# ╚══════════════════════════════════════════════════════════════╝

class TestQueryDomainKnowledge:
    """测试 _query_domain_knowledge 函数。"""

    @patch("chromadb.PersistentClient")
    def test_returns_empty_when_collection_not_exists(self, mock_client_cls):
        """集合不存在时应返回空字符串。"""
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Collection not found")
        mock_client_cls.return_value = mock_client

        result = _query_domain_knowledge("焦虑")
        assert result == ""

    @patch("chromadb.PersistentClient")
    def test_returns_formatted_knowledge(self, mock_client_cls):
        """应返回格式化的知识条目。"""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "documents": [["深呼吸可以激活副交感神经系统"]],
            "metadatas": [[{"category": "mindfulness", "topic": "呼吸练习"}]],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client

        result = _query_domain_knowledge("焦虑怎么办")
        assert "深呼吸" in result
        assert "mindfulness" in result

    @patch("chromadb.PersistentClient")
    def test_graceful_degradation_on_error(self, mock_client_cls):
        """任何异常都应优雅降级返回空字符串。"""
        mock_client_cls.side_effect = Exception("Connection error")
        result = _query_domain_knowledge("test")
        assert result == ""


# ╔══════════════════════════════════════════════════════════════╗
# ║  Empathy Agent 节点函数集成测试                                ║
# ╚══════════════════════════════════════════════════════════════╝

class TestEmpathyAgentNode:
    """测试 empathy_agent_node 主函数。"""

    def _make_state(self, **overrides) -> dict:
        """创建测试用 MultiAgentState。"""
        state = {
            "diary_content": "今天工作很累，但还是坚持完成了任务。",
            "user_id": 1,
            "diary_nid": 100,
            "intent": "pure_record",
            "token_budget": 600,
            "activated_agents": ["empathy"],
            "episodic_context": [],
            "long_term_profile": {
                "preferred_response_style": "empathetic",
                "emotion_baseline": {"average_sentiment": 0.0},
            },
            "compressed_history": "",
            "retrieval_context": "",
            "empathy_response": "",
            "insight_response": "",
            "final_response": "",
            "total_tokens_used": 0,
            "agent_mode": "multi_agent",
            "thk_log": "",
            "errors": [],
        }
        state.update(overrides)
        return state

    @patch("app.agents.empathy_agent._query_domain_knowledge")
    @patch("app.agents.empathy_agent._get_llm")
    def test_returns_empathy_response(self, mock_llm, mock_knowledge):
        """应返回包含 empathy_response 的字典。"""
        mock_knowledge.return_value = ""
        mock_response = MagicMock()
        mock_response.content = "感谢你今天的坚持，辛苦了。"

        # Mock the LLM so that prompt | llm returns a chain whose invoke returns mock_response
        mock_llm_instance = MagicMock()
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_llm_instance.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.return_value = mock_llm_instance

        with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_from:
            mock_prompt_obj = MagicMock()
            mock_prompt_obj.__or__ = MagicMock(return_value=mock_chain)
            mock_from.return_value = mock_prompt_obj

            state = self._make_state()
            result = empathy_agent_node(state)

            assert "empathy_response" in result
            assert result["empathy_response"] == "感谢你今天的坚持，辛苦了。"

    @patch("app.agents.empathy_agent._query_domain_knowledge")
    @patch("app.agents.empathy_agent._get_llm")
    def test_crisis_appends_resources(self, mock_llm, mock_knowledge):
        """危机模式应在回应后附加支持资源。"""
        mock_knowledge.return_value = ""
        mock_response = MagicMock()
        mock_response.content = "我能感受到你现在的痛苦。"

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_llm_instance = MagicMock()
        mock_llm_instance.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.return_value = mock_llm_instance

        with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_from:
            mock_prompt_obj = MagicMock()
            mock_prompt_obj.__or__ = MagicMock(return_value=mock_chain)
            mock_from.return_value = mock_prompt_obj

            state = self._make_state(
                diary_content="我真的不想活了，太绝望了，想死",
                intent="emotional_support",
            )
            result = empathy_agent_node(state)

            assert CRISIS_RESOURCES in result["empathy_response"]
            assert "我能感受到你现在的痛苦。" in result["empathy_response"]

    @patch("app.agents.empathy_agent._query_domain_knowledge")
    @patch("app.agents.empathy_agent._get_llm")
    def test_uses_preferred_style(self, mock_llm, mock_knowledge):
        """应使用用户偏好的回应风格。"""
        mock_knowledge.return_value = ""
        mock_response = MagicMock()
        mock_response.content = "务实的回应"

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_llm_instance = MagicMock()
        mock_llm_instance.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.return_value = mock_llm_instance

        with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_from:
            mock_prompt_obj = MagicMock()
            mock_prompt_obj.__or__ = MagicMock(return_value=mock_chain)
            mock_from.return_value = mock_prompt_obj

            state = self._make_state(
                long_term_profile={"preferred_response_style": "practical"},
            )
            result = empathy_agent_node(state)
            assert "empathy_response" in result

    @patch("app.agents.empathy_agent._get_llm")
    def test_fallback_on_llm_failure(self, mock_llm):
        """LLM 失败时应返回降级回应。"""
        mock_llm.side_effect = RuntimeError("API Key 未配置")

        state = self._make_state()
        result = empathy_agent_node(state)

        assert "empathy_response" in result
        assert len(result["empathy_response"]) > 0
        # 降级回应不应为空
        assert "记录" in result["empathy_response"] or "关照" in result["empathy_response"]

    @patch("app.agents.empathy_agent._query_domain_knowledge")
    @patch("app.agents.empathy_agent._get_llm")
    def test_crisis_fallback_includes_resources(self, mock_llm, mock_knowledge):
        """危机模式 LLM 失败时降级回应也应包含资源。"""
        mock_llm.side_effect = RuntimeError("API Key 未配置")
        mock_knowledge.return_value = ""

        state = self._make_state(
            diary_content="想死 不想活了 绝望",
            intent="emotional_support",
        )
        result = empathy_agent_node(state)

        assert "400-161-9995" in result["empathy_response"]

    @patch("app.agents.empathy_agent._query_domain_knowledge")
    @patch("app.agents.empathy_agent._get_llm")
    def test_queries_domain_knowledge_for_emotional_support(self, mock_llm, mock_knowledge):
        """emotional_support 意图应查询领域知识。"""
        mock_knowledge.return_value = "正念呼吸练习"
        mock_response = MagicMock()
        mock_response.content = "回应"

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_llm_instance = MagicMock()
        mock_llm_instance.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.return_value = mock_llm_instance

        with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_from:
            mock_prompt_obj = MagicMock()
            mock_prompt_obj.__or__ = MagicMock(return_value=mock_chain)
            mock_from.return_value = mock_prompt_obj

            state = self._make_state(intent="emotional_support")
            empathy_agent_node(state)

            # 应调用领域知识查询
            mock_knowledge.assert_called_once()

    @patch("app.agents.empathy_agent._query_domain_knowledge")
    @patch("app.agents.empathy_agent._get_llm")
    def test_skips_domain_knowledge_for_pure_record(self, mock_llm, mock_knowledge):
        """pure_record 意图（非危机）不应查询领域知识。"""
        mock_knowledge.return_value = ""
        mock_response = MagicMock()
        mock_response.content = "回应"

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_llm_instance = MagicMock()
        mock_llm_instance.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.return_value = mock_llm_instance

        with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_from:
            mock_prompt_obj = MagicMock()
            mock_prompt_obj.__or__ = MagicMock(return_value=mock_chain)
            mock_from.return_value = mock_prompt_obj

            state = self._make_state(intent="pure_record")
            empathy_agent_node(state)

            # pure_record 非危机时不应查询
            mock_knowledge.assert_not_called()
