"""
ContextCompressor — 智能上下文压缩器
======================================

替代固定 7 天窗口策略，基于语义相关性动态选择历史上下文。

核心逻辑：
1. 合并 Episodic Memory 条目（高信息密度）+ 候选日记条目
2. 跳过低信息密度条目（< 20 字符或仅问候）
3. 按与当前日记的语义相似度排序
4. 超过 200 字符的条目生成摘要
5. 贪心填充上下文窗口直到 800 tokens 上限

Token 估算规则：1 个中文字符 ≈ 1.5 tokens

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量与配置                                                    ║
# ╚══════════════════════════════════════════════════════════════╝

# 默认最大上下文 Token 限制
DEFAULT_MAX_CONTEXT_TOKENS = 800

# 低信息密度阈值（字符数）
MIN_CONTENT_LENGTH = 20

# 超过此字符数时生成摘要
SUMMARIZE_THRESHOLD = 200

# 日常问候模式（用于过滤低信息密度条目）
_GREETING_PATTERNS = re.compile(
    r"^(早安?|晚安?|你好|嗨|hi|hello|good\s*(morning|night|evening)|今天也要加油|"
    r"新的一天|打卡|签到|早上好|下午好|晚上好)[。！!.，,]?\s*$",
    re.IGNORECASE,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Token 估算工具函数                                            ║
# ╚══════════════════════════════════════════════════════════════╝

def estimate_tokens(text: str) -> int:
    """
    估算文本的 Token 数量。
    规则：中文字符按 1.5 token 计算，英文单词按 1 token 计算，
    其他字符（标点等）按 0.5 token 计算。

    :param text: 输入文本
    :return: 估算的 Token 数
    """
    if not text:
        return 0

    chinese_chars = 0
    ascii_chars = 0
    other_chars = 0

    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
            chinese_chars += 1
        elif ch.isascii() and ch.isalpha():
            ascii_chars += 1
        else:
            other_chars += 1

    # 英文字符约 4 个字符一个 token
    english_tokens = ascii_chars / 4.0
    chinese_tokens = chinese_chars * 1.5
    other_tokens = other_chars * 0.5

    return int(chinese_tokens + english_tokens + other_tokens + 0.5)


# ╔══════════════════════════════════════════════════════════════╗
# ║  辅助函数                                                      ║
# ╚══════════════════════════════════════════════════════════════╝

def _is_low_density(content: str) -> bool:
    """
    判断条目是否为低信息密度。
    低信息密度定义：短于 20 字符，或仅包含日常问候。

    :param content: 条目文本
    :return: True 表示低信息密度，应跳过
    """
    if not content or len(content.strip()) < MIN_CONTENT_LENGTH:
        return True

    stripped = content.strip()
    if _GREETING_PATTERNS.match(stripped):
        return True

    return False


def _generate_summary(content: str, llm=None) -> str:
    """
    为超过 200 字符的条目生成摘要。
    如果 LLM 可用则调用 LLM 生成摘要，否则优雅截断。

    :param content: 原始文本
    :param llm: 可选的 LLM 实例
    :return: 摘要文本
    """
    if llm is not None:
        try:
            prompt = (
                "请用一句话（不超过50字）概括以下日记内容的核心要点：\n\n"
                f"{content[:500]}"
            )
            response = llm.invoke(prompt)
            summary = response.content if hasattr(response, "content") else str(response)
            summary = summary.strip()
            if summary and len(summary) < len(content):
                return summary
        except Exception as exc:
            logger.debug("LLM 摘要生成失败，使用截断: %s", exc)

    # 无 LLM 或 LLM 失败时：优雅截断
    # 尝试在句子边界截断
    truncated = content[:180]
    # 寻找最后一个句号/感叹号/问号作为截断点
    for sep in ("。", "！", "？", "；", ".", "!", "?"):
        last_idx = truncated.rfind(sep)
        if last_idx > 80:  # 确保至少保留 80 字符
            return truncated[:last_idx + 1] + "..."
    return truncated + "..."


def _compute_similarity_scores(
    query_text: str,
    candidates: List[dict],
) -> List[float]:
    """
    使用 vector_service 的 Embedding 模型计算语义相似度。
    降级方案：如果模型不可用，返回均匀分数。

    :param query_text: 当前日记内容
    :param candidates: 候选条目列表
    :return: 与 candidates 等长的相似度分数列表（0-1，越高越相似）
    """
    if not candidates:
        return []

    try:
        from app.services.vector_service import _get_embedding_model
        import numpy as np

        model = _get_embedding_model()

        # 计算当前日记的 embedding
        query_embedding = model.encode([query_text[:500]], show_progress_bar=False)[0]

        # 计算候选条目的 embeddings
        candidate_texts = [c.get("content", "")[:500] for c in candidates]
        candidate_embeddings = model.encode(candidate_texts, show_progress_bar=False)

        # 余弦相似度
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return [0.5] * len(candidates)

        scores = []
        for emb in candidate_embeddings:
            emb_norm = np.linalg.norm(emb)
            if emb_norm == 0:
                scores.append(0.0)
            else:
                cos_sim = float(np.dot(query_embedding, emb) / (query_norm * emb_norm))
                # 归一化到 0-1 范围
                scores.append(max(0.0, min(1.0, (cos_sim + 1.0) / 2.0)))
        return scores

    except Exception as exc:
        logger.warning("语义相似度计算失败，使用均匀分数: %s", exc)
        return [0.5] * len(candidates)


# ╔══════════════════════════════════════════════════════════════╗
# ║  ContextCompressor 类                                          ║
# ╚══════════════════════════════════════════════════════════════╝

class ContextCompressor:
    """
    智能上下文压缩器：相关性排序 + 摘要生成 + 贪心填充。

    替代固定 7 天窗口策略，基于语义相似度动态选择最相关的历史上下文。
    优先使用 Episodic Memory 条目（信息密度更高），
    跳过低信息密度条目，对长文本生成摘要，贪心填充至 Token 上限。
    """

    MAX_CONTEXT_TOKENS = DEFAULT_MAX_CONTEXT_TOKENS

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        llm=None,
    ):
        """
        初始化压缩器。

        :param max_tokens: 最大上下文 Token 限制，默认 800
        :param llm: 可选的 LLM 实例，用于生成摘要。为 None 时使用截断策略。
        """
        self.max_tokens = max_tokens
        self._llm = llm

    def compress(
        self,
        current_content: str,
        candidates: Optional[List[dict]] = None,
        episodic: Optional[List[dict]] = None,
    ) -> str:
        """
        智能压缩上下文，返回拼接后的上下文字符串。

        流程：
        1. 合并 episodic 条目和候选日记，episodic 条目获得优先加权
        2. 过滤低信息密度条目
        3. 按语义相似度排序
        4. 贪心填充直到达到 Token 上限
        5. 超过 200 字符的条目生成摘要

        :param current_content: 当前日记内容（用于计算语义相似度）
        :param candidates: 候选日记条目列表，每项需包含 "content" 字段，
                          可选 "date", "nid" 字段
        :param episodic: Episodic Memory 条目列表，每项需包含 "event" 或 "content" 字段
        :return: 压缩后的上下文字符串
        """
        if not current_content:
            return ""

        candidates = candidates or []
        episodic = episodic or []

        # Step 1: 统一格式并标记来源
        unified_entries = []

        # Episodic Memory 条目（标记为高优先级）
        for entry in episodic:
            content = entry.get("event") or entry.get("content") or ""
            if not content:
                continue
            unified_entries.append({
                "content": content,
                "source": "episodic",
                "priority_boost": 0.2,  # episodic 条目优先加权
                "date": entry.get("date", ""),
                "nid": entry.get("nid", 0),
            })

        # 候选日记条目
        for entry in candidates:
            content = entry.get("content", "")
            if not content:
                continue
            unified_entries.append({
                "content": content,
                "source": "diary",
                "priority_boost": 0.0,
                "date": entry.get("date", ""),
                "nid": entry.get("nid", 0),
            })

        if not unified_entries:
            return ""

        # Step 2: 过滤低信息密度条目
        filtered_entries = [
            e for e in unified_entries
            if not _is_low_density(e["content"])
        ]

        if not filtered_entries:
            return ""

        # Step 3: 计算语义相似度并排序
        similarity_scores = _compute_similarity_scores(current_content, filtered_entries)

        # 综合分数 = 相似度 + 优先级加权（episodic 条目优先）
        scored_entries = []
        for i, entry in enumerate(filtered_entries):
            sim_score = similarity_scores[i] if i < len(similarity_scores) else 0.5
            final_score = sim_score + entry["priority_boost"]
            scored_entries.append((final_score, entry))

        # 按分数降序排列
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # Step 4: 贪心填充上下文窗口
        context_parts = []
        tokens_used = 0

        for score, entry in scored_entries:
            content = entry["content"]

            # Step 5: 超过 200 字符的条目生成摘要
            if len(content) > SUMMARIZE_THRESHOLD:
                content = _generate_summary(content, self._llm)

            # 估算该条目的 Token 消耗
            entry_tokens = estimate_tokens(content)

            # 检查是否还有空间
            if tokens_used + entry_tokens > self.max_tokens:
                # 如果当前条目太大但上下文还有空间，尝试进一步截断
                remaining_tokens = self.max_tokens - tokens_used
                if remaining_tokens > 30:  # 至少留 30 tokens 才值得加入
                    # 按剩余 token 估算可用字符数
                    max_chars = int(remaining_tokens / 1.5)
                    truncated = content[:max_chars] + "..."
                    context_parts.append(truncated)
                    tokens_used += estimate_tokens(truncated)
                break

            context_parts.append(content)
            tokens_used += entry_tokens

        if not context_parts:
            return ""

        # 用换行分隔各条目
        compressed_context = "\n---\n".join(context_parts)
        return compressed_context
