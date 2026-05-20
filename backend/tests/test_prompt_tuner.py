"""
PromptTuner 单元测试
=====================

测试动态 Prompt 构建器的核心功能：
- 新用户默认偏好
- Thompson Sampling 风格选择
- 动态 Prompt 片段生成
- 偏好加载失败时的降级行为
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.feedback.prompt_tuner import (
    PromptTuner,
    UserPreference,
    ResponseLength,
    AgentType,
    build_dynamic_prompt_for_agent,
    get_default_preference,
    DEFAULT_STYLE,
    DEFAULT_RESPONSE_LENGTH,
    DEFAULT_DIRECTNESS,
    SUPPORTED_STYLES,
    _sample_style_from_preferences,
    _infer_directness,
    _infer_response_length,
)
from app.models.style_preference import StylePreference


def _make_style_pref(style: str, alpha: float = 1.0, beta: float = 1.0) -> StylePreference:
    """创建一个 mock StylePreference 对象。"""
    pref = MagicMock(spec=StylePreference)
    pref.style = style
    pref.alpha = alpha
    pref.beta = beta
    pref.user_id = 1
    pref.updated_at = datetime.utcnow()
    return pref


class TestDefaultPreference:
    """测试默认偏好向量。"""

    def test_default_preference_values(self):
        """新用户默认偏好：中等长度、共情型、0.5 直接度。"""
        pref = get_default_preference()
        assert pref.response_length == ResponseLength.MEDIUM
        assert pref.style == "empathetic"
        assert pref.directness == 0.5

    def test_new_user_gets_default(self):
        """新用户（无 StylePreference 记录）应返回默认偏好。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        tuner = PromptTuner(db)
        pref = tuner.get_user_preference(user_id=999)

        assert pref.style == DEFAULT_STYLE
        assert pref.response_length == DEFAULT_RESPONSE_LENGTH
        assert pref.directness == DEFAULT_DIRECTNESS


class TestThompsonSampling:
    """测试 Thompson Sampling 风格选择。"""

    def test_sample_returns_valid_style(self):
        """采样结果应为支持的风格之一。"""
        prefs = [_make_style_pref(s) for s in SUPPORTED_STYLES]
        style = _sample_style_from_preferences(prefs)
        assert style in SUPPORTED_STYLES

    def test_sample_empty_preferences_returns_default(self):
        """空偏好列表应返回默认风格。"""
        style = _sample_style_from_preferences([])
        assert style == DEFAULT_STYLE

    def test_high_alpha_style_preferred(self):
        """alpha 远大于 beta 的风格应更频繁被选中。"""
        prefs = [
            _make_style_pref("practical", alpha=50.0, beta=1.0),
            _make_style_pref("empathetic", alpha=1.0, beta=50.0),
            _make_style_pref("philosophical", alpha=1.0, beta=50.0),
            _make_style_pref("humorous", alpha=1.0, beta=50.0),
        ]

        # 多次采样，practical 应占多数
        results = [_sample_style_from_preferences(prefs) for _ in range(100)]
        practical_count = results.count("practical")
        assert practical_count > 80  # 应该绝大多数选择 practical


class TestDirectnessInference:
    """测试直接度推断。"""

    def test_empty_preferences_returns_default(self):
        """空偏好应返回默认直接度。"""
        assert _infer_directness([]) == DEFAULT_DIRECTNESS

    def test_practical_preference_higher_directness(self):
        """偏好 practical 风格的用户应有较高直接度。"""
        prefs = [
            _make_style_pref("practical", alpha=10.0, beta=1.0),
            _make_style_pref("empathetic", alpha=1.0, beta=10.0),
        ]
        directness = _infer_directness(prefs)
        assert directness > 0.5

    def test_empathetic_preference_lower_directness(self):
        """偏好 empathetic 风格的用户应有较低直接度。"""
        prefs = [
            _make_style_pref("empathetic", alpha=10.0, beta=1.0),
            _make_style_pref("practical", alpha=1.0, beta=10.0),
        ]
        directness = _infer_directness(prefs)
        assert directness < 0.5


