"""
Multi-Agent State 定义
=======================

定义 MultiAgentState TypedDict，作为 LangGraph 状态图的共享状态类型。
使用 Annotated 类型为列表字段提供 reducer，支持多个 Worker Agent 并发更新。

Requirements: 2.1, 2.3
"""

import operator
from typing import Annotated, List, TypedDict


def _reduce_list(left: List[str], right: List[str]) -> List[str]:
    """
    列表 reducer：合并两个列表，去重保持顺序。
    用于 activated_agents 字段，避免并发写入冲突。
    """
    seen = set(left)
    result = list(left)
    for item in right:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_token_usage(response) -> dict:
    """
    从 LangChain AIMessage 的 response_metadata 中提取 token 消耗。
    供各 Agent 节点复用，避免重复代码。

    DeepSeek API 返回的 usage 结构：
    {
        "prompt_tokens": 600,
        "completion_tokens": 280,
        "total_tokens": 880,
        "prompt_cache_hit_tokens": 400,
        "prompt_cache_miss_tokens": 200
    }

    :param response: LangChain AIMessage 对象
    :return: {"total_tokens_used": int, "cache_hit_tokens": int, "cache_miss_tokens": int, "output_tokens": int}
    """
    usage = {}
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage", {})

    return {
        "total_tokens_used": usage.get("total_tokens", 0),
        "cache_hit_tokens": usage.get("prompt_cache_hit_tokens", 0),
        "cache_miss_tokens": usage.get("prompt_cache_miss_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }


class MultiAgentState(TypedDict):
    """
    LangGraph 状态图共享状态，在各 Agent 节点间传递数据。

    字段说明：
    - 输入字段：diary_content, user_id, diary_nid
    - Supervisor 输出：intent, token_budget, activated_agents
    - Memory 上下文：episodic_context, long_term_profile, compressed_history
    - Worker 输出：retrieval_context, empathy_response, insight_response
    - 最终输出：final_response, total_tokens_used, agent_mode, thk_log
    - Token 追踪：使用 operator.add reducer 支持多节点累加
    - 错误追踪：errors（使用 operator.add reducer 支持并发追加）

    Requirements: 2.1
    """

    # 输入
    diary_content: str
    user_id: int
    diary_nid: int

    # Supervisor 输出
    intent: str  # pure_record | emotional_support | retrospective_review | habit_tracking
    token_budget: int
    activated_agents: Annotated[List[str], _reduce_list]

    # Memory 上下文
    episodic_context: List[dict]
    long_term_profile: dict
    compressed_history: str

    # Worker 输出
    retrieval_context: str
    empathy_response: str
    insight_response: str

    # 最终输出
    final_response: str
    total_tokens_used: Annotated[int, operator.add]
    agent_mode: str  # "multi_agent"
    thk_log: str

    # Token 明细追踪（各节点 LLM 调用后累加）
    cache_hit_tokens: Annotated[int, operator.add]
    cache_miss_tokens: Annotated[int, operator.add]
    output_tokens: Annotated[int, operator.add]

    # 错误追踪（使用 operator.add reducer 支持多个 Worker 并发追加错误）
    errors: Annotated[List[str], operator.add]


__all__ = ["MultiAgentState", "extract_token_usage"]
