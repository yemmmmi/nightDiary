"""
向量数据库服务（Vector Service）— Chroma + text2vec-base-chinese
================================================================

本模块封装了 Chroma 向量数据库的所有操作，是 RAG 检索的核心基础设施。

架构概览：
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│ diary_service │ ──→ │ vector_service     │ ──→ │ Chroma DB        │
│ (CRUD 同步)   │     │ (本模块)           │     │ (持久化向量存储)  │
└──────────────┘     └───────────────────┘     └──────────────────┘
                              │
                              ▼
                     ┌───────────────────┐
                     │ Embedding Model   │
                     │ text2vec-base-cn  │
                     │ (本地，免费)       │
                     └───────────────────┘

核心设计：
1. 每个用户一个独立的 Chroma Collection(user_{uid}_diar), 保证数据隔离
2. 使用 shibing624/text2vec-base-chinese 作为 Embedding 模型（中文优化，本地运行）
3. 日记的增删改操作通过 diary_service 同步到 Chroma
4. AI 分析时通过语义检索获取相关历史日记，替代原来的 SQL LIKE 关键词搜索

Chroma 存储结构：
- Collection 名称: user_{uid}_diary
- Document ID: diary_{nid}（与 MySQL 的 NID 对应）
- Document 内容: 日记正文
- Metadata: {"nid": int, "uid": int, "date": str, "tags": str}
"""

import logging
import os
from typing import Optional, List, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════╗
# ║  全局单例：Embedding 模型 & Chroma Client                     ║
# ╚══════════════════════════════════════════════════════════════╝

# Embedding 模型单例（约 400MB，首次加载会下载，之后从缓存读取）
_embedding_model = None

# Chroma 客户端单例
_chroma_client: Optional[chromadb.ClientAPI] = None


def _get_embedding_model():
    """
    获取 Embedding 模型单例。
    设置离线模式避免每次都联网检查 HuggingFace。
    使用延迟导入，确保环境变量在 import 之前生效。
    """
    global _embedding_model
    if _embedding_model is None:
        # 必须在 import sentence_transformers 之前设置，否则无效
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("EMBEDDING_MODEL", "shibing624/text2vec-base-chinese")
        logger.info("正在加载 Embedding 模型: %s", model_name)
        _embedding_model = SentenceTransformer(model_name)
        logger.info("Embedding 模型加载完成")
    return _embedding_model


def _get_chroma_client() -> chromadb.ClientAPI:
    """
    获取 Chroma 客户端单例。

    Chroma 支持两种模式：
    1. 持久化模式（PersistentClient）：数据存储在磁盘，重启后保留
    2. 内存模式（EphemeralClient）：数据仅在内存中，重启后丢失

    我们使用持久化模式，数据存储在 CHROMA_PERSIST_DIR 指定的目录。
    """
    global _chroma_client
    if _chroma_client is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        logger.info("初始化 Chroma 客户端，持久化目录: %s", persist_dir)
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        logger.info("Chroma 客户端初始化完成")
    return _chroma_client


# ╔══════════════════════════════════════════════════════════════╗
# ║  自定义 Embedding Function（适配 Chroma 接口）                  ║
# ╚══════════════════════════════════════════════════════════════╝

class Text2VecEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    将 SentenceTransformer 适配为 Chroma 的 EmbeddingFunction 接口。

    Chroma 要求 EmbeddingFunction 实现 __call__ 方法，
    接收文本列表，返回向量列表。
    """

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        将文本列表转换为向量列表。

        :param input: 文本列表，如 ["今天心情不错", "工作很累"]
        :return: 向量列表，每个向量是 768 维的 float 列表
        """
        model = _get_embedding_model()
        # encode 返回 numpy array，需要转为 Python list
        embeddings = model.encode(input, show_progress_bar=False)
        return embeddings.tolist()


# 全局 Embedding Function 实例
_embedding_fn = Text2VecEmbeddingFunction()


# ╔══════════════════════════════════════════════════════════════╗
# ║  Collection 管理                                              ║
# ╚══════════════════════════════════════════════════════════════╝

def _get_user_collection(user_id: int) -> chromadb.Collection:
    """
    获取指定用户的 Chroma Collection。

    每个用户一个独立的 Collection，命名规则: user_{uid}_diary
    这是数据隔离的关键 — 用户 A 的搜索永远不会触及用户 B 的向量。

    get_or_create_collection: 如果 Collection 不存在则创建，存在则返回已有的。
    """
    client = _get_chroma_client()
    collection_name = f"user_{user_id}_diary"
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=_embedding_fn,
        metadata={"description": f"用户 {user_id} 的日记向量集合"},
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║  文档写入（与 diary_service 的 CRUD 同步）                      ║
# ╚══════════════════════════════════════════════════════════════╝

