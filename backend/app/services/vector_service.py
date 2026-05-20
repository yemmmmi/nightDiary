"""
向量数据库服务(Vector Service) — Chroma + text2vec-base-chinese
================================================================

本模块封装了 Chroma 向量数据库的所有操作，是 RAG 检索的核心基础设施。

架构概览：
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│ diary_service │ ──→ │ vector_service   │──→  │ Chroma DB        │
│ (CRUD 同步)   │     │ (本模块)          │     │ (持久化向量存储)  │
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
# ║  ChunkSplitter — 中文日记文本切分器                            ║
# ╚══════════════════════════════════════════════════════════════╝

class ChunkSplitter:
    """
    中文日记文本切分器，基于 LangChain RecursiveCharacterTextSplitter。
    针对中文标点（。！？；，）优化分隔符优先级。

    使用方式：
        splitter = ChunkSplitter()
        chunks = splitter.split("很长的日记内容...")
        chunk_dicts = splitter.split_with_metadata("内容", nid=1, uid=1, date_str="2025-01-15")
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        min_chunk_size: int = 128,
    ):
        """
        :param chunk_size: 每个 chunk 的最大字符数，默认从 CHUNK_SIZE 环境变量读取，兜底 512
        :param chunk_overlap: 相邻 chunk 的重叠字符数，默认从 CHUNK_OVERLAP 环境变量读取，兜底 50
        :param min_chunk_size: 低于此长度的日记不切分，默认 128
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        self.chunk_size = chunk_size if chunk_size is not None else int(os.getenv("CHUNK_SIZE", "512"))
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else int(os.getenv("CHUNK_OVERLAP", "50"))
        self.min_chunk_size = min_chunk_size

        self._splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n",
                        "。", "！", "？", "：", "，",
                        ".", "!", "?", ":", "," ,
                         " ", ""],
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            keep_separator=True,
        )

    def split(self, content: str) -> list[str]:
        """
        将日记内容切分为 chunk 列表。
        短文本(< min_chunk_size)直接返回 [content]，不进行切分。

        :param content: 日记正文
        :return: chunk 文本列表
        """
        if len(content) < self.min_chunk_size:
            return [content]

        chunks = self._splitter.split_text(content)
        return chunks

    def split_with_metadata(
        self,
        content: str,
        nid: int,
        uid: int,
        date_str: str = "",
        tags_str: str = "",
    ) -> list[dict]:
        """
        切分并附加元数据，返回 chunk 字典列表。

        :param content: 日记正文
        :param nid: 日记 ID
        :param uid: 用户 ID
        :param date_str: 日期字符串
        :param tags_str: 标签字符串
        :return: chunk 字典列表，每项包含 content, nid, uid, date, tags, chunk_index, chunk_total
        """
        chunks = self.split(content)
        total = len(chunks)

        return [
            {
                "content": chunk,
                "nid": nid,
                "uid": uid,
                "date": date_str,
                "tags": tags_str,
                "chunk_index": i,
                "chunk_total": total,
            }
            for i, chunk in enumerate(chunks)
        ]


# ╔══════════════════════════════════════════════════════════════╗
# ║  BM25Index — 关键词检索器                                      ║
# ╚══════════════════════════════════════════════════════════════╝

class BM25Index:
    """
    用户级 BM25 倒排索引，使用 jieba 分词 + rank_bm25 库。
    每个用户维护一个独立的 BM25 索引（内存中）。

    使用方式：
        index = BM25Index(user_id=1)
        index.build(chunks)
        results = index.search("关键词查询", top_k=20)
    """

    def __init__(self, user_id: int):
        """
        :param user_id: 用户 ID，用于标识索引归属
        """
        self.user_id = user_id
        self.corpus: list[list[str]] = []
        self.chunk_metadata: list[dict] = []
        self.bm25 = None

    def build(self, chunks: list[dict]) -> None:
        """
        从 chunk 列表构建 BM25 索引。
        使用 jieba.lcut 进行中文分词，过滤长度 <= 1 的停用词。

        :param chunks: chunk 字典列表，每项需包含 content 字段及元数据
        """
        import jieba
        from rank_bm25 import BM25Okapi

        self.chunk_metadata = chunks
        self.corpus = []

        for chunk in chunks:
            content = chunk.get("content", "")
            # jieba 分词，过滤长度 <= 1 的词（停用词/标点）
            tokens = [w for w in jieba.lcut(content) if len(w) > 1]
            self.corpus.append(tokens)

        if self.corpus:
            self.bm25 = BM25Okapi(self.corpus)
        else:
            self.bm25 = None

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """
        BM25 关键词检索，返回按 BM25 分数排序的 chunk 列表。

        :param query: 查询文本
        :param top_k: 返回的最大结果数，默认 20
        :return: 按 bm25_score 降序排列的 chunk 列表
        """
        import jieba

        if self.bm25 is None or not self.corpus:
            return []

        query_tokens = [w for w in jieba.lcut(query) if len(w) > 1]
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # 将分数与 chunk 元数据配对，按分数降序排列
        scored_chunks = []
        for i, score in enumerate(scores):
            if i < len(self.chunk_metadata):
                meta = self.chunk_metadata[i]
                scored_chunks.append({
                    "content": meta.get("content", ""),
                    "nid": meta.get("nid", 0),
                    "uid": meta.get("uid", 0),
                    "date": meta.get("date", ""),
                    "tags": meta.get("tags", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "chunk_total": meta.get("chunk_total", 1),
                    "bm25_score": float(score),
                    "doc_id": meta.get("doc_id", f"diary_{meta.get('nid', 0)}_chunk_{meta.get('chunk_index', 0)}"),
                })

        # 按 bm25_score 降序排列，取 top_k
        scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored_chunks[:top_k]


# 模块级 BM25 索引缓存：user_id -> BM25Index
_bm25_indexes: dict[int, BM25Index] = {}


# ╔══════════════════════════════════════════════════════════════╗
# ║  RRF 融合函数                                                 ║
# ╚══════════════════════════════════════════════════════════════╝

def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """
    Reciprocal Rank Fusion 算法。

    公式: score(d) = Σ 1/(k + rank_i(d))

    使用 doc_id 作为去重键，融合多路召回结果。

    :param ranked_lists: 多路召回的排序结果列表
    :param k: RRF 常数，默认 60
    :return: 按 RRF 分数降序排列的融合结果，每项附加 rrf_score
    """
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list):
            doc_id = doc.get("doc_id", "")
            if not doc_id:
                continue

            # 累加 RRF 分数
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

            # 保留首次出现的文档信息
            if doc_id not in doc_map:
                doc_map[doc_id] = doc.copy()

    # 构建结果列表，附加 rrf_score
    results = []
    for doc_id, score in rrf_scores.items():
        item = doc_map[doc_id].copy()
        item["rrf_score"] = score
        # 确保 nid 字段存在
        if "nid" not in item:
            item["nid"] = 0
        results.append(item)

    # 按 rrf_score 降序排列
    results.sort(key=lambda x: x["rrf_score"], reverse=True)
    return results


# ╔══════════════════════════════════════════════════════════════╗
# ║  ReRanker — 重排序器                                          ║
# ╚══════════════════════════════════════════════════════════════╝

class ReRanker:
    """
    基于 CrossEncoder 的重排序器。
    使用 BAAI/bge-reranker-base 模型对 (query, chunk) 对进行相关性打分。
    模型懒加载，首次调用 rerank 时才加载。

    使用方式：
        ranker = ReRanker()
        results = ranker.rerank("查询文本", candidates)
    """

    def __init__(self, model_name: str | None = None, top_k: int | None = None):
        """
        :param model_name: 模型名称，默认从 RERANK_MODEL 环境变量读取，兜底 BAAI/bge-reranker-base
        :param top_k: 返回的最大结果数，默认从 RERANK_TOP_K 环境变量读取，兜底 5
        """
        self.model_name = model_name or os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
        self.top_k = top_k if top_k is not None else int(os.getenv("RERANK_TOP_K", "5"))
        self._model = None

    def _load_model(self):
        """懒加载 CrossEncoder 模型。"""
        if self._model is None:
            # 设置离线模式，与 Embedding 模型一致
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

            from sentence_transformers import CrossEncoder

            logger.info("正在加载 ReRanker 模型: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
            logger.info("ReRanker 模型加载完成")

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        对候选列表进行重排序。

        :param query: 查询文本
        :param candidates: 候选 chunk 列表，每项需包含 content 字段
        :return: 按 rerank_score 降序排列的结果列表，截取 top_k
        """
        if not candidates:
            return []

        try:
            self._load_model()

            # 构建 (query, content) 对
            pairs = [(query, c.get("content", "")) for c in candidates]

            # 计算相关性分数
            scores = self._model.predict(pairs)

            # 将分数附加到候选项
            scored = []
            for i, candidate in enumerate(candidates):
                item = candidate.copy()
                item["rerank_score"] = float(scores[i])
                scored.append(item)

            # 按 rerank_score 降序排列
            scored.sort(key=lambda x: x["rerank_score"], reverse=True)

            return scored[:self.top_k]

        except Exception as exc:
            logger.warning("ReRanker 执行异常，降级返回原始列表: %s", exc)
            # 降级：返回原始列表截取 top_k，不附加 rerank_score
            return candidates[:self.top_k]


