"""
RAG 召回率评估脚本
==========================================================

评估四种检索模式的召回质量：
1. 语义检索（Chroma 向量检索）
2. BM25 关键词检索
3. 混合检索（语义 + BM25 + RRF 融合）
4. 混合检索 + Re-rank 精排

运行方式（在 backend 目录下）：
    python -m scripts.evaluate_retrieval --user-id 1 --k 5
    python -m scripts.evaluate_retrieval --user-id 1 --k 10 --dataset eval_data.json
    python -m scripts.evaluate_retrieval --user-id 1 --k 5 --output results.json

评估数据集 JSON 格式：
    [{"query": "今天心情不错", "expected_nids": [1, 3, 5]}]
"""

import sys
import os
import json
import random
import argparse

# 确保能导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal
from app.models.user import User
from app.models.diary import DiaryEntry
from app.services.vector_service import (
    _get_user_collection,
    BM25Index,
    reciprocal_rank_fusion,
    ReRanker,
)


class RecallEvaluator:
    """
    RAG 召回率评估工具。
    支持四种模式对比：语义检索、BM25、混合检索、混合+Re-rank。
    输出 Hit Rate@K、MRR@K、Recall@K 指标。
    """

    def __init__(self, user_id: int, k: int = 5):
        self.user_id = user_id
        self.k = k
        self.collection = _get_user_collection(user_id)

    def _compute_metrics(
        self, retrieved_nids: list[int], expected_nids: list[int], k: int
    ) -> dict:
        """
        计算单个查询的评估指标。

        :param retrieved_nids: 检索返回的 nid 列表（按排序）
        :param expected_nids: 期望命中的 nid 列表
        :param k: 评估的 K 值
        :return: {"hit_rate": float, "mrr": float, "recall": float}
        """
        retrieved_at_k = retrieved_nids[:k]
        expected_set = set(expected_nids)

        # Hit Rate@K: 是否至少命中一个期望结果
        hit = 1.0 if any(nid in expected_set for nid in retrieved_at_k) else 0.0

        # MRR@K: 第一个命中结果的倒数排名
        mrr = 0.0
        for i, nid in enumerate(retrieved_at_k):
            if nid in expected_set:
                mrr = 1.0 / (i + 1)
                break

        # Recall@K: 命中的期望结果占期望总数的比例
        if expected_set:
            hits = sum(1 for nid in retrieved_at_k if nid in expected_set)
            recall = hits / len(expected_set)
        else:
            recall = 0.0

        return {"hit_rate": hit, "mrr": mrr, "recall": recall}

    def _semantic_search(self, query: str, top_k: int) -> list[dict]:
        """语义检索（仅 Chroma 向量检索）。"""
        try:
            n_results = min(top_k, self.collection.count())
            if n_results == 0:
                return []
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            items = []
            if results and results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][i]
                    items.append({
                        "doc_id": doc_id,
                        "nid": meta.get("nid", 0),
                        "content": results["documents"][0][i],
                        "date": meta.get("date", ""),
                        "tags": meta.get("tags", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "chunk_total": meta.get("chunk_total", 1),
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })
            return items
        except Exception:
            return []

    def _build_bm25_index(self) -> BM25Index | None:
        """构建 BM25 索引。"""
        try:
            all_data = self.collection.get(include=["documents", "metadatas"])
            if not all_data or not all_data["ids"]:
                return None
            chunks = []
            for j, cid in enumerate(all_data["ids"]):
                meta = all_data["metadatas"][j] if all_data["metadatas"] else {}
                chunks.append({
                    "content": all_data["documents"][j] if all_data["documents"] else "",
                    "doc_id": cid,
                    "nid": meta.get("nid", 0),
                    "uid": meta.get("uid", 0),
                    "date": meta.get("date", ""),
                    "tags": meta.get("tags", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "chunk_total": meta.get("chunk_total", 1),
                })
            idx = BM25Index(self.user_id)
            idx.build(chunks)
            return idx
        except Exception:
            return None

    def _dedupe_by_nid(self, items: list[dict]) -> list[int]:
        """按 nid 去重，保持顺序，返回 nid 列表。"""
        seen = set()
        result = []
        for item in items:
            nid = item.get("nid", 0)
            if nid not in seen:
                seen.add(nid)
                result.append(nid)
        return result

    def _generate_auto_dataset(self, num_samples: int = 10) -> list[dict]:
        """
        自动从用户日记中随机抽取内容片段作为查询。
        以对应日记 ID 作为期望命中。
        """
        db = SessionLocal()
        try:
            entries = (
                db.query(DiaryEntry)
                .filter(DiaryEntry.UID == self.user_id)
                .all()
            )
            if not entries:
                return []

            # 过滤有内容的日记
            valid_entries = [e for e in entries if e.content and len(e.content.strip()) > 20]
            if not valid_entries:
                return []

            # 随机抽取
            sample_size = min(num_samples, len(valid_entries))
            sampled = random.sample(valid_entries, sample_size)

            dataset = []
            for entry in sampled:
                content = entry.content.strip()
                # 从日记中随机截取一段作为查询（取 30-80 字符的片段）
                max_start = max(0, len(content) - 30)
                if max_start > 0:
                    start = random.randint(0, max_start)
                    length = min(random.randint(30, 80), len(content) - start)
                    query = content[start:start + length]
                else:
                    query = content

                dataset.append({
                    "query": query,
                    "expected_nids": [entry.NID],
                })

            return dataset
        finally:
            db.close()

    def evaluate(
        self,
        dataset: list[dict] | None = None,
        k: int | None = None,
    ) -> dict:
        """
        执行评估，返回四种模式的指标。

        :param dataset: 评估数据集，格式 [{"query": str, "expected_nids": [int]}]
        :param k: 评估的 K 值，默认使用初始化时的 k
        :return: 四种模式的评估结果字典
        """
        if k is None:
            k = self.k

        if dataset is None:
            print("未提供评估数据集，自动从日记中抽样生成...")
            dataset = self._generate_auto_dataset()

        if not dataset:
            print("无可用的评估数据，请确保用户有日记数据。")
            return {}

        print(f"评估数据集: {len(dataset)} 条查询, K={k}")

        # 构建 BM25 索引
        print("构建 BM25 索引...")
        bm25_index = self._build_bm25_index()

        # 初始化 ReRanker
        reranker = ReRanker()

        # 四种模式的指标累加器
        modes = {
            "语义检索": {"hit_rate": 0.0, "mrr": 0.0, "recall": 0.0},
            "BM25": {"hit_rate": 0.0, "mrr": 0.0, "recall": 0.0},
            "混合检索": {"hit_rate": 0.0, "mrr": 0.0, "recall": 0.0},
            "混合+Re-rank": {"hit_rate": 0.0, "mrr": 0.0, "recall": 0.0},
        }

        semantic_top_k = int(os.getenv("SEMANTIC_TOP_K", "20"))
        bm25_top_k = int(os.getenv("BM25_TOP_K", "20"))

        for i, item in enumerate(dataset):
            query = item["query"]
            expected_nids = item["expected_nids"]

            # 1. 语义检索
            semantic_results = self._semantic_search(query, semantic_top_k)
            semantic_nids = self._dedupe_by_nid(semantic_results)
            metrics = self._compute_metrics(semantic_nids, expected_nids, k)
            for key in modes["语义检索"]:
                modes["语义检索"][key] += metrics[key]

            # 2. BM25 检索
            bm25_results = []
            if bm25_index:
                bm25_results = bm25_index.search(query, top_k=bm25_top_k)
            bm25_nids = self._dedupe_by_nid(bm25_results)
            metrics = self._compute_metrics(bm25_nids, expected_nids, k)
            for key in modes["BM25"]:
                modes["BM25"][key] += metrics[key]

            # 3. 混合检索（RRF 融合）
            ranked_lists = []
            if semantic_results:
                ranked_lists.append(semantic_results)
            if bm25_results:
                ranked_lists.append(bm25_results)
            fused = reciprocal_rank_fusion(ranked_lists) if ranked_lists else []
            fused_nids = self._dedupe_by_nid(fused)
            metrics = self._compute_metrics(fused_nids, expected_nids, k)
            for key in modes["混合检索"]:
                modes["混合检索"][key] += metrics[key]

            # 4. 混合检索 + Re-rank
            try:
                reranked = reranker.rerank(query, fused) if fused else []
            except Exception:
                reranked = fused
            reranked_nids = self._dedupe_by_nid(reranked)
            metrics = self._compute_metrics(reranked_nids, expected_nids, k)
            for key in modes["混合+Re-rank"]:
                modes["混合+Re-rank"][key] += metrics[key]

            print(f"  [{i+1}/{len(dataset)}] 查询: {query[:30]}...")

        # 计算平均值
        n = len(dataset)
        results = {}
        for mode_name, totals in modes.items():
            results[mode_name] = {
                "hit_rate": round(totals["hit_rate"] / n, 4) if n > 0 else 0.0,
                "mrr": round(totals["mrr"] / n, 4) if n > 0 else 0.0,
                "recall": round(totals["recall"] / n, 4) if n > 0 else 0.0,
            }

        return results


def print_results_table(results: dict, k: int):
    """以表格形式输出评估结果。"""
    print("\n" + "=" * 70)
    print(f"  RAG 召回率评估结果 (K={k})")
    print("=" * 70)
    print(f"  {'检索模式':<16} {'Hit Rate@K':>12} {'MRR@K':>12} {'Recall@K':>12}")
    print("  " + "-" * 52)

    for mode_name, metrics in results.items():
        print(
            f"  {mode_name:<16} "
            f"{metrics['hit_rate']:>12.4f} "
            f"{metrics['mrr']:>12.4f} "
            f"{metrics['recall']:>12.4f}"
        )

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="RAG 召回率评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
        help="要评估的用户 ID",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="评估的 K 值（默认 5）",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="评估数据集 JSON 文件路径",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="评估结果输出 JSON 文件路径",
    )

    args = parser.parse_args()

    # 加载评估数据集
    dataset = None
    if args.dataset:
        with open(args.dataset, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        print(f"已加载评估数据集: {args.dataset} ({len(dataset)} 条)")

    # 验证用户存在
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.UID == args.user_id).first()
        if not user:
            print(f"错误: 用户 ID={args.user_id} 不存在")
            sys.exit(1)
        print(f"评估用户: {user.user_name} (UID={user.UID})")
    finally:
        db.close()

    # 执行评估
    evaluator = RecallEvaluator(user_id=args.user_id, k=args.k)
    results = evaluator.evaluate(dataset=dataset, k=args.k)

    if not results:
        print("评估未产生结果。")
        sys.exit(1)

    # 输出表格
    print_results_table(results, args.k)

    # 导出 JSON
    if args.output:
        output_data = {
            "user_id": args.user_id,
            "k": args.k,
            "num_queries": len(dataset) if dataset else "auto",
            "results": results,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n评估结果已导出: {args.output}")


if __name__ == "__main__":
    main()
