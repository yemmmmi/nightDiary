"""
Insight Agent — 洞察分析 Worker Agent
=======================================

专注模式发现、趋势分析和行为建议的 Worker Agent。

核心功能：
1. 分析历史日记中的反复情绪主题和行为趋势
2. 生成具体可操作建议（非泛泛鼓励）
3. 将当前情绪与 Long_Term_Memory 中的 emotion_baseline 对比，检测显著偏离
4. 支持周报/月报结构化报告（主导情绪、关键事件、趋势方向、个性化建议）
5. 查询 Domain Knowledge Store 获取专业心理学知识

作为 LangGraph Worker 节点函数使用，返回 {"insight_response": "..."} 部分状态更新。

Requirements: 6.1, 6.2, 6.3, 6.4, 18.3
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.state import MultiAgentState, extract_token_usage
from app.core.database import SessionLocal
from app.feedback.prompt_tuner import build_dynamic_prompt_for_agent
from app.schemas.memory import EmotionBaseline

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量与配置                                                    ║
# ╚══════════════════════════════════════════════════════════════╝

# 情绪偏离检测阈值：当前情绪与基线差值超过此值视为显著偏离
EMOTION_DEVIATION_THRESHOLD = 0.3

# 周报/月报关键词检测
_REPORT_KEYWORDS_WEEKLY = ["周报", "这周", "本周", "一周", "过去七天", "过去7天", "weekly"]
_REPORT_KEYWORDS_MONTHLY = ["月报", "这个月", "本月", "一个月", "过去三十天", "过去30天", "monthly"]

# Insight Agent 系统提示词
_INSIGHT_SYSTEM_PROMPT = """你是一位专业的心理洞察分析师，擅长从日记中发现情绪模式和行为趋势。

你的职责：
1. 分析用户日记中反复出现的情绪主题和行为模式
2. 提供具体、可操作的建议（而非泛泛的鼓励如"加油"、"会好起来的"）
3. 当检测到情绪显著偏离基线时，温和地指出并提供应对策略
4. 引用专业心理学知识支撑你的建议

回应要求：
- 建议必须具体可执行（例如："尝试每天睡前写下3件感恩的事"而非"保持积极心态"）
- 语言温和但直接，避免说教
- 如果发现负面模式，先共情再给建议
- 控制回应在 200-400 字之间
"""

# 周报/月报系统提示词
_REPORT_SYSTEM_PROMPT = """你是一位专业的心理洞察分析师，正在为用户生成{report_type}。

请生成结构化报告，包含以下部分：
1. 📊 主导情绪：本{period}最突出的情绪状态
2. 📌 关键事件：影响情绪的重要事件（2-3个）
3. 📈 趋势方向：情绪变化趋势（上升/下降/波动/稳定）
4. 💡 个性化建议：基于分析的具体可操作建议（2-3条）

要求：
- 建议必须具体可执行，与用户实际情况相关
- 引用专业心理学知识支撑建议
- 语言温和、有洞察力
- 总长度控制在 300-500 字
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║  辅助函数                                                      ║
# ╚══════════════════════════════════════════════════════════════╝


def _detect_report_type(diary_content: str) -> Optional[str]:
    """
    检测用户是否请求周报或月报。

    Args:
        diary_content: 日记内容

    Returns:
        "weekly" | "monthly" | None
    """
    content_lower = diary_content.lower()
    for keyword in _REPORT_KEYWORDS_MONTHLY:
        if keyword in content_lower:
            return "monthly"
    for keyword in _REPORT_KEYWORDS_WEEKLY:
        if keyword in content_lower:
            return "weekly"
    return None


def _detect_emotion_deviation(
    diary_content: str,
    emotion_baseline: EmotionBaseline,
    episodic_context: List[dict],
) -> Optional[Dict[str, Any]]:
    """
    检测当前情绪与基线的显著偏离。

    通过分析日记内容中的情绪信号和近期情景记忆，
    与 emotion_baseline 中的 average_sentiment 对比。

    Args:
        diary_content: 当前日记内容
        emotion_baseline: 用户情绪基线
        episodic_context: 近期情景记忆条目

    Returns:
        偏离信息 dict 或 None（无显著偏离时）
        {"direction": "lower"|"higher", "magnitude": float, "baseline_avg": float}
    """
    if not episodic_context:
        return None

    # 从近期情景记忆中提取情绪信号
    recent_emotions = []
    for entry in episodic_context:
        importance = entry.get("importance", 0.5)
        emotion = entry.get("emotion", "")
        # 简单情绪极性映射
        if emotion in ("焦虑", "悲伤", "愤怒", "沮丧", "失落", "压力", "疲惫", "孤独"):
            recent_emotions.append(-0.6 * importance)
        elif emotion in ("开心", "满足", "兴奋", "感恩", "平静", "希望", "自信"):
            recent_emotions.append(0.6 * importance)
        else:
            recent_emotions.append(0.0)

    if not recent_emotions:
        return None

    # 计算近期情绪均值
    recent_avg = sum(recent_emotions) / len(recent_emotions)
    baseline_avg = emotion_baseline.average_sentiment

    deviation = recent_avg - baseline_avg
    if abs(deviation) >= EMOTION_DEVIATION_THRESHOLD:
        return {
            "direction": "lower" if deviation < 0 else "higher",
            "magnitude": abs(deviation),
            "baseline_avg": baseline_avg,
            "recent_avg": recent_avg,
        }

    return None


