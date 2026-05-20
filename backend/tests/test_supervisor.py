"""
Supervisor Agent 单元测试
==========================

测试 SupervisorAgent 的核心功能：
- classify_intent(): 意图分类和 Token 预算分配
- synthesize_response(): 多 Worker 输出整合
- Worker 失败时的降级行为

Requirements: 1.1, 1.6, 1.7, 3.1, 3.3, 23.2
"""

import pytest
from unittest.mock import MagicMock, patch

from app.agents.supervisor import (
    SupervisorAgent,
    allocate_token_budget,
    get_budget_range,
    create_supervisor,
    TOKEN_BUDGET_MAP,
    DEFAULT_TOKEN_BUDGET,
    SUPERVISOR_CLASSIFY_TOKEN_LIMIT,
)
from app.agents.state import MultiAgentState


# ╔══════════════════════════════════════════════════════════════╗
# ║  Token 预算分配测试                                            ║
# ╚══════════════════════════════════════════════════════════════╝

class TestAllocateTokenBudget:
    """测试 Token 预算分配逻辑。"""

    def test_pure_record_budget_in_range(self):
        """pure_record 预算应在 400-600 范围内。"""
        budget = allocate_token_budget("pure_record")
        assert 400 <= budget <= 600

    def test_emotional_support_budget_in_range(self):
        """emotional_support 预算应在 1000-1500 范围内。"""
        budget = allocate_token_budget("emotional_support")
        assert 1000 <= budget <= 1500

    def test_retrospective_review_budget_in_range(self):
        """retrospective_review 预算应在 1500-2500 范围内。"""
        budget = allocate_token_budget("retrospective_review")
        assert 1500 <= budget <= 2500

    def test_habit_tracking_budget_in_range(self):
        """habit_tracking 预算应在 1200-2000 范围内。"""
        budget = allocate_token_budget("habit_tracking")
        assert 1200 <= budget <= 2000

    def test_unknown_intent_uses_default(self):
        """未知 intent 应使用默认预算。"""
        budget = allocate_token_budget("unknown_intent")
        assert budget == DEFAULT_TOKEN_BUDGET

    def test_get_budget_range_known_intent(self):
        """get_budget_range 应返回正确的范围元组。"""
        min_b, max_b = get_budget_range("pure_record")
        assert min_b == 400
        assert max_b == 600

    def test_get_budget_range_unknown_intent(self):
        """未知 intent 的 budget range 应返回默认值。"""
        min_b, max_b = get_budget_range("unknown")
        assert min_b == DEFAULT_TOKEN_BUDGET
        assert max_b == DEFAULT_TOKEN_BUDGET


# ╔══════════════════════════════════════════════════════════════╗
# ║  classify_intent 测试                                          ║
# ╚══════════════════════════════════════════════════════════════╝

