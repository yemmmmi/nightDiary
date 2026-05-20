"""
结构化知识抽取模块
=================

从日记中异步提取结构化信息（人物、事件、地点、话题、mood_score），
存储到 KnowledgeEntry 表，供 Retrieval Agent 查询使用。

核心组件：
- KnowledgeExtractor: 知识抽取器，使用单次 LLM 调用 + 结构化输出
- extract_knowledge_async: 异步入口，fire-and-forget 模式调用

设计原则：
- 日记 > 100 字符时才触发抽取
- 单次 LLM 调用，每次 ≤ 500 tokens
- LLM 调用失败时跳过抽取，不影响日记保存
- 所有查询强制 user_id 过滤（数据隔离）
"""

from app.knowledge.extractor import KnowledgeExtractor, extract_knowledge_async

__all__ = ["KnowledgeExtractor", "extract_knowledge_async"]