def _build_context_summary(
    retrieval_context: str,
    episodic_context: List[dict],
    long_term_profile: dict,
) -> str:
    """
    构建供 LLM 分析的上下文摘要。

    整合检索到的历史日记、情景记忆和用户画像信息。

    Args:
        retrieval_context: Retrieval Agent 提供的历史日记摘要
        episodic_context: 情景记忆条目列表
        long_term_profile: 用户长期画像

    Returns:
        格式化的上下文字符串
    """
    parts = []

    # 历史日记检索结果
    if retrieval_context:
        parts.append(f"【历史日记摘要】\n{retrieval_context}")

    # 情景记忆
    if episodic_context:
        memory_lines = []
        for entry in episodic_context[:5]:  # 最多取 5 条
            event = entry.get("event", "")
            emotion = entry.get("emotion", "")
            suggestion = entry.get("ai_suggestion", "")
            if event:
                line = f"- {event}"
                if emotion:
                    line += f"（情绪: {emotion}）"
                if suggestion:
                    line += f" → 建议: {suggestion}"
                memory_lines.append(line)
        if memory_lines:
            parts.append("【近期重要记忆】\n" + "\n".join(memory_lines))

    # 用户画像关键信息
    if long_term_profile:
        profile_parts = []
        recurring_topics = long_term_profile.get("recurring_topics", [])
        if recurring_topics:
            profile_parts.append(f"反复话题: {', '.join(recurring_topics[:5])}")

        personality_tags = long_term_profile.get("personality_tags", [])
        if personality_tags:
            profile_parts.append(f"性格特征: {', '.join(personality_tags[:5])}")

        emotion_baseline = long_term_profile.get("emotion_baseline", {})
        if emotion_baseline:
            dominant = emotion_baseline.get("dominant_emotion", "")
            if dominant:
                profile_parts.append(f"主导情绪: {dominant}")

        if profile_parts:
            parts.append("【用户画像】\n" + "\n".join(profile_parts))

    return "\n\n".join(parts) if parts else "（暂无历史上下文）"


