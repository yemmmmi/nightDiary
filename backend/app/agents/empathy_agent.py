"""
Empathy Agent — 情感陪伴 Worker Agent
======================================

专注情感共鸣、心理支持和危机识别的 Worker Agent。
作为 LangGraph 状态图中的 Worker 节点运行。

功能：
- 生成确认用户情绪状态的回应，使用 Long_Term_Memory 中的 preferred_response_style
- 极端负面情绪（情感分数 < -0.7）触发危机响应路径
- 整合 Episodic_Memory 上下文体现关怀连续性
- 回应长度控制：pure_record 50-150 汉字，emotional_support 100-300 汉字
- 查询 Domain Knowledge Store 获取专业心理学知识

Requirements: 5.1, 5.2, 5.3, 5.4, 18.3
"""

import logging
import os
from typing import Optional

from langchain_openai import ChatOpenAI

from app.agents.state import MultiAgentState, extract_token_usage
from app.core.database import SessionLocal
from app.feedback.prompt_tuner import build_dynamic_prompt_for_agent

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量定义                                                     ║
# ╚══════════════════════════════════════════════════════════════╝

# 极端负面情绪阈值
CRISIS_EMOTION_THRESHOLD = -0.7

# 回应长度限制（汉字数）
RESPONSE_LENGTH = {
    "pure_record": {"min": 50, "max": 150},
    "emotional_support": {"min": 100, "max": 300},
    "retrospective_review": {"min": 100, "max": 300},
    "habit_tracking": {"min": 50, "max": 150},
}

# 危机响应支持资源
CRISIS_RESOURCES = (
    "如果你正在经历极度痛苦，请记住你并不孤单。"
    "以下资源可以提供帮助：\n"
    "• 全国心理援助热线：400-161-9995\n"
    "• 北京心理危机研究与干预中心：010-82951332\n"
    "• 生命热线：400-821-1215\n"
    "请不要独自承受，寻求专业帮助是勇敢的选择。"
)

# Domain Knowledge Store 集合名称
DOMAIN_KNOWLEDGE_COLLECTION = "domain_knowledge_psychology"


# ╔══════════════════════════════════════════════════════════════╗
# ║  Domain Knowledge Store 查询                                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _query_domain_knowledge(query: str, top_k: int = 2) -> str:
    """
    查询心理学领域知识库，获取专业知识参考。

    从共享的 Chroma 集合 domain_knowledge_psychology 中检索相关条目。
    每次最多返回 2 条，避免信息过载。
    查询失败时优雅降级，返回空字符串。

    Requirements: 18.3, 18.4
    """
    try:
        import chromadb

        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        client = chromadb.PersistentClient(path=persist_dir)

        # 尝试获取领域知识集合（只读）
        try:
            collection = client.get_collection(name=DOMAIN_KNOWLEDGE_COLLECTION)
        except Exception:
            # 集合不存在时静默降级
            logger.debug("Domain Knowledge Store 集合不存在，跳过知识查询")
            return ""

        if collection.count() == 0:
            return ""

        n_results = min(top_k, collection.count())
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas"],
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return ""

        # 格式化知识条目
        knowledge_parts = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            category = meta.get("category", "")
            topic = meta.get("topic", "")
            prefix = f"[{category}/{topic}]" if category else ""
            knowledge_parts.append(f"{prefix} {doc}")

        return "\n".join(knowledge_parts)

    except Exception as e:
        logger.warning("Domain Knowledge Store 查询失败，降级跳过: %s", e)
        return ""


# ╔══════════════════════════════════════════════════════════════╗
# ║  情绪分数提取                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _extract_emotion_score(state: MultiAgentState) -> float:
    """
    从状态中提取情绪分数。

    优先从 long_term_profile 的 emotion_baseline 获取，
    若不可用则返回中性值 0.0。
    """
    profile = state.get("long_term_profile", {})
    if not profile:
        return 0.0

    emotion_baseline = profile.get("emotion_baseline", {})
    if isinstance(emotion_baseline, dict):
        return emotion_baseline.get("average_sentiment", 0.0)

    return 0.0