# 全局 ReRanker 单例
_reranker: ReRanker | None = None


def _get_reranker() -> ReRanker:
    """获取 ReRanker 全局单例。"""
    global _reranker
    if _reranker is None:
        _reranker = ReRanker()
    return _reranker


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

# 全局 ChunkSplitter 单例
_chunk_splitter = ChunkSplitter()


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
    将一篇日记切分为 chunk 后批量写入 Chroma 向量库。

    调用时机: diary_service.create_entry() 成功后

    :param user_id: 用户 ID
    :param nid: 日记 ID(MySQL 主键)
    :param content: 日记正文
    :param date_str: 日期字符串，如 "2025-01-15"
    :param tags_str: 标签字符串，如 "#工作、#学习"
    """
    try:
        collection = _get_user_collection(user_id)

        # 使用 ChunkSplitter 切分日记内容
        chunk_dicts = _chunk_splitter.split_with_metadata(
            content, nid=nid, uid=user_id, date_str=date_str, tags_str=tags_str
        )

        # 构建批量写入数据
        ids = [f"diary_{nid}_chunk_{cd['chunk_index']}" for cd in chunk_dicts]
        documents = [cd["content"] for cd in chunk_dicts]
        metadatas = [
            {
                "nid": nid,
                "uid": user_id,
                "date": cd["date"],
                "tags": cd["tags"],
                "chunk_index": cd["chunk_index"],
                "chunk_total": cd["chunk_total"],
            }
            for cd in chunk_dicts
        ]

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # 失效该用户的 BM25 索引缓存
        _bm25_indexes.pop(user_id, None)

        logger.debug("日记已写入 Chroma（%d 个 chunk）: user=%d, nid=%d", len(chunk_dicts), user_id, nid)
    except Exception as exc:
        # Chroma 写入失败不应阻塞主流程（MySQL 是主数据源）
        logger.error("Chroma 写入失败（不影响主流程）: %s", exc)


def update_diary(user_id: int, nid: int, content: str, date_str: str = "", tags_str: str = "") -> None:
    """
    更新 Chroma 中的日记向量。

    调用时机: diary_service.update_entry() 修改了 content 后
    先删除该日记的所有旧 chunk, 再重新切分写入新 chunk。
    """
    try:
        collection = _get_user_collection(user_id)
        # 先通过 metadata where 条件删除该日记的所有旧 chunk
        collection.delete(where={"nid": nid})
        logger.debug("已删除日记旧 chunk: user=%d, nid=%d", user_id, nid)
    except Exception as exc:
        logger.error("删除旧 chunk 失败: %s", exc)

    # 重新切分并写入新 chunk
    add_diary(user_id, nid, content, date_str, tags_str)


def delete_diary(user_id: int, nid: int) -> None:
    """
    从 Chroma 中删除一篇日记的所有 chunk 向量。

    调用时机: diary_service.delete_entry() 成功后
    使用 where={"nid": nid} 过滤删除该日记的所有 chunk。
    """
    try:
        collection = _get_user_collection(user_id)
        collection.delete(where={"nid": nid})

        # 失效该用户的 BM25 索引缓存
        _bm25_indexes.pop(user_id, None)

        logger.debug("日记所有 chunk 已从 Chroma 删除: user=%d, nid=%d", user_id, nid)
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
    混合检索 + Re-rank：根据查询文本，从用户的日记向量库中检索最相似的日记。

    流程：
    1. 语义检索（Chroma）召回 SEMANTIC_TOP_K 个 chunk
    2. BM25 检索召回 BM25_TOP_K 个 chunk（失败时降级为仅语义检索）
    3. RRF 融合两路结果
    4. Re-rank 精排
    5. 按原始日记 nid 去重聚合，返回 top_k 个结果

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

        semantic_top_k = int(os.getenv("SEMANTIC_TOP_K", "20"))
        bm25_top_k = int(os.getenv("BM25_TOP_K", "20"))

        # ── 1. 语义检索（Chroma query）──
        semantic_results = []
        try:
            n_results = min(semantic_top_k, collection.count())
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            if results and results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][i]
                    semantic_results.append({
                        "doc_id": doc_id,
                        "nid": meta.get("nid", 0),
                        "content": results["documents"][0][i],
                        "date": meta.get("date", ""),
                        "tags": meta.get("tags", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "chunk_total": meta.get("chunk_total", 1),
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    })
        except Exception as exc:
            logger.warning("语义检索异常: %s", exc)

        # ── 2. BM25 检索 ──
        bm25_results = []
        try:
            if user_id not in _bm25_indexes:
                # 从 Chroma collection 加载所有文档构建索引
                all_data = collection.get(include=["documents", "metadatas"])
                if all_data and all_data["ids"]:
                    chunks_for_bm25 = []
                    for j, cid in enumerate(all_data["ids"]):
                        meta = all_data["metadatas"][j] if all_data["metadatas"] else {}
                        chunks_for_bm25.append({
                            "content": all_data["documents"][j] if all_data["documents"] else "",
                            "doc_id": cid,
                            "nid": meta.get("nid", 0),
                            "uid": meta.get("uid", 0),
                            "date": meta.get("date", ""),
                            "tags": meta.get("tags", ""),
                            "chunk_index": meta.get("chunk_index", 0),
                            "chunk_total": meta.get("chunk_total", 1),
                        })
                    bm25_idx = BM25Index(user_id)
                    bm25_idx.build(chunks_for_bm25)
                    _bm25_indexes[user_id] = bm25_idx

            if user_id in _bm25_indexes:
                bm25_results = _bm25_indexes[user_id].search(query, top_k=bm25_top_k)
        except Exception as exc:
            logger.warning("BM25 索引构建/检索失败，降级为仅语义检索: %s", exc)

        # ── 3. RRF 融合 ──
        ranked_lists = []
        if semantic_results:
            ranked_lists.append(semantic_results)
        if bm25_results:
            ranked_lists.append(bm25_results)

        if not ranked_lists:
            return []

        fused = reciprocal_rank_fusion(ranked_lists)

        # ── 4. Re-rank 精排 ──
        try:
            reranked = _get_reranker().rerank(query, fused)
        except Exception as exc:
            logger.warning("Re-rank 失败，使用 RRF 融合结果: %s", exc)
            reranked = fused

        # ── 5. 按原始日记 nid 去重聚合（同一 nid 的多个 chunk 只保留分数最高的）──
        seen_nids: dict[int, dict] = {}
        for item in reranked:
            nid = item.get("nid", 0)
            if nid not in seen_nids:
                seen_nids[nid] = item

        # 保持 reranked 的顺序
        deduped = []
        added_nids = set()
        for item in reranked:
            nid = item.get("nid", 0)
            if nid not in added_nids:
                added_nids.add(nid)
                deduped.append(item)

        # 取 top_k 并格式化返回
        final = []
        for item in deduped[:top_k]:
            final.append({
                "nid": item.get("nid", 0),
                "content": item.get("content", ""),
                "date": item.get("date", ""),
                "tags": item.get("tags", ""),
                "distance": item.get("distance") or item.get("rerank_score") or item.get("rrf_score", 0),
            })

        logger.debug("混合检索完成: user=%d, query='%s', 命中 %d 条", user_id, query[:30], len(final))
        return final

    except Exception as exc:
        logger.error("混合检索失败: %s", exc)
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
    批量将用户的历史日记导入 Chroma（Chunk 模式）。

    用于首次部署或数据迁移场景: MySQL 中已有日记数据，
    需要一次性全部导入 Chroma 建立向量索引。
    对每篇日记使用 ChunkSplitter 切分后批量写入。

    :param user_id: 用户 ID
    :param diaries: 日记列表，每项需包含 {"nid", "content", "date", "tags"}
    :param batch_size: 每批写入的数量(Chroma 建议不超过 100)
    :return: 成功导入的数量
    """
    if not diaries:
        return 0

    collection = _get_user_collection(user_id)
    imported = 0

    # 对所有日记进行 chunk 切分，收集所有 chunk
    all_ids = []
    all_documents = []
    all_metadatas = []

    for d in diaries:
        nid = d["nid"]
        content = d.get("content", "")
        date_str = d.get("date", "")
        tags_str = d.get("tags", "")

        chunk_dicts = _chunk_splitter.split_with_metadata(
            content, nid=nid, uid=user_id, date_str=date_str, tags_str=tags_str
        )

        for cd in chunk_dicts:
            all_ids.append(f"diary_{nid}_chunk_{cd['chunk_index']}")
            all_documents.append(cd["content"])
            all_metadatas.append({
                "nid": nid,
                "uid": user_id,
                "date": cd["date"],
                "tags": cd["tags"],
                "chunk_index": cd["chunk_index"],
                "chunk_total": cd["chunk_total"],
            })

    # 分批写入，避免单次请求过大
    for i in range(0, len(all_ids), batch_size):
        batch_ids = all_ids[i:i + batch_size]
        batch_docs = all_documents[i:i + batch_size]
        batch_metas = all_metadatas[i:i + batch_size]

        try:
            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            imported += len(batch_ids)
            logger.info("批量导入进度: user=%d, %d/%d chunks", user_id, imported, len(all_ids))
        except Exception as exc:
            logger.error("批量导入失败(batch %d-%d): %s", i, i + len(batch_ids), exc)

    # 失效该用户的 BM25 索引缓存
    _bm25_indexes.pop(user_id, None)

    return imported