def _query_domain_knowledge(query: str) -> str:
    """
    查询心理学领域知识库（Domain Knowledge Store）。

    从 Chroma 共享集合 "domain_knowledge_psychology" 中检索相关专业知识。
    每次最多返回 2 条相关条目。

    如果 Domain Knowledge Store 不可用，优雅降级返回空字符串。

    Args:
        query: 查询文本

    Returns:
        格式化的专业知识参考文本，或空字符串
    """
    try:
        import chromadb

        # 尝试连接 Chroma 并查询领域知识
        chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        client = chromadb.PersistentClient(path=chroma_persist_dir)

        try:
            collection = client.get_collection("domain_knowledge_psychology")
        except Exception:
            # 集合不存在，降级
            logger.debug("Domain Knowledge Store 集合不存在，跳过知识查询")
            return ""

        results = collection.query(
            query_texts=[query],
            n_results=2,
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return ""

        # 格式化知识条目
        knowledge_parts = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = {}
            if results.get("metadatas") and results["metadatas"][0]:
                metadata = results["metadatas"][0][i] if i < len(results["metadatas"][0]) else {}
            topic = metadata.get("topic", "")
            prefix = f"[{topic}] " if topic else ""
            knowledge_parts.append(f"{prefix}{doc}")

        if knowledge_parts:
            return "【专业知识参考】\n" + "\n".join(knowledge_parts)
        return ""

    except Exception as e:
        logger.debug("Domain Knowledge Store 查询失败，降级跳过: %s", e)
        return ""


def _build_llm() -> ChatOpenAI:
    """
    构建 Insight Agent 使用的 LLM 实例。

    使用与 AIService 相同的配置来源（环境变量）。
    """
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("Insight Agent: LLM_API_KEY 未配置")

    kwargs = {
        "api_key": api_key,
        "model": model,
        "temperature": 0.6,
        "max_tokens": 500,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Insight Agent 主函数（LangGraph Worker 节点）                   ║
# ╚══════════════════════════════════════════════════════════════╝


def insight_agent(state: MultiAgentState) -> dict:
    """
    Insight Agent Worker 节点函数。

    分析历史日记中的情绪模式和行为趋势，生成可操作建议。
    支持周报/月报结构化报告。

    作为 LangGraph Worker 节点使用：
        builder.add_worker("insight", insight_agent)

    Args:
        state: MultiAgentState 共享状态

    Returns:
        部分状态更新 dict: {"insight_response": "..."}

    Requirements: 6.1, 6.2, 6.3, 6.4, 18.3
    """
    diary_content = state.get("diary_content", "")
    user_id = state.get("user_id", 0)
    retrieval_context = state.get("retrieval_context", "")
    episodic_context = state.get("episodic_context", [])
    long_term_profile = state.get("long_term_profile", {})

    logger.info("Insight Agent 开始执行 (user_id=%d)", user_id)

    # 1. 检测是否为周报/月报请求
    report_type = _detect_report_type(diary_content)

    # 2. 解析 emotion_baseline
    emotion_baseline_data = long_term_profile.get("emotion_baseline", {})
    emotion_baseline = EmotionBaseline(
        average_sentiment=emotion_baseline_data.get("average_sentiment", 0.0),
        volatility=emotion_baseline_data.get("volatility", 0.0),
        dominant_emotion=emotion_baseline_data.get("dominant_emotion", "neutral"),
    )

    # 3. 检测情绪偏离
    deviation = _detect_emotion_deviation(diary_content, emotion_baseline, episodic_context)

    # 4. 构建上下文摘要
    context_summary = _build_context_summary(
        retrieval_context, episodic_context, long_term_profile
    )

    # 5. 查询领域知识库（Requirement 18.3）
    knowledge_query = diary_content[:100]  # 用日记前 100 字作为查询
    domain_knowledge = _query_domain_knowledge(knowledge_query)

    # 6. 构建 LLM 提示
    if report_type:
        # 周报/月报模式
        period = "周" if report_type == "weekly" else "月"
        report_type_label = "周报" if report_type == "weekly" else "月报"
        system_prompt = _REPORT_SYSTEM_PROMPT.format(
            report_type=report_type_label, period=period
        )
    else:
        # 常规洞察分析模式
        system_prompt = _INSIGHT_SYSTEM_PROMPT

    # 6.5 注入 PromptTuner 动态偏好片段
    # Requirements: 13.1, 13.2, 13.3
    # 每次请求实时从数据库读取偏好，偏好变化下次请求立即生效
    if user_id:
        try:
            db = SessionLocal()
            try:
                dynamic_fragment = build_dynamic_prompt_for_agent(db, user_id, "insight")
                system_prompt = system_prompt + "\n" + dynamic_fragment
            finally:
                db.close()
        except Exception as e:
            logger.warning("PromptTuner 动态 Prompt 注入失败，使用基础 Prompt: %s", e)

    # 构建用户消息
    user_message_parts = [f"【当前日记】\n{diary_content}"]

    if context_summary:
        user_message_parts.append(context_summary)

    if domain_knowledge:
        user_message_parts.append(domain_knowledge)

    if deviation:
        direction_text = "低于" if deviation["direction"] == "lower" else "高于"
        user_message_parts.append(
            f"【情绪偏离提醒】\n"
            f"用户近期情绪显著{direction_text}其历史基线 "
            f"(偏离幅度: {deviation['magnitude']:.2f})。"
            f"请在分析中温和地指出这一变化，并提供应对策略。"
        )

    user_message = "\n\n".join(user_message_parts)

    # 7. 调用 LLM 生成洞察
    try:
        llm = _build_llm()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        response = llm.invoke(messages)
        insight_text = response.content.strip()

        # 提取 token 消耗
        token_usage = extract_token_usage(response)

        logger.info(
            "Insight Agent 完成 (user_id=%d, report_type=%s, deviation=%s, tokens=%d)",
            user_id,
            report_type or "none",
            "detected" if deviation else "none",
            token_usage["total_tokens_used"],
        )

        return {
            "insight_response": insight_text,
            **token_usage,
        }

    except Exception as e:
        error_msg = f"Insight Agent LLM 调用失败: {type(e).__name__}: {e}"
        logger.error(error_msg)
        # 返回降级响应而非抛出异常，让 graph 的 safe_worker_node 处理
        return {
            "insight_response": "",
            "errors": [error_msg],
        }


__all__ = ["insight_agent"]