def _estimate_emotion_from_content(content: str) -> float:
    """
    基于日记内容的关键词快速估算情绪分数。

    这是一个轻量级的启发式方法，用于在没有 LLM 情感分析结果时
    快速判断是否需要触发危机响应。

    返回值范围 [-1.0, 1.0]，负值表示负面情绪。
    """
    if not content:
        return 0.0

    # 极端负面关键词（权重高）
    severe_negative = [
        "想死", "不想活", "自杀", "结束生命", "活着没意思",
        "绝望", "崩溃", "撑不下去", "没有希望", "生不如死",
        "伤害自己", "自残", "割腕", "跳楼",
    ]

    # 一般负面关键词
    negative = [
        "难过", "痛苦", "焦虑", "抑郁", "孤独", "害怕",
        "愤怒", "失望", "无助", "悲伤", "压抑", "烦躁",
        "失眠", "哭", "崩溃", "受不了", "太累了",
    ]

    # 正面关键词
    positive = [
        "开心", "快乐", "幸福", "感恩", "满足", "期待",
        "兴奋", "温暖", "感动", "自豪", "放松", "愉快",
    ]

    score = 0.0

    for word in severe_negative:
        if word in content:
            score -= 0.4  # 每个极端负面词大幅降低分数

    for word in negative:
        if word in content:
            score -= 0.15

    for word in positive:
        if word in content:
            score += 0.15

    # 限制在 [-1.0, 1.0] 范围内
    return max(-1.0, min(1.0, score))


# ╔══════════════════════════════════════════════════════════════╗
# ║  Prompt 构建                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _build_empathy_prompt(
    diary_content: str,
    intent: str,
    preferred_style: str,
    episodic_context: str,
    domain_knowledge: str,
    is_crisis: bool,
) -> str:
    """
    构建 Empathy Agent 的系统提示词。

    根据意图类型、用户偏好风格、情景记忆上下文和领域知识
    动态生成提示词。
    """
    # 确定回应长度要求
    length_config = RESPONSE_LENGTH.get(intent, RESPONSE_LENGTH["pure_record"])
    min_len = length_config["min"]
    max_len = length_config["max"]

    # 风格映射
    style_instructions = {
        "empathetic": "温暖共情、理解接纳，让用户感受到被理解和支持",
        "practical": "务实关怀、给出具体可操作的建议，同时表达理解",
        "philosophical": "富有哲思、引导用户从更宏观的角度看待当下，同时保持温暖",
        "humorous": "轻松幽默、用温和的方式化解情绪，但不轻视用户的感受",
    }
    style_desc = style_instructions.get(preferred_style, style_instructions["empathetic"])

    # 基础系统提示
    system_parts = [
        "你是「夜记助手」的情感陪伴模块，专注于理解和回应用户的情绪状态。",
        f"\n## 回应风格\n{style_desc}",
        f"\n## 回应长度\n请将回应控制在 {min_len}-{max_len} 个汉字之间。",
    ]

    # 危机响应模式
    if is_crisis:
        system_parts.append(
            "\n## ⚠️ 危机响应模式\n"
            "检测到用户可能正在经历极度痛苦。请：\n"
            "1. 首先表达真诚的关心和理解\n"
            "2. 明确告诉用户他们的感受是被接纳的\n"
            "3. 温和地提供专业支持资源\n"
            "4. 绝对不要使用轻视性语言（如「想开点」「没什么大不了」）\n"
            "5. 不要试图快速解决问题，而是陪伴和倾听"
        )

    # 情景记忆上下文（体现关怀连续性）
    if episodic_context:
        system_parts.append(
            f"\n## 之前的交互记忆\n"
            f"以下是与用户之前的重要交互记录，请在相关时自然地引用，"
            f"体现你对用户的持续关注和记忆：\n{episodic_context}"
        )

    # 领域知识参考
    if domain_knowledge:
        system_parts.append(
            f"\n## 专业知识参考（通用知识，非针对用户的诊断）\n"
            f"以下心理学知识可供参考，如果引用请标注为通用知识参考：\n{domain_knowledge}"
        )

    # 通用指导
    system_parts.append(
        "\n## 注意事项\n"
        "- 确认用户的情绪状态，让他们感到被看见\n"
        "- 避免说教或给出过于笼统的建议\n"
        "- 使用中文回应\n"
        "- 不要使用 markdown 格式"
    )

    return "\n".join(system_parts)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Empathy Agent 主函数                                         ║