class TestResponseLengthInference:
    """测试回应长度推断。"""

    def test_empty_preferences_returns_default(self):
        """空偏好应返回默认长度。"""
        assert _infer_response_length([]) == DEFAULT_RESPONSE_LENGTH

    def test_new_user_few_feedback_returns_default(self):
        """反馈不足的用户应返回默认长度。"""
        prefs = [_make_style_pref(s) for s in SUPPORTED_STYLES]
        assert _infer_response_length(prefs) == DEFAULT_RESPONSE_LENGTH


class TestPromptTunerBuildPrompt:
    """测试动态 Prompt 片段构建。"""

    def test_empathy_prompt_contains_style(self):
        """Empathy Agent 的 Prompt 应包含风格描述。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        tuner = PromptTuner(db)
        prompt = tuner.build_dynamic_prompt(user_id=1, agent_type="empathy")

        assert "用户偏好适配指令" in prompt
        assert "回应风格" in prompt
        assert "回应长度" in prompt
        assert "表达直接度" in prompt

    def test_insight_prompt_contains_style(self):
        """Insight Agent 的 Prompt 应包含风格描述。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        tuner = PromptTuner(db)
        prompt = tuner.build_dynamic_prompt(user_id=1, agent_type="insight")

        assert "用户偏好适配指令" in prompt
        assert "回应风格" in prompt

    def test_prompt_reflects_user_preference(self):
        """Prompt 应反映用户的实际偏好。"""
        prefs = [
            _make_style_pref("practical", alpha=50.0, beta=1.0),
            _make_style_pref("empathetic", alpha=1.0, beta=50.0),
            _make_style_pref("philosophical", alpha=1.0, beta=50.0),
            _make_style_pref("humorous", alpha=1.0, beta=50.0),
        ]

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = prefs

        tuner = PromptTuner(db)

        # 多次生成，大部分应包含 practical 风格描述
        practical_count = 0
        for _ in range(20):
            prompt = tuner.build_dynamic_prompt(user_id=1, agent_type="empathy")
            if "务实" in prompt or "简洁有力" in prompt:
                practical_count += 1

        assert practical_count > 15  # 大部分应选择 practical

    def test_db_failure_returns_default_prompt(self):
        """数据库查询失败时应返回基于默认偏好的 Prompt。"""
        db = MagicMock()
        db.query.side_effect = Exception("DB connection error")

        tuner = PromptTuner(db)
        prompt = tuner.build_dynamic_prompt(user_id=1, agent_type="empathy")

        # 应该不抛异常，返回默认偏好的 Prompt
        assert "用户偏好适配指令" in prompt
        assert "温暖共情" in prompt  # 默认共情型


class TestBuildDynamicPromptForAgent:
    """测试便捷函数。"""

    def test_convenience_function_works(self):
        """便捷函数应正常工作。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        prompt = build_dynamic_prompt_for_agent(db, user_id=1, agent_type="empathy")
        assert "用户偏好适配指令" in prompt

    def test_convenience_function_insight(self):
        """便捷函数对 insight agent 应正常工作。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        prompt = build_dynamic_prompt_for_agent(db, user_id=1, agent_type="insight")
        assert "用户偏好适配指令" in prompt


class TestDirectnessToLevel:
    """测试直接度数值到级别的映射。"""

    def test_low_directness(self):
        assert PromptTuner._directness_to_level(0.0) == "low"
        assert PromptTuner._directness_to_level(0.2) == "low"
        assert PromptTuner._directness_to_level(0.34) == "low"

    def test_medium_directness(self):
        assert PromptTuner._directness_to_level(0.35) == "medium"
        assert PromptTuner._directness_to_level(0.5) == "medium"
        assert PromptTuner._directness_to_level(0.65) == "medium"

    def test_high_directness(self):
        assert PromptTuner._directness_to_level(0.66) == "high"
        assert PromptTuner._directness_to_level(0.8) == "high"
        assert PromptTuner._directness_to_level(1.0) == "high"


