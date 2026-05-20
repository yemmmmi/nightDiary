"""
Supervisor Agent — 协调者节点
================================

负责意图识别、Token 预算分配、Worker 调度和结果整合。

核心职责：
1. classify_intent(): 调用 IntentClassifier 分类意图，分配 Token 预算
2. synthesize_response(): 整合多个 Worker 输出为统一连贯回应
3. Worker 失败时使用已成功的 Agent 输出生成回应（降级策略）

Token 预算分配策略：
| Intent               | Total Budget |
|----------------------|-------------|
| pure_record          | 400-600     |
| emotional_support    | 1000-1500   |
| retrospective_review | 1500-2500   |
| habit_tracking       | 1200-2000   |

Requirements: 1.1, 1.6, 1.7, 3.1, 3.3, 23.2
"""

import logging
from typing import Optional

from langchain_openai import ChatOpenAI

from app.agents.intent_classifier import IntentClassifier
from app.agents.state import MultiAgentState, extract_token_usage

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Token 预算配置                                                ║
# ╚══════════════════════════════════════════════════════════════╝

# 各 intent 类型的 Token 预算范围 (min, max)
TOKEN_BUDGET_MAP = {
    "pure_record": (400, 600),
    "emotional_support": (1000, 1500),
    "retrospective_review": (1500, 2500),
    "habit_tracking": (1200, 2000),
}

# 默认预算（未知 intent 时使用中间值）
DEFAULT_TOKEN_BUDGET = 800

# Supervisor 自身分类消耗的 Token 上限
SUPERVISOR_CLASSIFY_TOKEN_LIMIT = 100


# ╔══════════════════════════════════════════════════════════════╗
# ║  预算分配辅助函数                                               ║
# ╚══════════════════════════════════════════════════════════════╝

def allocate_token_budget(intent: str) -> int:
    """
    根据 intent 类型分配 Token 预算。

    使用范围的中间值作为默认分配。实际运行中可根据上下文复杂度
    在范围内动态调整。

    :param intent: 意图类别 (pure_record | emotional_support | retrospective_review | habit_tracking)
    :return: 分配的 Token 预算
    """
    budget_range = TOKEN_BUDGET_MAP.get(intent)
    if budget_range is None:
        logger.warning("Unknown intent '%s', using default budget %d", intent, DEFAULT_TOKEN_BUDGET)
        return DEFAULT_TOKEN_BUDGET

    # 使用范围中间值
    min_budget, max_budget = budget_range
    return (min_budget + max_budget) // 2


def get_budget_range(intent: str) -> tuple:
    """
    获取 intent 对应的 Token 预算范围。

    :param intent: 意图类别
    :return: (min_budget, max_budget) 元组
    """
    return TOKEN_BUDGET_MAP.get(intent, (DEFAULT_TOKEN_BUDGET, DEFAULT_TOKEN_BUDGET))


# ╔══════════════════════════════════════════════════════════════╗
# ║  Supervisor Agent 类                                           ║
# ╚══════════════════════════════════════════════════════════════╝