# ╚══════════════════════════════════════════════════════════════╝

def _format_episodic_context(episodic_entries: list) -> str:
    """
    将情景记忆条目格式化为可读的上下文文本。

    Requirements: 5.3
    """
    if not episodic_entries:
        return ""

    lines = []
    for entry in episodic_entries[:5]:  # 最多使用 5 条
        if isinstance(entry, dict):
            event = entry.get("event", "")
            emotion = entry.get("emotion", "")
            suggestion = entry.get("ai_suggestion", "")
            feedback = entry.get("user_feedback", "none")

            parts = []
            if event:
                parts.append(f"事件：{event}")
            if emotion:
                parts.append(f"情绪：{emotion}")
            if suggestion:
                parts.append(f"当时的建议：{suggestion}")
            if feedback and feedback != "none":
                parts.append(f"用户反馈：{feedback}")

            if parts:
                lines.append("• " + "；".join(parts))

    return "\n".join(lines)


def _get_llm() -> ChatOpenAI:
    """
    获取 LLM 实例用于生成共情回应。

    优先使用用户配置的模型，回退到系统默认配置。
    """
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("LLM API Key 未配置，无法生成共情回应")

    kwargs = {
        "api_key": api_key,
        "model": model,
        "temperature": 0.8,  # 稍高温度增加共情表达的多样性
        "max_tokens": 500,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)


