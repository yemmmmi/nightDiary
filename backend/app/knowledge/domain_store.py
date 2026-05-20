"""
Domain Knowledge Store — 心理学领域知识库
==========================================

以只读 Chroma 集合 "domain_knowledge_psychology" 存储 50-100 条精选心理学知识。
所有用户共享同一集合（无 user_id 隔离），是系统中唯一的共享数据存储。

覆盖领域：
- CBT（认知行为疗法）基础
- 正念技巧
- 睡眠卫生
- 社会支持理论
- 情绪调节策略

使用方式：
    from app.knowledge.domain_store import DomainKnowledgeStore

    store = DomainKnowledgeStore()
    results = store.query("我最近总是失眠怎么办")
    # 返回最多 2 条相关条目，每条包含 content, category, topic, source

设计要点：
- 每次查询最多返回 2 条相关条目，避免信息过载
- 返回结果标注为"通用知识参考"，供 Agent 在回应中引用
- 集合初始化由 scripts/init_domain_knowledge.py 完成
- 查询失败时优雅降级，返回空列表不影响主流程
"""

import logging
from typing import List, Dict, Any, Optional

import chromadb

logger = logging.getLogger(__name__)

# 共享集合名称
COLLECTION_NAME = "domain_knowledge_psychology"

# 每次查询返回的最大条目数
MAX_RESULTS = 2


class DomainKnowledgeStore:
    """
    心理学领域知识库查询接口。

    使用与 vector_service 相同的 Chroma 持久化客户端和 Embedding 模型，
    但操作的是共享的 domain_knowledge_psychology 集合。
    """

    def __init__(self, chroma_client: Optional[chromadb.ClientAPI] = None):
        """
        初始化 Domain Knowledge Store。

        :param chroma_client: 可选的 Chroma 客户端实例，默认使用全局单例
        """
        self._client = chroma_client
        self._collection: Optional[chromadb.Collection] = None

    def _get_client(self) -> chromadb.ClientAPI:
        """获取 Chroma 客户端，复用 vector_service 的全局单例。"""
        if self._client is None:
            from app.services.vector_service import _get_chroma_client
            self._client = _get_chroma_client()
        return self._client

    def _get_collection(self) -> Optional[chromadb.Collection]:
        """
        获取 domain_knowledge_psychology 集合。

        如果集合不存在（尚未初始化），返回 None 并记录警告。
        """
        if self._collection is None:
            try:
                client = self._get_client()
                # 使用与 vector_service 相同的 Embedding Function
                from app.services.vector_service import _embedding_fn
                self._collection = client.get_collection(
                    name=COLLECTION_NAME,
                    embedding_function=_embedding_fn,
                )
            except Exception as exc:
                logger.warning(
                    "Domain Knowledge Store 集合 '%s' 不存在或无法访问: %s。"
                    "请运行 scripts/init_domain_knowledge.py 初始化。",
                    COLLECTION_NAME,
                    exc,
                )
                return None
        return self._collection

    def query(
        self,
        query_text: str,
        max_results: int = MAX_RESULTS,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询领域知识库，返回与查询文本最相关的条目。

        :param query_text: 查询文本（通常是日记内容或情绪管理相关问题）
        :param max_results: 最大返回条目数，默认 2
        :param category_filter: 可选的类别过滤（cbt/mindfulness/sleep_hygiene/social_support/emotion_regulation）
        :return: 相关条目列表，每项包含 content, category, topic, source, reference_note
        """
        if not query_text or not query_text.strip():
            return []

        try:
            collection = self._get_collection()
            if collection is None:
                return []

            # 构建查询参数
            query_params: Dict[str, Any] = {
                "query_texts": [query_text],
                "n_results": max_results,
                "include": ["documents", "metadatas", "distances"],
            }

            # 可选类别过滤
            if category_filter:
                query_params["where"] = {"category": category_filter}

            results = collection.query(**query_params)

            if not results or not results["ids"] or not results["ids"][0]:
                return []

            # 格式化返回结果
            entries = []
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else None

                entries.append({
                    "content": results["documents"][0][i],
                    "category": metadata.get("category", ""),
                    "topic": metadata.get("topic", ""),
                    "source": metadata.get("source", ""),
                    "distance": distance,
                    "reference_note": "【通用知识参考】",
                })

            logger.debug(
                "Domain Knowledge 查询完成: query='%s', 返回 %d 条",
                query_text[:30],
                len(entries),
            )
            return entries

        except Exception as exc:
            logger.error("Domain Knowledge Store 查询失败: %s", exc)
            return []

    def is_initialized(self) -> bool:
        """检查领域知识库是否已初始化（集合存在且有数据）。"""
        try:
            collection = self._get_collection()
            if collection is None:
                return False
            return collection.count() > 0
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取领域知识库统计信息。"""
        try:
            collection = self._get_collection()
            if collection is None:
                return {"initialized": False, "count": 0}
            count = collection.count()
            return {"initialized": count > 0, "count": count}
        except Exception as exc:
            return {"initialized": False, "count": 0, "error": str(exc)}


# 全局单例
_domain_store: Optional[DomainKnowledgeStore] = None


def get_domain_store() -> DomainKnowledgeStore:
    """获取 DomainKnowledgeStore 全局单例。"""
    global _domain_store
    if _domain_store is None:
        _domain_store = DomainKnowledgeStore()
    return _domain_store
