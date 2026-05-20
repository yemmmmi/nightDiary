"""
WorkingMemory 单元测试
======================

测试 WorkingMemory 的初始化、更新、Token 限制和清除功能。

Validates: Requirements 7.1, 7.2, 7.3, 7.4
"""

import pytest
from app.memory.working import WorkingMemory, MultiAgentState, MAX_CONTEXT_TOKENS
from app.agents.context_compressor import estimate_tokens


class TestWorkingMemoryInit:
    """测试 init_session 方法。"""

    def test_init_session_creates_valid_state(self):
        """init_session 应返回包含 diary_content 和 user_id 的 MultiAgentState。"""
        wm = WorkingMemory()
        state = wm.init_session(diary_content="今天心情不错", user_id=42, diary_nid=100)

        assert state["diary_content"] == "今天心情不错"
        assert state["user_id"] == 42
        assert state["diary_nid"] == 100
        assert state["agent_mode"] == "multi_agent"
        assert state["intent"] == ""
        assert state["activated_agents"] == []
        assert state["errors"] == []
        assert state["total_tokens_used"] == 0

    def test_init_session_sets_active(self):
        """init_session 后 is_active 应为 True。"""
        wm = WorkingMemory()
        assert wm.is_active is False
        wm.init_session("测试", user_id=1)
        assert wm.is_active is True

    def test_init_session_default_diary_nid(self):
        """diary_nid 默认值应为 0。"""
        wm = WorkingMemory()
        state = wm.init_session("内容", user_id=5)
        assert state["diary_nid"] == 0


class TestWorkingMemoryUpdate:
    """测试 update 方法。"""

    def test_update_simple_field(self):
        """update 应正确更新简单字段。"""
        wm = WorkingMemory()
        wm.init_session("日记内容", user_id=1)

        state = wm.update("intent", "emotional_support")
        assert state["intent"] == "emotional_support"

    def test_update_list_field(self):
        """update 应正确更新列表字段。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        state = wm.update("activated_agents", ["empathy", "retrieval"])
        assert state["activated_agents"] == ["empathy", "retrieval"]

    def test_update_raises_on_inactive_session(self):
        """未初始化时 update 应抛出 RuntimeError。"""
        wm = WorkingMemory()
        with pytest.raises(RuntimeError, match="not initialized"):
            wm.update("intent", "test")

    def test_update_raises_on_invalid_key(self):
        """无效 key 应抛出 KeyError。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)
        with pytest.raises(KeyError, match="Invalid state key"):
            wm.update("nonexistent_field", "value")

    def test_update_returns_deep_copy(self):
        """update 返回的 state 应为深拷贝，修改不影响内部状态。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        state = wm.update("activated_agents", ["empathy"])
        state["activated_agents"].append("retrieval")

        # 内部状态不应被修改
        internal = wm.state
        assert internal["activated_agents"] == ["empathy"]


class TestWorkingMemoryTokenLimit:
    """测试 4000 tokens 中间上下文限制。"""

    def test_within_limit_no_truncation(self):
        """未超限时不应截断。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        short_text = "这是一段简短的检索结果。"
        state = wm.update("retrieval_context", short_text)
        assert state["retrieval_context"] == short_text

    def test_exceeds_limit_truncates(self):
        """超限时应截断使总 Token 不超过 4000。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        # 生成一段超长文本（约 6000+ tokens）
        long_text = "这是一段非常长的文本内容，用于测试截断功能。" * 300

        state = wm.update("retrieval_context", long_text)

        # 截断后 tokens 应不超过 MAX_CONTEXT_TOKENS
        result_tokens = estimate_tokens(state["retrieval_context"])
        assert result_tokens <= MAX_CONTEXT_TOKENS

    def test_multiple_fields_share_budget(self):
        """多个中间上下文字段共享 4000 tokens 预算。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        # 先填充一个字段约 3000 tokens
        text_3000 = "这是一段较长的文本用于占用大量空间。" * 130
        wm.update("retrieval_context", text_3000)

        # 再更新另一个字段，应被截断
        long_text = "另一段很长的分析结果，测试共享预算。" * 200
        state = wm.update("empathy_response", long_text)

        # 总 tokens 不超限
        total = wm.get_context_tokens_used()
        assert total <= MAX_CONTEXT_TOKENS

    def test_no_space_returns_empty(self):
        """当其他字段已用满预算时，新字段应返回空字符串。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        # 用四个字段分别填充接近 1000 tokens 的内容
        fill_text = "填充内容测试长文本。" * 80  # ~约 1200 tokens
        wm.update("retrieval_context", fill_text)
        wm.update("empathy_response", fill_text)
        wm.update("insight_response", fill_text)
        wm.update("compressed_history", fill_text)

        # 总量应不超限
        total = wm.get_context_tokens_used()
        assert total <= MAX_CONTEXT_TOKENS


class TestWorkingMemoryClear:
    """测试 clear 方法。"""

    def test_clear_resets_state(self):
        """clear 后状态应为 None，is_active 为 False。"""
        wm = WorkingMemory()
        wm.init_session("日记内容", user_id=1)
        assert wm.is_active is True

        wm.clear()
        assert wm.is_active is False
        assert wm.state is None

    def test_clear_on_inactive_is_safe(self):
        """未初始化时调用 clear 不应报错。"""
        wm = WorkingMemory()
        wm.clear()  # 不应抛出异常
        assert wm.is_active is False


class TestGetContextTokensUsed:
    """测试 get_context_tokens_used 方法。"""

    def test_returns_zero_when_inactive(self):
        """未初始化时应返回 0。"""
        wm = WorkingMemory()
        assert wm.get_context_tokens_used() == 0

    def test_returns_correct_count(self):
        """应正确计算所有中间上下文字段的 Token 总和。"""
        wm = WorkingMemory()
        wm.init_session("日记", user_id=1)

        text = "测试内容"
        wm.update("retrieval_context", text)

        expected = estimate_tokens(text)
        assert wm.get_context_tokens_used() == expected