class TestPromptTunerAgentIntegration:
    """测试 PromptTuner 与 Agent 的集成注入。"""

    @patch("app.agents.empathy_agent.SessionLocal")
    def test_empathy_agent_injects_dynamic_prompt(self, mock_session_local):
        """Empathy Agent 应注入 PromptTuner 动态 Prompt 片段。"""
        # Mock DB session 返回空偏好（新用户）
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_session_local.return_value = mock_db

        # 验证 build_dynamic_prompt_for_agent 被正确调用
        with patch("app.agents.empathy_agent.build_dynamic_prompt_for_agent") as mock_build:
            mock_build.return_value = "\n## 用户偏好适配指令\n测试片段"

            from app.agents.empathy_agent import empathy_agent_node

            state = {
                "diary_content": "今天心情不错",
                "intent": "pure_record",
                "user_id": 1,
                "long_term_profile": {},
                "episodic_context": [],
            }

            # Mock LLM 调用以避免实际 API 请求
            with patch("app.agents.empathy_agent._get_llm") as mock_get_llm:
                mock_llm = MagicMock()
                mock_response = MagicMock()
                mock_response.content = "测试回应"
                mock_llm.invoke.return_value = mock_response

                # patch langchain_core.prompts 中的 ChatPromptTemplate
                with patch("langchain_core.prompts.ChatPromptTemplate.from_messages") as mock_from_msgs:
                    mock_chain = MagicMock()
                    mock_chain.invoke.return_value = mock_response
                    mock_prompt = MagicMock()
                    mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                    mock_from_msgs.return_value = mock_prompt

                    mock_get_llm.return_value = mock_llm

                    empathy_agent_node(state)
                    mock_build.assert_called_once_with(mock_db, 1, "empathy")

    @patch("app.agents.insight_agent.SessionLocal")
    def test_insight_agent_injects_dynamic_prompt(self, mock_session_local):
        """Insight Agent 应注入 PromptTuner 动态 Prompt 片段。"""
        # Mock DB session 返回空偏好（新用户）
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_session_local.return_value = mock_db

        with patch("app.agents.insight_agent.build_dynamic_prompt_for_agent") as mock_build:
            mock_build.return_value = "\n## 用户偏好适配指令\n测试片段"

            from app.agents.insight_agent import insight_agent

            state = {
                "diary_content": "今天心情不错",
                "intent": "retrospective_review",
                "user_id": 1,
                "retrieval_context": "",
                "episodic_context": [],
                "long_term_profile": {},
            }

            with patch("app.agents.insight_agent._query_domain_knowledge", return_value=""):
                with patch("app.agents.insight_agent._build_llm") as mock_llm_builder:
                    mock_llm = MagicMock()
                    mock_response = MagicMock()
                    mock_response.content = "洞察分析结果"
                    mock_llm.invoke.return_value = mock_response
                    mock_llm_builder.return_value = mock_llm

                    insight_agent(state)
                    mock_build.assert_called_once_with(mock_db, 1, "insight")

    def test_preference_change_takes_effect_immediately(self):
        """偏好变化应在下次请求时立即生效（无缓存）。"""
        # 第一次调用：返回 practical 偏好
        prefs_practical = [_make_style_pref("practical", alpha=50.0, beta=1.0)]
        # 第二次调用：返回 humorous 偏好
        prefs_humorous = [_make_style_pref("humorous", alpha=50.0, beta=1.0)]

        db = MagicMock()
        db.query.return_value.filter.return_value.all.side_effect = [
            prefs_practical,
            prefs_humorous,
        ]

        tuner = PromptTuner(db)

        # 第一次请求
        prompt1 = tuner.build_dynamic_prompt(user_id=1, agent_type="empathy")
        # 第二次请求（偏好已变化）
        prompt2 = tuner.build_dynamic_prompt(user_id=1, agent_type="empathy")

        # 两次结果应不同，证明没有缓存
        assert "务实" in prompt1 or "简洁有力" in prompt1
        assert "幽默" in prompt2 or "轻松" in prompt2