def empathy_agent_node(state: MultiAgentState) -> dict:
    """
    Empathy Agent Worker 节点函数。

    作为 LangGraph 状态图中的 Worker 节点运行。
    接收 MultiAgentState，返回部分状态更新 dict。

    流程：
    1. 从 state 提取日记内容、意图、用户画像和情景记忆
    2. 估算情绪分数，判断是否触发危机响应
    3. 查询 Domain Knowledge Store 获取相关心理学知识
    4. 构建动态 Prompt 并调用 LLM 生成共情回应
    5. 危机模式下附加支持资源信息

    Requirements: 5.1, 5.2, 5.3, 5.4, 18.3

    :param state: LangGraph 共享状态
    :return: 部分状态更新 {"empathy_response": str}
    """
    diary_content = state.get("diary_content", "")
    intent = state.get("intent", "pure_record")
    long_term_profile = state.get("long_term_profile", {})
    episodic_context_entries = state.get("episodic_context", [])

    logger.info(
        "Empathy Agent 开始执行 (intent=%s, user_id=%s)",
        intent, state.get("user_id"),
    )

    # ── Step 1: 获取用户偏好回应风格 ──
    # Requirements: 5.1
    preferred_style = "empathetic"  # 默认共情型
    if long_term_profile and isinstance(long_term_profile, dict):
        preferred_style = long_term_profile.get(
            "preferred_response_style", "empathetic"
        )

    # ── Step 2: 情绪评估与危机检测 ──
    # Requirements: 5.2
    # 综合使用画像基线和内容关键词估算情绪
    baseline_score = _extract_emotion_score(state)
    content_score = _estimate_emotion_from_content(diary_content)

    # 取两者中更负面的值作为最终情绪评估
    emotion_score = min(baseline_score, content_score) if content_score < 0 else content_score
    is_crisis = emotion_score < CRISIS_EMOTION_THRESHOLD

    if is_crisis:
        logger.warning(
            "Empathy Agent 检测到极端负面情绪 (score=%.2f, user_id=%s)，触发危机响应",
            emotion_score, state.get("user_id"),
        )

    # ── Step 3: 格式化情景记忆上下文 ──
    # Requirements: 5.3
    episodic_text = _format_episodic_context(episodic_context_entries)

    # ── Step 4: 查询 Domain Knowledge Store ──
    # Requirements: 18.3
    domain_knowledge = ""
    if intent in ("emotional_support", "retrospective_review") or is_crisis:
        # 仅在需要情感支持或危机时查询领域知识
        query_text = diary_content[:200]  # 使用日记前 200 字作为查询
        domain_knowledge = _query_domain_knowledge(query_text)

    # ── Step 5: 构建 Prompt 并调用 LLM ──
    system_prompt = _build_empathy_prompt(
        diary_content=diary_content,
        intent=intent,
        preferred_style=preferred_style,
        episodic_context=episodic_text,
        domain_knowledge=domain_knowledge,
        is_crisis=is_crisis,
    )

    # ── Step 5.5: 注入 PromptTuner 动态偏好片段 ──
    # Requirements: 13.1, 13.2, 13.3
    # 每次请求实时从数据库读取偏好，偏好变化下次请求立即生效
    user_id = state.get("user_id")
    if user_id:
        try:
            db = SessionLocal()
            try:
                dynamic_fragment = build_dynamic_prompt_for_agent(db, user_id, "empathy")
                system_prompt = system_prompt + "\n" + dynamic_fragment
            finally:
                db.close()
        except Exception as e:
            logger.warning("PromptTuner 动态 Prompt 注入失败，使用基础 Prompt: %s", e)

    try:
        llm = _get_llm()

        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "日记内容：{diary_content}\n\n请给予温暖的回应。"),
        ])

        chain = prompt | llm
        response = chain.invoke({"diary_content": diary_content})

        empathy_response = response.content if hasattr(response, "content") else str(response)

        # 提取 token 消耗
        token_usage = extract_token_usage(response)

        # ── Step 6: 危机模式附加支持资源 ──
        # Requirements: 5.2
        if is_crisis:
            empathy_response = empathy_response + "\n\n" + CRISIS_RESOURCES

        logger.info(
            "Empathy Agent 完成 (intent=%s, crisis=%s, response_len=%d, tokens=%d)",
            intent, is_crisis, len(empathy_response), token_usage["total_tokens_used"],
        )

        return {
            "empathy_response": empathy_response,
            **token_usage,
        }

    except Exception as e:
        logger.error("Empathy Agent LLM 调用失败: %s", e)
        # 降级回应：提供基本的共情文本
        fallback = _generate_fallback_response(intent, is_crisis)
        return {"empathy_response": fallback}


def _generate_fallback_response(intent: str, is_crisis: bool) -> str:
    """
    LLM 不可用时的降级回应。

    提供基本的共情文本，确保用户不会收到空回应。
    """
    if is_crisis:
        return (
            "我注意到你现在可能正在经历很大的痛苦，我想让你知道，"
            "你的感受是真实的，你不需要独自面对这一切。"
            "\n\n" + CRISIS_RESOURCES
        )

    fallback_responses = {
        "pure_record": "感谢你今天的记录，每一天的书写都是对自己的关照。",
        "emotional_support": (
            "谢谢你愿意把这些写下来。我能感受到你此刻的心情，"
            "无论是什么样的情绪，都值得被看见和接纳。"
            "希望书写本身能给你带来一些释放。"
        ),
        "retrospective_review": (
            "回顾过去需要勇气，感谢你愿意面对这些经历。"
            "每一次回顾都是成长的机会。"
        ),
        "habit_tracking": "坚持记录本身就是一种很好的习惯，为你的坚持点赞。",
    }

    return fallback_responses.get(intent, fallback_responses["pure_record"])


__all__ = ["empathy_agent_node"]
