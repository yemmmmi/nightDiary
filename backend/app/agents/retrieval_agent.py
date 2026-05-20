"""
Retrieval Agent — RAG 增强检索 Worker Agent
=============================================

负责从用户历史日记中检索相关信息，支持：
1. 从日记内容推断时间范围作为 RAG 过滤条件
2. 多跳检索：初始结果不足时最多连续 3 次查询
3. 生成不超过 300 tokens 的结构化摘要
4. 使用现有混合检索管线（Chroma + BM25 + RRF + bge-reranker-base）
5. 查询 Domain Knowledge Store 和结构化知识库

作为 LangGraph Worker 节点，接收 MultiAgentState，返回部分状态更新 dict。

Requirements: 4.1, 4.2, 4.3, 4.4, 17.3
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  常量与配置                                                    ║
# ╚══════════════════════════════════════════════════════════════╝

# 多跳检索最大次数
MAX_HOP_COUNT = 3

# 初始检索结果相关性阈值（低于此值触发多跳）
RELEVANCE_THRESHOLD = 0.3

# 结构化摘要最大 Token 数
MAX_SUMMARY_TOKENS = 300

# 每次检索返回的最大结果数
RETRIEVAL_TOP_K = 5

# Domain Knowledge Store 集合名称
DOMAIN_KNOWLEDGE_COLLECTION = "domain_knowledge_psychology"

# Domain Knowledge Store 每次查询最多返回条目数
DOMAIN_KNOWLEDGE_MAX_RESULTS = 2


# ╔══════════════════════════════════════════════════════════════╗
# ║  时间范围推断                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

# 时间关键词 → 天数偏移映射
_TIME_PATTERNS: List[Tuple[re.Pattern, int]] = [
    # 具体天数
    (re.compile(r"前天"), 2),
    (re.compile(r"大前天"), 3),
    (re.compile(r"昨天"), 1),
    # N 天/周/月前
    (re.compile(r"(\d+)\s*天前"), None),  # 动态计算
    (re.compile(r"(\d+)\s*周前"), None),
    (re.compile(r"(\d+)\s*个?月前"), None),
    (re.compile(r"(\d+)\s*年前"), None),
    # 相对时间段
    (re.compile(r"上周|上个?星期"), 7),
    (re.compile(r"上个?月"), 30),
    (re.compile(r"去年"), 365),
    # 模糊时间
    (re.compile(r"最近几天|这几天"), 3),
    (re.compile(r"最近一周|这一?周"), 7),
    (re.compile(r"最近一个?月|这个?月"), 30),
    (re.compile(r"最近"), 7),  # 默认最近 = 7 天
    # 时间段
    (re.compile(r"过去(\d+)天"), None),
    (re.compile(r"近(\d+)天"), None),
]


def infer_time_range(content: str) -> Optional[Tuple[str, str]]:
    """
    从日记内容推断时间范围，作为 RAG 查询的过滤条件。

    解析日记中的时间表达（如"上周"、"3天前"、"最近一个月"），
    返回 (start_date, end_date) 字符串元组。

    :param content: 日记内容
    :return: (start_date, end_date) 格式为 "YYYY-MM-DD"，无法推断时返回 None
    """
    if not content:
        return None

    today = datetime.now()
    days_back = None

    # 尝试匹配具体日期格式 (YYYY-MM-DD 或 YYYY年MM月DD日)
    date_match = re.search(r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})[日号]?", content)
    if date_match:
        try:
            year = int(date_match.group(1))
            month = int(date_match.group(2))
            day = int(date_match.group(3))
            target_date = datetime(year, month, day)
            # 返回目标日期前后 1 天的范围
            start = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
            end = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
            return (start, end)
        except (ValueError, OverflowError):
            pass

    # 尝试匹配相对时间表达
    for pattern, default_days in _TIME_PATTERNS:
        match = pattern.search(content)
        if match:
            if default_days is not None:
                days_back = default_days
                break
            else:
                # 动态计算天数
                num = int(match.group(1))
                pattern_str = pattern.pattern
                if "周" in pattern_str:
                    days_back = num * 7
                elif "月" in pattern_str:
                    days_back = num * 30
                elif "年" in pattern_str:
                    days_back = num * 365
                else:
                    days_back = num
                break

    if days_back is None:
        return None

    # 构建时间范围：从 days_back 天前到今天
    start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    return (start_date, end_date)


# ╔══════════════════════════════════════════════════════════════╗
# ║  结构化知识库查询                                               ║
# ╚══════════════════════════════════════════════════════════════╝

def _query_knowledge_entries(user_id: int, query: str) -> List[Dict[str, Any]]:
    """
    查询结构化知识库（KnowledgeEntry 表），搜索与查询相关的实体。

    使用关键词匹配在 entity_data JSON 中搜索。

    :param user_id: 用户 ID（数据隔离）
    :param query: 查询文本
    :return: 匹配的知识条目列表
    """
    try:
        from sqlalchemy import or_
        from app.core.database import SessionLocal
        from app.models.knowledge_entry import KnowledgeEntry

        db = SessionLocal()
        try:
            # 提取查询中的关键词（简单分词：按标点和空格分割，取长度 > 1 的词）
            keywords = [w.strip() for w in re.split(r"[，。！？、\s,.\?!]+", query) if len(w.strip()) > 1]

            if not keywords:
                return []

            # 构建 LIKE 查询条件
            conditions = []
            for kw in keywords[:5]:  # 最多使用 5 个关键词
                conditions.append(KnowledgeEntry.entity_data.like(f"%{kw}%"))

            results = (
                db.query(KnowledgeEntry)
                .filter(KnowledgeEntry.user_id == user_id)
                .filter(or_(*conditions))
                .order_by(KnowledgeEntry.extracted_at.desc())
                .limit(10)
                .all()
            )

            entries = []
            for r in results:
                try:
                    data = json.loads(r.entity_data) if isinstance(r.entity_data, str) else r.entity_data
                except (json.JSONDecodeError, TypeError):
                    data = {"raw": r.entity_data}

                entries.append({
                    "entity_type": r.entity_type,
                    "entity_data": data,
                    "diary_nid": r.diary_nid,
                    "extracted_at": r.extracted_at.isoformat() if r.extracted_at else "",
                })

            return entries
        finally:
            db.close()

    except Exception as exc:
        logger.warning("结构化知识库查询失败（降级跳过）: %s", exc)
        return []


def _query_domain_knowledge(query: str) -> List[str]:
    """
    查询 Domain Knowledge Store（心理学领域知识库）。

    使用共享的 Chroma 集合 "domain_knowledge_psychology" 进行语义检索。
    每次最多返回 2 条相关条目。

    :param query: 查询文本
    :return: 相关领域知识文本列表
    """
    try:
        from app.services.vector_service import _get_chroma_client, _embedding_fn

        client = _get_chroma_client()

        # 尝试获取 domain knowledge 集合
        try:
            collection = client.get_collection(
                name=DOMAIN_KNOWLEDGE_COLLECTION,
                embedding_function=_embedding_fn,
            )
        except Exception:
            # 集合不存在时静默返回空
            logger.debug("Domain Knowledge Store 集合不存在，跳过查询")
            return []

        if collection.count() == 0:
            return []

        n_results = min(DOMAIN_KNOWLEDGE_MAX_RESULTS, collection.count())
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents"],
        )

        if results and results["documents"] and results["documents"][0]:
            return results["documents"][0]

        return []

    except Exception as exc:
        logger.warning("Domain Knowledge Store 查询失败（降级跳过）: %s", exc)
        return []


# ╔══════════════════════════════════════════════════════════════╗
# ║  多跳检索逻辑                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _filter_by_time_range(
    results: List[Dict[str, Any]],
    time_range: Optional[Tuple[str, str]],
) -> List[Dict[str, Any]]:
    """
    按时间范围过滤检索结果。

    :param results: 检索结果列表
    :param time_range: (start_date, end_date) 元组，为 None 时不过滤
    :return: 过滤后的结果列表
    """
    if not time_range:
        return results

    start_date, end_date = time_range
    filtered = []
    for item in results:
        item_date = item.get("date", "")
        if not item_date:
            # 无日期信息的条目保留（宁可多返回）
            filtered.append(item)
            continue
        # 比较日期字符串（YYYY-MM-DD 格式可直接字符串比较）
        if start_date <= item_date <= end_date:
            filtered.append(item)

    return filtered


def _assess_relevance(results: List[Dict[str, Any]]) -> float:
    """
    评估检索结果的整体相关性分数。

    使用 rerank_score、rrf_score 或 distance 作为相关性指标。
    返回结果集的平均相关性分数。

    :param results: 检索结果列表
    :return: 平均相关性分数（0-1）
    """
    if not results:
        return 0.0

    scores = []
    for item in results:
        # 优先使用 rerank_score，其次 rrf_score，最后 distance
        score = item.get("rerank_score") or item.get("rrf_score") or item.get("distance")
        if score is not None:
            # distance 在 Chroma 中越小越相关，需要反转
            # rerank_score 和 rrf_score 越大越相关
            if "distance" in item and score == item.get("distance"):
                # Chroma distance 通常在 0-2 范围，转换为 0-1 相关性
                scores.append(max(0.0, 1.0 - score / 2.0))
            else:
                scores.append(min(1.0, max(0.0, float(score))))
        else:
            scores.append(0.5)  # 无分数时给中等值

    return sum(scores) / len(scores) if scores else 0.0


def _generate_refined_query(original_query: str, hop_count: int, previous_results: List[Dict]) -> str:
    """
    为多跳检索生成改进的查询。

    基于前一轮结果中的关键信息扩展查询，提高召回率。

    :param original_query: 原始查询
    :param hop_count: 当前跳数（1-based）
    :param previous_results: 前一轮检索结果
    :return: 改进后的查询文本
    """
    if not previous_results:
        return original_query

    # 从前一轮结果中提取关键片段作为查询扩展
    snippets = []
    for item in previous_results[:2]:
        content = item.get("content", "")
        if content:
            # 取前 50 字符作为上下文扩展
            snippets.append(content[:50])

    if snippets:
        # 将原始查询与上下文片段组合
        expanded = f"{original_query} {' '.join(snippets[:1])}"
        # 限制查询长度
        return expanded[:200]

    return original_query


def multi_hop_retrieve(
    user_id: int,
    query: str,
    time_range: Optional[Tuple[str, str]] = None,
    top_k: int = RETRIEVAL_TOP_K,
) -> List[Dict[str, Any]]:
    """
    多跳检索：初始结果不足时最多连续 3 次查询。

    流程：
    1. 使用原始查询进行首次检索
    2. 如果时间范围存在，过滤结果
    3. 评估结果相关性，低于阈值时生成改进查询并重试
    4. 最多重试 MAX_HOP_COUNT 次

    :param user_id: 用户 ID
    :param query: 查询文本
    :param time_range: 可选时间范围过滤
    :param top_k: 每次检索返回的最大结果数
    :return: 最终检索结果列表
    """
    from app.services.vector_service import search_similar_diaries

    all_results: List[Dict[str, Any]] = []
    seen_nids: set = set()
    current_query = query

    for hop in range(MAX_HOP_COUNT):
        # 执行混合检索
        results = search_similar_diaries(
            user_id=user_id,
            query=current_query,
            top_k=top_k,
        )

        # 按时间范围过滤
        if time_range:
            results = _filter_by_time_range(results, time_range)

        # 去重合并（避免重复 nid）
        new_results = []
        for item in results:
            nid = item.get("nid", 0)
            if nid and nid not in seen_nids:
                seen_nids.add(nid)
                new_results.append(item)

        all_results.extend(new_results)

        # 评估当前结果集的相关性
        relevance = _assess_relevance(all_results)

        logger.debug(
            "多跳检索 hop=%d: query='%s', 新增 %d 条, 总计 %d 条, 相关性=%.3f",
            hop + 1, current_query[:30], len(new_results), len(all_results), relevance,
        )

        # 如果结果足够好或已有足够数量，停止
        if relevance >= RELEVANCE_THRESHOLD and len(all_results) >= 2:
            break

        # 如果已经没有新结果，停止
        if not new_results and hop > 0:
            break

        # 生成改进查询用于下一跳
        current_query = _generate_refined_query(query, hop + 1, new_results)

    return all_results[:top_k]


# ╔══════════════════════════════════════════════════════════════╗
# ║  结构化摘要生成                                                 ║
# ╚══════════════════════════════════════════════════════════════╝

def _estimate_tokens(text: str) -> int:
    """
    估算文本的 Token 数量。
    中文字符按 1.5 token，英文按 0.25 token/字符。

    :param text: 输入文本
    :return: 估算 Token 数
    """
    if not text:
        return 0

    chinese_chars = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf')
    other_chars = len(text) - chinese_chars

    return int(chinese_chars * 1.5 + other_chars * 0.25 + 0.5)


def generate_structured_summary(
    retrieval_results: List[Dict[str, Any]],
    knowledge_entries: List[Dict[str, Any]],
    domain_knowledge: List[str],
    query: str,
) -> str:
    """
    生成不超过 300 tokens 的结构化摘要，供其他 Agent 使用。

    摘要结构：
    - 【相关日记】：检索到的历史日记摘要
    - 【知识关联】：结构化知识库中的相关实体
    - 【领域参考】：Domain Knowledge Store 中的专业知识

    :param retrieval_results: 混合检索结果
    :param knowledge_entries: 结构化知识条目
    :param domain_knowledge: 领域知识文本
    :param query: 原始查询（用于上下文）
    :return: 结构化摘要文本
    """
    parts = []
    tokens_used = 0

    # 1. 相关日记摘要
    if retrieval_results:
        diary_summaries = []
        for item in retrieval_results:
            content = item.get("content", "")
            date = item.get("date", "")

            # 截断长内容
            if len(content) > 100:
                content = content[:100] + "..."

            entry_text = f"[{date}] {content}" if date else content
            entry_tokens = _estimate_tokens(entry_text)

            if tokens_used + entry_tokens > MAX_SUMMARY_TOKENS * 0.6:
                break

            diary_summaries.append(entry_text)
            tokens_used += entry_tokens

        if diary_summaries:
            parts.append("【相关日记】\n" + "\n".join(diary_summaries))

    # 2. 知识关联
    if knowledge_entries:
        knowledge_summaries = []
        for entry in knowledge_entries[:3]:
            entity_type = entry.get("entity_type", "")
            entity_data = entry.get("entity_data", {})

            if isinstance(entity_data, dict):
                # 格式化实体信息
                name = entity_data.get("name", entity_data.get("description", ""))
                relation = entity_data.get("relation", "")
                info = f"{entity_type}: {name}"
                if relation:
                    info += f"（{relation}）"
            else:
                info = f"{entity_type}: {entity_data}"

            entry_tokens = _estimate_tokens(info)
            if tokens_used + entry_tokens > MAX_SUMMARY_TOKENS * 0.85:
                break

            knowledge_summaries.append(info)
            tokens_used += entry_tokens

        if knowledge_summaries:
            parts.append("【知识关联】\n" + "\n".join(knowledge_summaries))

    # 3. 领域参考
    if domain_knowledge:
        domain_parts = []
        for dk in domain_knowledge[:DOMAIN_KNOWLEDGE_MAX_RESULTS]:
            # 截断长文本
            if len(dk) > 80:
                dk = dk[:80] + "..."

            entry_tokens = _estimate_tokens(dk)
            if tokens_used + entry_tokens > MAX_SUMMARY_TOKENS:
                break

            domain_parts.append(dk)
            tokens_used += entry_tokens

        if domain_parts:
            parts.append("【领域参考】\n" + "\n".join(domain_parts))

    if not parts:
        return ""

    summary = "\n\n".join(parts)

    # 最终安全检查：确保不超过 300 tokens
    while _estimate_tokens(summary) > MAX_SUMMARY_TOKENS and len(summary) > 50:
        # 逐步截断
        summary = summary[:int(len(summary) * 0.9)]
        # 尝试在句子边界截断
        for sep in ("\n", "。", "！", "？"):
            last_idx = summary.rfind(sep)
            if last_idx > len(summary) * 0.7:
                summary = summary[:last_idx + 1]
                break

    return summary


# ╔══════════════════════════════════════════════════════════════╗
# ║  Retrieval Agent 主函数（LangGraph Worker 节点）                ║
# ╚══════════════════════════════════════════════════════════════╝

def retrieval_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieval Agent Worker 节点函数。

    接收 MultiAgentState，执行 RAG 增强检索，返回部分状态更新。

    流程：
    1. 从日记内容推断时间范围
    2. 使用混合检索管线执行多跳检索
    3. 查询结构化知识库
    4. 查询 Domain Knowledge Store
    5. 生成结构化摘要（≤ 300 tokens）
    6. 返回 {"retrieval_context": summary}

    :param state: MultiAgentState 字典
    :return: 部分状态更新 {"retrieval_context": str}
    """
    diary_content = state.get("diary_content", "")
    user_id = state.get("user_id", 0)

    if not diary_content or not user_id:
        logger.warning("Retrieval Agent: 缺少 diary_content 或 user_id，跳过检索")
        return {"retrieval_context": ""}

    logger.info("Retrieval Agent 开始执行: user_id=%d, content_len=%d", user_id, len(diary_content))

    # Step 1: 推断时间范围
    time_range = infer_time_range(diary_content)
    if time_range:
        logger.debug("推断时间范围: %s ~ %s", time_range[0], time_range[1])

    # Step 2: 多跳检索
    retrieval_results = multi_hop_retrieve(
        user_id=user_id,
        query=diary_content,
        time_range=time_range,
        top_k=RETRIEVAL_TOP_K,
    )

    # Step 3: 查询结构化知识库
    knowledge_entries = _query_knowledge_entries(user_id, diary_content)

    # Step 4: 查询 Domain Knowledge Store
    domain_knowledge = _query_domain_knowledge(diary_content)

    # Step 5: 生成结构化摘要
    summary = generate_structured_summary(
        retrieval_results=retrieval_results,
        knowledge_entries=knowledge_entries,
        domain_knowledge=domain_knowledge,
        query=diary_content,
    )

    logger.info(
        "Retrieval Agent 完成: 检索 %d 条日记, %d 条知识, %d 条领域知识, 摘要 %d 字符",
        len(retrieval_results),
        len(knowledge_entries),
        len(domain_knowledge),
        len(summary),
    )

    return {"retrieval_context": summary}


__all__ = [
    "retrieval_agent",
    "infer_time_range",
    "multi_hop_retrieve",
    "generate_structured_summary",
]