class SupervisorAgent:
    """
    协调者节点：意图识别 + Token 预算分配 + 结果整合。

    作为 LangGraph 状态图中的两个节点函数使用：
    - classify_intent: 入口节点，完成意图分类和预算分配
    - synthesize_response: 出口节点，整合 Worker 输出为最终回应

    用法：
        supervisor = SupervisorAgent(llm=llm)
        builder.set_supervisor(supervisor.classify_intent, supervisor.synthesize_response)
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        初始化 Supervisor Agent。

        :param llm: LLM 实例，用于意图分类（LLM 层）和结果整合。
                    为 None 时意图分类仅使用规则层，结果整合使用简单拼接。
        """
        self._llm = llm
        self._intent_classifier = IntentClassifier(llm=llm)

    def classify_intent(self, state: MultiAgentState) -> dict:
        """
        意图分类节点函数。

        流程：
        1. 调用 IntentClassifier 对日记内容进行意图分类
        2. 根据分类结果分配 Token 预算
        3. 确定需要激活的 Worker Agent 列表

        单次 LLM 调用完成分类，输出 Token ≤ 100（Requirement 1.6）。

        :param state: MultiAgentState 当前状态
        :return: 部分状态更新 dict，包含 intent, token_budget, activated_agents
        """
        diary_content = state.get("diary_content", "")

        # 调用 IntentClassifier 进行分类
        try:
            intent_result = self._intent_classifier.classify(diary_content)
            intent_category = intent_result.intent_category or "pure_record"
        except Exception as exc:
            logger.error("IntentClassifier 调用失败，降级为 pure_record: %s", exc)
            intent_category = "pure_record"

        # 分配 Token 预算
        token_budget = allocate_token_budget(intent_category)

        # 确定激活的 Worker Agent 列表
        activated_agents = self._determine_activated_agents(intent_category)

        logger.info(
            "Supervisor classify_intent: intent=%s, budget=%d, agents=%s",
            intent_category, token_budget, activated_agents,
        )

        return {
            "intent": intent_category,
            "token_budget": token_budget,
            "activated_agents": activated_agents,
        }

    def synthesize_response(self, state: MultiAgentState) -> dict:
        """
        结果整合节点函数。

        整合多个 Worker Agent 的输出为统一连贯回应（Requirement 1.7）。
        Worker 失败时使用已成功的 Agent 输出生成回应（Requirement 23.2）。

        整合策略：
        - 如果有 LLM 可用：调用 LLM 将多个 Worker 输出融合为自然连贯的回应
        - 如果无 LLM：按优先级拼接各 Worker 输出

        :param state: MultiAgentState 当前状态（包含各 Worker 的输出）
        :return: 部分状态更新 dict，包含 final_response, agent_mode
        """
        # 收集已成功的 Worker 输出
        worker_outputs = self._collect_worker_outputs(state)
        errors = state.get("errors", [])

        if errors:
            logger.warning(
                "Supervisor synthesize: %d worker(s) failed, using %d successful outputs. Errors: %s",
                len(errors), len(worker_outputs), errors,
            )

        # 如果没有任何成功的输出，返回降级回应
        if not worker_outputs:
            logger.error("All workers failed, returning fallback response.")
            return {
                "final_response": _FALLBACK_RESPONSE,
                "agent_mode": "multi_agent",
            }

        # 整合输出
        if self._llm is not None and len(worker_outputs) > 1:
            final_response, token_usage = self._llm_synthesize(worker_outputs, state)
        else:
            final_response = self._simple_synthesize(worker_outputs)
            token_usage = {}

        result = {
            "final_response": final_response,
            "agent_mode": "multi_agent",
        }
        # 将 synthesize 的 token 消耗也累加到 state
        if token_usage:
            result.update(token_usage)

        return result

    # ──────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────

    def _determine_activated_agents(self, intent: str) -> list:
        """
        根据 intent 确定需要激活的 Worker Agent 列表。

        路由规则（Requirement 1.2-1.5）：
        - pure_record: 仅 Empathy
        - emotional_support: Empathy + Retrieval（可选）
        - retrospective_review: Empathy + Retrieval + Insight（并发）
        - habit_tracking: Retrieval + Insight

        :param intent: 意图类别
        :return: 激活的 Agent 名称列表
        """
        routing = {
            "pure_record": ["empathy"],
            "emotional_support": ["empathy", "retrieval"],
            "retrospective_review": ["empathy", "retrieval", "insight"],
            "habit_tracking": ["retrieval", "insight"],
        }
        return routing.get(intent, ["empathy"])

    def _collect_worker_outputs(self, state: MultiAgentState) -> dict:
        """
        从 state 中收集已成功的 Worker 输出。

        仅收集非空的输出字段，跳过失败的 Worker。

        :param state: 当前状态
        :return: {worker_name: output_text} 字典
        """
        outputs = {}

        retrieval_context = state.get("retrieval_context", "")
        if retrieval_context and retrieval_context.strip():
            outputs["retrieval"] = retrieval_context.strip()

        empathy_response = state.get("empathy_response", "")
        if empathy_response and empathy_response.strip():
            outputs["empathy"] = empathy_response.strip()

        insight_response = state.get("insight_response", "")
        if insight_response and insight_response.strip():
            outputs["insight"] = insight_response.strip()

        return outputs

    def _llm_synthesize(self, worker_outputs: dict, state: MultiAgentState) -> tuple:
        """
        使用 LLM 将多个 Worker 输出整合为统一连贯回应。

        :param worker_outputs: {worker_name: output_text} 字典
        :param state: 当前状态（用于获取上下文信息）
        :return: (整合后的回应文本, token_usage dict)
        """
        # 构建整合 prompt
        outputs_text = ""
        for name, output in worker_outputs.items():
            label = _WORKER_LABELS.get(name, name)
            outputs_text += f"【{label}】\n{output}\n\n"

        intent = state.get("intent", "pure_record")
        token_budget = state.get("token_budget", 800)

        # 计算整合回应的目标长度（扣除已消耗的 Token）
        # 整合回应应控制在合理范围内
        max_response_chars = min(300, token_budget // 3)

        prompt = _SYNTHESIZE_PROMPT.format(
            intent=intent,
            outputs_text=outputs_text,
            max_chars=max_response_chars,
        )

        try:
            response = self._llm.invoke(prompt)
            result = response.content if hasattr(response, "content") else str(response)
            token_usage = extract_token_usage(response)
            return result.strip(), token_usage
        except Exception as exc:
            logger.warning("LLM 整合失败，回退简单拼接: %s", exc)
            return self._simple_synthesize(worker_outputs), {}

    def _simple_synthesize(self, worker_outputs: dict) -> str:
        """
        简单拼接策略：按优先级顺序拼接各 Worker 输出。

        优先级：empathy > insight > retrieval
        （情感回应最重要，洞察次之，检索上下文作为补充）

        :param worker_outputs: {worker_name: output_text} 字典
        :return: 拼接后的回应文本
        """
        parts = []

        # 按优先级顺序拼接
        priority_order = ["empathy", "insight", "retrieval"]
        for name in priority_order:
            if name in worker_outputs:
                parts.append(worker_outputs[name])

        # 如果有未在优先级列表中的输出，追加到末尾
        for name, output in worker_outputs.items():
            if name not in priority_order:
                parts.append(output)

        if not parts:
            return _FALLBACK_RESPONSE

        # 单个输出直接返回
        if len(parts) == 1:
            return parts[0]

        # 多个输出用换行分隔
        return "\n\n".join(parts)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量与 Prompt 模板                                            ║
# ╚══════════════════════════════════════════════════════════════╝

# Worker 名称到中文标签的映射
_WORKER_LABELS = {
    "retrieval": "历史参考",
    "empathy": "情感回应",
    "insight": "洞察分析",
}

# 所有 Worker 失败时的降级回应
_FALLBACK_RESPONSE = (
    "感谢你今天的记录！坚持写日记是一件很棒的事，"
    "每一天的记录都是珍贵的回忆。继续加油，期待明天的故事！"
)

# LLM 整合 Prompt
_SYNTHESIZE_PROMPT = """你是"夜记助手"的回应整合器。请将以下多个分析模块的输出整合为一个统一、连贯、自然的回应。

用户意图类型：{intent}

各模块输出：
{outputs_text}

整合要求：
1. 将各模块输出融合为一段自然流畅的中文回应，不要出现模块分隔标记
2. 情感回应部分应作为主体，洞察和历史参考作为补充自然融入
3. 保持温暖、支持性的语调
4. 回应长度控制在 {max_chars} 字以内
5. 不要重复相同的信息
6. 不要使用"根据分析"、"综合来看"等机械化表达

请直接输出整合后的回应，不要添加任何前缀或解释："""


# ╔══════════════════════════════════════════════════════════════╗
# ║  便捷工厂函数                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

def create_supervisor(llm: Optional[ChatOpenAI] = None) -> SupervisorAgent:
    """
    创建 SupervisorAgent 实例的工厂函数。

    :param llm: LLM 实例，为 None 时仅使用规则层分类和简单拼接整合
    :return: SupervisorAgent 实例
    """
    return SupervisorAgent(llm=llm)


__all__ = [
    "SupervisorAgent",
    "create_supervisor",
    "allocate_token_budget",
    "get_budget_range",
    "TOKEN_BUDGET_MAP",
    "SUPERVISOR_CLASSIFY_TOKEN_LIMIT",
]