class TestClassifyIntent:
    """测试 Supervisor 的意图分类节点函数。"""

    def _make_state(self, content: str = "今天心情不错") -> dict:
        """创建测试用的最小 state dict。"""
        return {
            "diary_content": content,
            "user_id": 1,
            "diary_nid": 100,
            "intent": "",
            "token_budget": 0,
            "activated_agents": [],
            "episodic_context": [],
            "long_term_profile": {},
            "compressed_history": "",
            "retrieval_context": "",
            "empathy_response": "",
            "insight_response": "",
            "final_response": "",
            "total_tokens_used": 0,
            "agent_mode": "",
            "thk_log": "",
            "errors": [],
        }

    def test_classify_returns_intent(self):
        """classify_intent 应返回包含 intent 字段的 dict。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state("记录一下今天吃了火锅")
        result = supervisor.classify_intent(state)

        assert "intent" in result
        assert result["intent"] in ("pure_record", "emotional_support", "retrospective_review", "habit_tracking")

    def test_classify_returns_token_budget(self):
        """classify_intent 应返回 token_budget 字段。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state("今天心情很差，感觉崩溃了")
        result = supervisor.classify_intent(state)

        assert "token_budget" in result
        assert result["token_budget"] > 0

    def test_classify_returns_activated_agents(self):
        """classify_intent 应返回 activated_agents 列表。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state("今天心情不错")
        result = supervisor.classify_intent(state)

        assert "activated_agents" in result
        assert isinstance(result["activated_agents"], list)
        assert len(result["activated_agents"]) > 0

    def test_pure_record_activates_only_empathy(self):
        """pure_record 意图应仅激活 empathy agent。"""
        supervisor = SupervisorAgent(llm=None)
        # 短文本 + 纯记录信号词 → pure_record
        state = self._make_state("记录一下今天吃了面条")
        result = supervisor.classify_intent(state)

        if result["intent"] == "pure_record":
            assert result["activated_agents"] == ["empathy"]

    def test_emotional_support_activates_empathy_and_retrieval(self):
        """emotional_support 意图应激活 empathy 和 retrieval。"""
        supervisor = SupervisorAgent(llm=None)
        # 强烈情感表达 → emotional_support
        state = self._make_state("今天真的太崩溃了，感觉快撑不住了，好绝望")
        result = supervisor.classify_intent(state)

        if result["intent"] == "emotional_support":
            assert "empathy" in result["activated_agents"]
            assert "retrieval" in result["activated_agents"]

    def test_retrospective_review_activates_all_three(self):
        """retrospective_review 意图应激活三个 Worker Agent。"""
        supervisor = SupervisorAgent(llm=None)
        # 时间回溯 + 分析关键词 → retrospective_review
        state = self._make_state("和之前写过的一样，为什么总是这样反复，想要复盘一下最近的状态")
        result = supervisor.classify_intent(state)

        if result["intent"] == "retrospective_review":
            assert "empathy" in result["activated_agents"]
            assert "retrieval" in result["activated_agents"]
            assert "insight" in result["activated_agents"]

    def test_habit_tracking_activates_retrieval_and_insight(self):
        """habit_tracking 意图应激活 retrieval 和 insight。"""
        supervisor = SupervisorAgent(llm=None)
        result_agents = supervisor._determine_activated_agents("habit_tracking")
        assert "retrieval" in result_agents
        assert "insight" in result_agents
        assert "empathy" not in result_agents

    def test_classify_budget_matches_intent(self):
        """分配的预算应与 intent 类型对应的范围匹配。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state("今天心情不错")
        result = supervisor.classify_intent(state)

        intent = result["intent"]
        budget = result["token_budget"]
        min_b, max_b = get_budget_range(intent)
        assert min_b <= budget <= max_b

    def test_classify_handles_empty_content(self):
        """空内容应降级为 pure_record。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state("")
        result = supervisor.classify_intent(state)

        assert result["intent"] == "pure_record"

    def test_classify_handles_classifier_exception(self):
        """IntentClassifier 异常时应降级为 pure_record。"""
        supervisor = SupervisorAgent(llm=None)
        # Mock IntentClassifier 抛出异常
        supervisor._intent_classifier = MagicMock()
        supervisor._intent_classifier.classify.side_effect = RuntimeError("LLM error")

        state = self._make_state("测试内容")
        result = supervisor.classify_intent(state)

        assert result["intent"] == "pure_record"
        assert result["token_budget"] > 0


# ╔══════════════════════════════════════════════════════════════╗
# ║  synthesize_response 测试                                      ║
# ╚══════════════════════════════════════════════════════════════╝

class TestSynthesizeResponse:
    """测试 Supervisor 的结果整合节点函数。"""

    def _make_state_with_outputs(
        self,
        empathy: str = "",
        retrieval: str = "",
        insight: str = "",
        errors: list = None,
        intent: str = "pure_record",
    ) -> dict:
        """创建包含 Worker 输出的测试 state。"""
        return {
            "diary_content": "测试日记",
            "user_id": 1,
            "diary_nid": 100,
            "intent": intent,
            "token_budget": 1000,
            "activated_agents": [],
            "episodic_context": [],
            "long_term_profile": {},
            "compressed_history": "",
            "retrieval_context": retrieval,
            "empathy_response": empathy,
            "insight_response": insight,
            "final_response": "",
            "total_tokens_used": 0,
            "agent_mode": "",
            "thk_log": "",
            "errors": errors or [],
        }

    def test_synthesize_single_output(self):
        """单个 Worker 输出时直接返回该输出。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state_with_outputs(empathy="你今天辛苦了，好好休息。")
        result = supervisor.synthesize_response(state)

        assert result["final_response"] == "你今天辛苦了，好好休息。"
        assert result["agent_mode"] == "multi_agent"

    def test_synthesize_multiple_outputs(self):
        """多个 Worker 输出时应拼接为连贯回应。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state_with_outputs(
            empathy="理解你的感受，这确实不容易。",
            insight="从最近的日记来看，你的压力主要来自工作。",
        )
        result = supervisor.synthesize_response(state)

        # 简单拼接模式下，两个输出都应包含在最终回应中
        assert "理解你的感受" in result["final_response"]
        assert "压力主要来自工作" in result["final_response"]

    def test_synthesize_with_worker_failure(self):
        """Worker 失败时应使用已成功的输出生成回应（Requirement 23.2）。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state_with_outputs(
            empathy="你今天的心情我能理解。",
            retrieval="",  # retrieval 失败，无输出
            errors=["Worker 'retrieval' failed: TimeoutError: API timeout"],
        )
        result = supervisor.synthesize_response(state)

        # 应使用 empathy 的成功输出
        assert "你今天的心情我能理解" in result["final_response"]
        assert result["agent_mode"] == "multi_agent"

    def test_synthesize_all_workers_failed(self):
        """所有 Worker 失败时应返回降级回应。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state_with_outputs(
            empathy="",
            retrieval="",
            insight="",
            errors=[
                "Worker 'empathy' failed: RuntimeError",
                "Worker 'retrieval' failed: RuntimeError",
            ],
        )
        result = supervisor.synthesize_response(state)

        # 应返回 fallback 回应
        assert "感谢你今天的记录" in result["final_response"]

    def test_synthesize_with_llm(self):
        """有 LLM 时应调用 LLM 整合多个输出。"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "综合来看，你今天经历了不少，好好休息吧。"
        mock_llm.invoke.return_value = mock_response

        supervisor = SupervisorAgent(llm=mock_llm)
        state = self._make_state_with_outputs(
            empathy="理解你的感受。",
            insight="最近压力较大。",
            intent="retrospective_review",
        )
        result = supervisor.synthesize_response(state)

        # LLM 被调用
        mock_llm.invoke.assert_called_once()
        assert result["final_response"] == "综合来看，你今天经历了不少，好好休息吧。"

    def test_synthesize_llm_failure_fallback(self):
        """LLM 整合失败时应回退到简单拼接。"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")

        supervisor = SupervisorAgent(llm=mock_llm)
        state = self._make_state_with_outputs(
            empathy="理解你。",
            insight="建议休息。",
            intent="retrospective_review",
        )
        result = supervisor.synthesize_response(state)

        # 应回退到简单拼接
        assert "理解你" in result["final_response"]
        assert "建议休息" in result["final_response"]

    def test_synthesize_priority_order(self):
        """简单拼接时应按 empathy > insight > retrieval 优先级排序。"""
        supervisor = SupervisorAgent(llm=None)
        state = self._make_state_with_outputs(
            empathy="情感回应",
            insight="洞察分析",
            retrieval="历史参考",
        )
        result = supervisor.synthesize_response(state)

        response = result["final_response"]
        # empathy 应在 insight 之前，insight 应在 retrieval 之前
        empathy_pos = response.index("情感回应")
        insight_pos = response.index("洞察分析")
        retrieval_pos = response.index("历史参考")
        assert empathy_pos < insight_pos < retrieval_pos


# ╔══════════════════════════════════════════════════════════════╗
# ║  工厂函数测试                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

class TestCreateSupervisor:
    """测试工厂函数。"""

    def test_create_supervisor_without_llm(self):
        """无 LLM 时应创建仅规则层的 Supervisor。"""
        supervisor = create_supervisor(llm=None)
        assert isinstance(supervisor, SupervisorAgent)

    def test_create_supervisor_with_llm(self):
        """有 LLM 时应创建完整的 Supervisor。"""
        mock_llm = MagicMock()
        supervisor = create_supervisor(llm=mock_llm)
        assert isinstance(supervisor, SupervisorAgent)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Token 预算常量验证                                            ║
# ╚══════════════════════════════════════════════════════════════╝

class TestTokenBudgetConstants:
    """验证 Token 预算常量符合需求规格。"""

    def test_supervisor_classify_token_limit(self):
        """Supervisor 分类 Token 上限应为 100（Requirement 1.6）。"""
        assert SUPERVISOR_CLASSIFY_TOKEN_LIMIT == 100

    def test_all_intent_types_have_budget(self):
        """所有 4 种 intent 类型都应有预算配置。"""
        expected_intents = {"pure_record", "emotional_support", "retrospective_review", "habit_tracking"}
        assert set(TOKEN_BUDGET_MAP.keys()) == expected_intents

    def test_budget_ranges_match_requirements(self):
        """预算范围应匹配需求规格（Requirement 3.1）。"""
        assert TOKEN_BUDGET_MAP["pure_record"] == (400, 600)
        assert TOKEN_BUDGET_MAP["emotional_support"] == (1000, 1500)
        assert TOKEN_BUDGET_MAP["retrospective_review"] == (1500, 2500)
        assert TOKEN_BUDGET_MAP["habit_tracking"] == (1200, 2000)