def add_diary(user_id: int, nid: int, content: str, date_str: str = "", tags_str: str = "") -> None:
    """
    将一篇日记写入 Chroma 向量库。

    调用时机: diary_service.create_entry() 成功后

    :param user_id: 用户 ID
    :param nid: 日记 ID(MySQL 主键)
    :param content: 日记正文
    :param date_str: 日期字符串，如 "2025-01-15"
    :param tags_str: 标签字符串，如 "#工作、#学习"
    """
    try:
        collection = _get_user_collection(user_id)
        doc_id = f"diary_{nid}"

        collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[{
                "nid": nid,
                "uid": user_id,
                "date": date_str,
                "tags": tags_str,
            }],
        )
        logger.debug("日记已写入 Chroma: user=%d, nid=%d", user_id, nid)
    except Exception as exc:
        # Chroma 写入失败不应阻塞主流程（MySQL 是主数据源）
        logger.error("Chroma 写入失败（不影响主流程）: %s", exc)


def update_diary(user_id: int, nid: int, content: str, date_str: str = "", tags_str: str = "") -> None:
    """
    更新 Chroma 中的日记向量。

    调用时机: diary_service.update_entry() 修改了 content 后
    使用 upsert 实现：存在则更新，不存在则插入。
    """
    # upsert 语义天然支持更新，直接复用 add_diary
    add_diary(user_id, nid, content, date_str, tags_str)


def delete_diary(user_id: int, nid: int) -> None:
    """
    从 Chroma 中删除一篇日记的向量。

    调用时机: diary_service.delete_entry() 成功后
    """
    try:
        collection = _get_user_collection(user_id)
        doc_id = f"diary_{nid}"
        collection.delete(ids=[doc_id])
        logger.debug("日记已从 Chroma 删除: user=%d, nid=%d", user_id, nid)
    except Exception as exc:
        logger.error("Chroma 删除失败（不影响主流程）: %s", exc)


# ╔══════════════════════════════════════════════════════════════╗
# ║  语义检索（RAG 的核心）                                        ║
# ╚══════════════════════════════════════════════════════════════╝

def search_similar_diaries(
    user_id: int,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    语义检索：根据查询文本，从用户的日记向量库中检索最相似的日记。

    这是 RAG(Retrieval-Augmented Generation)的 R(Retrieval)部分。

    工作原理：
    1. 将 query 文本通过 Embedding 模型转换为 768 维向量
    2. 在 Chroma 中计算该向量与所有日记向量的余弦相似度
    3. 返回相似度最高的 top_k 篇日记

    与 SQL LIKE 的区别：
    - SQL LIKE "%开心%"：只能匹配包含"开心"这个词的日记
    - 语义检索 "开心"：能匹配"今天心情很好"、"感到快乐"等语义相近的日记
    - 语义检索理解的是"意思"，而不是"字面"

    :param user_id: 用户 ID(决定搜索哪个 Collection)
    :param query: 查询文本
    :param top_k: 返回最相似的前 N 篇，默认 5
    :return: 结果列表，每项包含 {"nid", "content", "date", "tags", "distance"}
    """
    try:
        collection = _get_user_collection(user_id)

        # 检查 Collection 是否有数据
        if collection.count() == 0:
            return []

        # 执行语义检索
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),  # 不能超过实际文档数
            include=["documents", "metadatas", "distances"],
        )

        # 解析结果
        items = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append({
                    "nid": results["metadatas"][0][i].get("nid", 0),
                    "content": results["documents"][0][i],
                    "date": results["metadatas"][0][i].get("date", ""),
                    "tags": results["metadatas"][0][i].get("tags", ""),
                    "distance": results["distances"][0][i] if results["distances"] else None,
                })

        logger.debug("语义检索完成: user=%d, query='%s', 命中 %d 条", user_id, query[:30], len(items))
        return items

    except Exception as exc:
        logger.error("Chroma 语义检索失败: %s", exc)
        return []


# ╔══════════════════════════════════════════════════════════════╗
# ║  批量导入（迁移脚本用）                                        ║
# ╚══════════════════════════════════════════════════════════════╝

def bulk_import_user_diaries(
    user_id: int,
    diaries: List[Dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """
    批量将用户的历史日记导入 Chroma。

    用于首次部署或数据迁移场景: MySQL 中已有日记数据，
    需要一次性全部导入 Chroma 建立向量索引。

    :param user_id: 用户 ID
    :param diaries: 日记列表，每项需包含 {"nid", "content", "date", "tags"}
    :param batch_size: 每批写入的数量(Chroma 建议不超过 100)
    :return: 成功导入的数量
    """
    if not diaries:
        return 0

    collection = _get_user_collection(user_id)
    imported = 0

    # 分批写入，避免单次请求过大
    for i in range(0, len(diaries), batch_size):
        batch = diaries[i:i + batch_size]

        ids = [f"diary_{d['nid']}" for d in batch]
        documents = [d.get("content", "") for d in batch]
        metadatas = [
            {
                "nid": d["nid"],
                "uid": user_id,
                "date": d.get("date", ""),
                "tags": d.get("tags", ""),
            }
            for d in batch
        ]

        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            imported += len(batch)
            logger.info("批量导入进度: user=%d, %d/%d", user_id, imported, len(diaries))
        except Exception as exc:
            logger.error("批量导入失败(batch %d-%d): %s", i, i + len(batch), exc)

    return imported
