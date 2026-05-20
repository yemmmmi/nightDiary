"""
LangGraph Multi-Agent 状态图
==============================

使用 LangGraph StateGraph 构建 Multi-Agent 协调状态图。
实现条件路由器，根据 intent 将执行路由到对应 Worker Agent 节点。
支持添加新 Worker Agent 节点无需修改已有节点实现。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import logging
from typing import Callable, Dict, List, Sequence

from langgraph.graph import END, StateGraph

from app.agents.state import MultiAgentState

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Intent → Worker Agent 路由映射                                ║
# ╚══════════════════════════════════════════════════════════════╝

# 默认路由映射：intent → 需要激活的 worker agent 名称列表
DEFAULT_INTENT_ROUTING: Dict[str, List[str]] = {
    "pure_record": ["empathy"],
    "emotional_support": ["empathy", "retrieval"],
    "retrospective_review": ["empathy", "retrieval", "insight"],
    "habit_tracking": ["retrieval", "insight"],
}


# ╔══════════════════════════════════════════════════════════════╗
# ║  Worker Node 包装器                                            ║
# ╚══════════════════════════════════════════════════════════════╝

# Worker Agent 节点函数类型：接收 MultiAgentState，返回部分状态更新 dict
WorkerNodeFn = Callable[[MultiAgentState], dict]


def _make_safe_worker_node(name: str, fn: WorkerNodeFn) -> WorkerNodeFn:
    """
    包装 Worker Agent 节点函数，捕获异常并记录到 state["errors"]。

    满足 Requirement 2.5：若某个 Worker Agent 执行失败，
    LangGraph_State 应记录错误，Supervisor_Agent 应使用其余成功的输出生成回应。

    注意：返回值仅包含需要更新的字段（部分状态更新），
    避免并发 Worker 同时写入相同字段导致 InvalidUpdateError。

    :param name: Worker Agent 名称（用于错误日志）
    :param fn: 原始 Worker Agent 节点函数
    :return: 安全包装后的节点函数
    """

    def safe_node(state: MultiAgentState) -> dict:
        try:
            return fn(state)
        except Exception as exc:
            error_msg = f"Worker '{name}' failed: {type(exc).__name__}: {exc}"
            logger.error(error_msg, exc_info=True)
            # 仅返回 errors 字段更新（使用 Annotated[List, operator.add] reducer 追加）
            return {"errors": [error_msg]}

    safe_node.__name__ = f"safe_{name}_node"
    return safe_node


# ╔══════════════════════════════════════════════════════════════╗
# ║  条件路由器                                                     ║
# ╚══════════════════════════════════════════════════════════════╝

def _build_route_function(
    registered_workers: Dict[str, str],
    intent_routing: Dict[str, List[str]],
) -> Callable[[MultiAgentState], Sequence[str]]:
    """
    构建条件路由函数，根据 state["intent"] 决定分发到哪些 Worker 节点。

    满足 Requirement 2.2：条件路由器根据分类意图将执行路由到相应的 Worker Agent 节点。

    :param registered_workers: worker_name → graph_node_name 映射
    :param intent_routing: intent → worker_names 映射
    :return: 路由函数
    """

    def route(state: MultiAgentState) -> Sequence[str]:
        intent = state.get("intent", "pure_record") or "pure_record"
        worker_names = intent_routing.get(intent, intent_routing.get("pure_record", ["empathy"]))

        # 仅路由到已注册的 Worker 节点
        targets = []
        for name in worker_names:
            if name in registered_workers:
                targets.append(registered_workers[name])

        if not targets:
            # 没有匹配的 Worker，跳到 supervisor_synthesize
            logger.warning(
                "No registered workers match intent '%s'. Routing to supervisor_synthesize directly.",
                intent,
            )
            return ["supervisor_synthesize"]

        return targets

    return route


# ╔══════════════════════════════════════════════════════════════╗
# ║  MultiAgentGraph 构建器                                        ║
# ╚══════════════════════════════════════════════════════════════╝

class MultiAgentGraphBuilder:
    """
    LangGraph Multi-Agent 状态图构建器。

    支持动态注册 Worker Agent 节点，无需修改已有节点实现（Requirement 2.4）。

    用法：
        builder = MultiAgentGraphBuilder()
        builder.set_supervisor(classify_fn, synthesize_fn)
        builder.add_worker("empathy", empathy_execute)
        builder.add_worker("retrieval", retrieval_execute)
        builder.add_worker("insight", insight_execute)
        graph = builder.compile()

    Worker 节点函数签名：
        def worker_fn(state: MultiAgentState) -> dict:
            # 返回部分状态更新，仅包含该 Worker 修改的字段
            return {"empathy_response": "..."}
    """

    def __init__(self, intent_routing: Dict[str, List[str]] | None = None):
        """
        初始化构建器。

        :param intent_routing: 自定义 intent → worker_names 路由映射。
                               为 None 时使用 DEFAULT_INTENT_ROUTING。
        """
        self._intent_routing = intent_routing or DEFAULT_INTENT_ROUTING
        self._workers: Dict[str, WorkerNodeFn] = {}
        self._supervisor_classify: WorkerNodeFn | None = None
        self._supervisor_synthesize: WorkerNodeFn | None = None

    def set_supervisor(
        self,
        classify_fn: WorkerNodeFn,
        synthesize_fn: WorkerNodeFn,
    ) -> "MultiAgentGraphBuilder":
        """
        设置 Supervisor Agent 的分类和整合函数。

        :param classify_fn: 意图分类节点函数（接收 state，返回部分状态更新 dict）
        :param synthesize_fn: 结果整合节点函数
        :return: self（支持链式调用）
        """
        self._supervisor_classify = classify_fn
        self._supervisor_synthesize = synthesize_fn
        return self

    def add_worker(self, name: str, fn: WorkerNodeFn) -> "MultiAgentGraphBuilder":
        """
        注册一个 Worker Agent 节点。

        支持在不修改已有节点实现的情况下添加新 Worker（Requirement 2.4）。
        新增 Worker 只需调用 add_worker 并在 intent_routing 中配置即可。

        :param name: Worker 名称（对应 intent_routing 中的名称）
        :param fn: Worker 执行函数（接收 MultiAgentState，返回部分状态更新 dict）
        :return: self（支持链式调用）
        """
        self._workers[name] = fn
        return self

    def compile(self) -> StateGraph:
        """
        编译 LangGraph 状态图。

        图结构：
        1. supervisor_classify → 条件路由器
        2. 条件路由器 → 各 Worker 节点（并行分发）
        3. 各 Worker 节点 → supervisor_synthesize
        4. supervisor_synthesize → END

        满足 Requirement 2.3：Worker 完成后更新状态，再传递给下一个节点。
        满足 Requirement 2.4：支持添加新 Worker 无需修改已有节点。

        :return: 编译后的 CompiledStateGraph 可运行图
        :raises ValueError: 未设置 Supervisor 或无 Worker 注册时
        """
        if self._supervisor_classify is None or self._supervisor_synthesize is None:
            raise ValueError(
                "Supervisor not set. Call set_supervisor(classify_fn, synthesize_fn) first."
            )

        if not self._workers:
            raise ValueError("No workers registered. Call add_worker() at least once.")

        graph = StateGraph(MultiAgentState)

        # 添加 Supervisor 分类节点
        graph.add_node("supervisor_classify", self._supervisor_classify)

        # 添加 Worker 节点（包装为安全节点，捕获异常记录到 errors）
        registered_workers: Dict[str, str] = {}
        for name, fn in self._workers.items():
            node_name = f"{name}_agent"
            safe_fn = _make_safe_worker_node(name, fn)
            graph.add_node(node_name, safe_fn)
            registered_workers[name] = node_name

        # 添加 Supervisor Synthesize 节点
        graph.add_node("supervisor_synthesize", self._supervisor_synthesize)

        # 设置入口
        graph.set_entry_point("supervisor_classify")

        # 条件路由：supervisor_classify → workers（并行分发）
        route_fn = _build_route_function(registered_workers, self._intent_routing)

        # 所有可能的目标节点（workers + supervisor_synthesize 作为 fallback）
        all_targets = list(registered_workers.values()) + ["supervisor_synthesize"]
        conditional_map = {target: target for target in all_targets}

        graph.add_conditional_edges(
            "supervisor_classify",
            route_fn,
            conditional_map,
        )

        # Worker → supervisor_synthesize
        for node_name in registered_workers.values():
            graph.add_edge(node_name, "supervisor_synthesize")

        # supervisor_synthesize → END
        graph.add_edge("supervisor_synthesize", END)

        return graph.compile()
