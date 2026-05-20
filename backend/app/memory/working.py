"""
WorkingMemory — 会话级工作记忆（LangGraph State 包装）
======================================================

管理当前分析会话的上下文状态，基于 LangGraph MultiAgentState TypedDict。

核心职责：
- init_session(): 初始化 MultiAgentState，设置 diary_content 和 user_id
- update(): 更新状态字段，强制 4000 tokens 中间上下文限制
- clear(): 请求完成后清除会话状态

Requirements: 7.1, 7.2, 7.3, 7.4
"""

import logging
from copy import deepcopy
from typing import Any, List, Optional

from app.agents.context_compressor import estimate_tokens
from app.agents.state import MultiAgentState

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量                                                          ║
# ╚══════════════════════════════════════════════════════════════╝

# 中间上下文最大 Token 限制
MAX_CONTEXT_TOKENS = 4000

# 需要强制 Token 限制的中间上下文字段
_CONTEXT_FIELDS = (
    "retrieval_context",
    "empathy_response",
    "insight_response",
    "compressed_history",
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  WorkingMemory 类                                              ║
# ╚══════════════════════════════════════════════════════════════╝

class WorkingMemory:
    """
    会话级工作记忆，包装 LangGraph MultiAgentState。

    在每次分析请求开始时通过 init_session() 初始化，
    通过 update() 更新状态字段并强制 4000 tokens 中间上下文限制，
    请求完成后通过 clear() 清除。

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """

    MAX_CONTEXT_TOKENS = MAX_CONTEXT_TOKENS

    def __init__(self) -> None:
        """初始化 WorkingMemory 实例，状态为空。"""
        self._state: Optional[MultiAgentState] = None

    @property
    def state(self) -> Optional[MultiAgentState]:
        """获取当前会话状态（只读副本）。"""
        if self._state is None:
            return None
        return deepcopy(self._state)

    @property
    def is_active(self) -> bool:
        """会话是否已初始化且未清除。"""
        return self._state is not None

    def init_session(self, diary_content: str, user_id: int, diary_nid: int = 0) -> MultiAgentState:
        """
        初始化会话，创建 MultiAgentState。

        :param diary_content: 当前日记内容
        :param user_id: 用户 ID
        :param diary_nid: 日记条目 NID，默认 0
        :return: 初始化后的 MultiAgentState
        """
        self._state = MultiAgentState(
            diary_content=diary_content,
            user_id=user_id,
            diary_nid=diary_nid,
            intent="",
            token_budget=0,
            activated_agents=[],
            episodic_context=[],
            long_term_profile={},
            compressed_history="",
            retrieval_context="",
            empathy_response="",
            insight_response="",
            final_response="",
            total_tokens_used=0,
            agent_mode="multi_agent",
            thk_log="",
            errors=[],
        )
        logger.debug(
            "WorkingMemory session initialized: user_id=%d, content_len=%d",
            user_id,
            len(diary_content),
        )
        return deepcopy(self._state)

    def update(self, key: str, value: Any) -> MultiAgentState:
        """
        更新状态字段。

        对中间上下文字段（retrieval_context, empathy_response,
        insight_response, compressed_history）强制 4000 tokens 总限制。
        当更新后中间上下文超限时，截断当前写入的值使总量不超过限制。

        :param key: 状态字段名
        :param value: 新值
        :return: 更新后的 MultiAgentState
        :raises RuntimeError: 会话未初始化时调用
        :raises KeyError: key 不在 MultiAgentState 中
        """
        if self._state is None:
            raise RuntimeError("WorkingMemory session not initialized. Call init_session() first.")

        if key not in MultiAgentState.__annotations__:
            raise KeyError(f"Invalid state key: '{key}'. Must be one of {list(MultiAgentState.__annotations__.keys())}")

        # 对中间上下文字段强制 Token 限制
        if key in _CONTEXT_FIELDS and isinstance(value, str):
            value = self._enforce_token_limit(key, value)

        self._state[key] = value  # type: ignore[literal-required]
        logger.debug("WorkingMemory updated: key=%s, type=%s", key, type(value).__name__)
        return deepcopy(self._state)

    def get_context_tokens_used(self) -> int:
        """
        计算当前所有中间上下文字段的总 Token 消耗。

        :return: 中间上下文总 Token 数
        """
        if self._state is None:
            return 0

        total = 0
        for field in _CONTEXT_FIELDS:
            content = self._state.get(field, "")  # type: ignore[literal-required]
            if content and isinstance(content, str):
                total += estimate_tokens(content)
        return total

    def clear(self) -> None:
        """
        清除会话状态，释放内存。
        请求完成后调用。
        """
        if self._state is not None:
            user_id = self._state.get("user_id", "unknown")
            logger.debug("WorkingMemory session cleared: user_id=%s", user_id)
        self._state = None

    # ──────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────

    def _enforce_token_limit(self, key: str, value: str) -> str:
        """
        强制中间上下文不超过 MAX_CONTEXT_TOKENS。

        计算其他中间上下文字段已用 Token 数，如果加上新值会超限，
        则截断新值使总量恰好不超过限制。

        :param key: 当前要写入的字段名
        :param value: 要写入的文本
        :return: 可能被截断的文本
        """
        # 计算其他字段已占用的 tokens
        other_tokens = 0
        for field in _CONTEXT_FIELDS:
            if field == key:
                continue
            content = self._state.get(field, "")  # type: ignore[literal-required]
            if content and isinstance(content, str):
                other_tokens += estimate_tokens(content)

        # 计算当前值的 tokens
        value_tokens = estimate_tokens(value)
        total = other_tokens + value_tokens

        if total <= self.MAX_CONTEXT_TOKENS:
            return value

        # 需要截断
        available_tokens = self.MAX_CONTEXT_TOKENS - other_tokens
        if available_tokens <= 0:
            logger.warning(
                "WorkingMemory token limit reached: no space for field '%s' "
                "(other fields use %d tokens, limit=%d)",
                key,
                other_tokens,
                self.MAX_CONTEXT_TOKENS,
            )
            return ""

        # 逐步截断直到符合限制
        # 粗略估算：每个中文字符约 1.5 tokens，取保守比例
        ratio = available_tokens / value_tokens
        target_len = int(len(value) * ratio * 0.9)  # 留 10% 余量
        truncated = value[:target_len]

        # 微调确保不超限
        while estimate_tokens(truncated) > available_tokens and len(truncated) > 0:
            truncated = truncated[:int(len(truncated) * 0.9)]

        if truncated and not truncated.endswith("..."):
            truncated = truncated.rstrip() + "..."

        logger.info(
            "WorkingMemory enforced token limit on '%s': %d -> %d tokens (available=%d)",
            key,
            value_tokens,
            estimate_tokens(truncated),
            available_tokens,
        )
        return truncated
