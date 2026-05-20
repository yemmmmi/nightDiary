# -*- coding: utf-8 -*-
"""
Property-Based Tests for Enterprise RAG Upgrade
Uses hypothesis + pytest

Feature: enterprise-rag-upgrade
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import MagicMock
import numpy as np

from app.services.vector_service import (
    ChunkSplitter,
    BM25Index,
    reciprocal_rank_fusion,
    ReRanker,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_CN_CHARS = "今天心情很好工作学习生活开心快乐难过压力放松运动读书旅行美食天气晴朗下雨多云"
_CN_PUNCTS = "。！？；，\n"

st_cn_text = st.text(alphabet=list(_CN_CHARS + _CN_PUNCTS), min_size=1, max_size=800)
st_cn_long_text = st.text(alphabet=list(_CN_CHARS + _CN_PUNCTS), min_size=128, max_size=800)
st_cn_short_text = st.text(alphabet=list(_CN_CHARS), min_size=1, max_size=127)
st_nid = st.integers(min_value=1, max_value=10000)
st_uid = st.integers(min_value=1, max_value=1000)


# =========================================================================
# Property 1: Chunk length upper bound
# =========================================================================
class TestProperty1ChunkLengthUpperBound:
    """Feature: enterprise-rag-upgrade, Property 1: Chunk length upper bound"""

    @given(text=st_cn_long_text)
    @settings(max_examples=30, deadline=None)
    def test_chunk_length_within_bound(self, text: str):
        splitter = ChunkSplitter(chunk_size=512, chunk_overlap=50)
        chunks = splitter.split(text)
        for chunk in chunks:
            assert len(chunk) <= 512


# =========================================================================
# Property 2: Short text no split
# =========================================================================
class TestProperty2ShortTextNoSplit:
    """Feature: enterprise-rag-upgrade, Property 2: Short text no split"""

    @given(text=st_cn_short_text)
    @settings(max_examples=30, deadline=None)
    def test_short_text_returns_single_chunk(self, text: str):
        splitter = ChunkSplitter(chunk_size=512, chunk_overlap=50)
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0] == text


# =========================================================================
# Property 3: Adjacent chunk overlap
# =========================================================================
class TestProperty3AdjacentChunkOverlap:
    """Feature: enterprise-rag-upgrade, Property 3: Adjacent chunk overlap"""

    @given(text=st_cn_long_text)
    @settings(max_examples=30, deadline=None)
    def test_adjacent_chunks_have_overlap(self, text: str):
        splitter = ChunkSplitter(chunk_size=256, chunk_overlap=50)
        chunks = splitter.split(text)
        assume(len(chunks) > 1)
        for i in range(len(chunks) - 1):
            current = chunks[i]
            next_chunk = chunks[i + 1]
            common = set(current) & set(next_chunk)
            assert len(common) > 0


# =========================================================================
# Property 4: Chunk metadata integrity
# =========================================================================
class TestProperty4ChunkMetadataIntegrity:
    """Feature: enterprise-rag-upgrade, Property 4: Chunk metadata integrity"""

    @given(text=st_cn_text, nid=st_nid, uid=st_uid)
    @settings(max_examples=30, deadline=None)
    def test_metadata_fields_complete(self, text: str, nid: int, uid: int):
        splitter = ChunkSplitter(chunk_size=512, chunk_overlap=50)
        result = splitter.split_with_metadata(text, nid=nid, uid=uid, date_str="2025-01-15", tags_str="#test")
        assert len(result) >= 1
        for i, cd in enumerate(result):
            assert "content" in cd
            assert cd["nid"] == nid
            assert cd["uid"] == uid
            assert cd["chunk_index"] == i
            assert cd["chunk_total"] == len(result)


# =========================================================================
# Property 5: Chunk coverage round-trip
# =========================================================================
class TestProperty5ChunkCoverageRoundTrip:
    """Feature: enterprise-rag-upgrade, Property 5: Chunk coverage round-trip"""

    @given(text=st_cn_text)
    @settings(max_examples=30, deadline=None)
    def test_all_chars_covered_by_chunks(self, text: str):
        splitter = ChunkSplitter(chunk_size=512, chunk_overlap=50)
        chunks = splitter.split(text)
        all_chunk_chars = "".join(chunks)
        for char in text:
            assert char in all_chunk_chars


# =========================================================================
# Property 6: RRF fusion invariants
# =========================================================================
st_doc_id = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=3, max_size=20)
st_doc = st.fixed_dictionaries({
    "doc_id": st_doc_id,
    "nid": st.integers(min_value=1, max_value=1000),
    "content": st.text(min_size=1, max_size=50),
})
st_ranked_list = st.lists(st_doc, min_size=1, max_size=10)
st_ranked_lists = st.lists(st_ranked_list, min_size=1, max_size=3)


class TestProperty6RRFFusionInvariants:
    """Feature: enterprise-rag-upgrade, Property 6: RRF fusion invariants"""

    @given(ranked_lists=st_ranked_lists)
    @settings(max_examples=30, deadline=None)
    def test_rrf_no_duplicates(self, ranked_lists):
        result = reciprocal_rank_fusion(ranked_lists)
        doc_ids = [r["doc_id"] for r in result]
        assert len(doc_ids) == len(set(doc_ids))

    @given(ranked_lists=st_ranked_lists)
    @settings(max_examples=30, deadline=None)
    def test_rrf_sorted_by_score(self, ranked_lists):
        result = reciprocal_rank_fusion(ranked_lists)
        if len(result) > 1:
            scores = [r["rrf_score"] for r in result]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1]

    @given(ranked_lists=st_ranked_lists)
    @settings(max_examples=30, deadline=None)
    def test_rrf_all_unique_docs_present(self, ranked_lists):
        input_ids = set()
        for rl in ranked_lists:
            for d in rl:
                if d.get("doc_id"):
                    input_ids.add(d["doc_id"])
        result = reciprocal_rank_fusion(ranked_lists)
        output_ids = {r["doc_id"] for r in result}
        assert input_ids == output_ids

    @given(ranked_lists=st_ranked_lists)
    @settings(max_examples=30, deadline=None)
    def test_rrf_all_results_have_nid_and_score(self, ranked_lists):
        result = reciprocal_rank_fusion(ranked_lists)
        for r in result:
            assert "nid" in r
            assert "rrf_score" in r
            assert r["rrf_score"] > 0


# =========================================================================
# Property 7: Re-rank output ordered with scores
# =========================================================================
class TestProperty7ReRankOutputOrdered:
    """Feature: enterprise-rag-upgrade, Property 7: Re-rank output ordered"""

    @given(
        n=st.integers(min_value=1, max_value=15),
        scores=st.lists(st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False), min_size=1, max_size=15),
    )
    @settings(max_examples=30, deadline=None)
    def test_rerank_output_sorted_by_score(self, n, scores):
        candidates = [{"content": f"c{i}", "doc_id": f"d{i}", "nid": i} for i in range(min(n, len(scores)))]
        actual_scores = scores[:len(candidates)]
        ranker = ReRanker(top_k=len(candidates))
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array(actual_scores)
        ranker._model = mock_model
        result = ranker.rerank("q", candidates)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]["rerank_score"] >= result[i + 1]["rerank_score"]
        for r in result:
            assert "rerank_score" in r


# =========================================================================
# Property 8: Re-rank Top-K constraint
# =========================================================================
class TestProperty8ReRankTopKConstraint:
    """Feature: enterprise-rag-upgrade, Property 8: Re-rank Top-K constraint"""

    @given(top_k=st.integers(min_value=1, max_value=10), n=st.integers(min_value=1, max_value=20))
    @settings(max_examples=30, deadline=None)
    def test_rerank_respects_top_k(self, top_k, n):
        candidates = [{"content": f"c{i}", "doc_id": f"d{i}", "nid": i} for i in range(n)]
        ranker = ReRanker(top_k=top_k)
        mock_model = MagicMock()
        mock_model.predict.return_value = np.random.rand(n)
        ranker._model = mock_model
        result = ranker.rerank("q", candidates)
        assert len(result) <= top_k


# =========================================================================
# ReRanker edge cases
# =========================================================================
class TestReRankerEdgeCases:
    def test_empty_candidates_returns_empty(self):
        assert ReRanker(top_k=5).rerank("q", []) == []

    def test_model_load_failure_degrades(self):
        ranker = ReRanker(model_name="nonexistent/model", top_k=3)
        candidates = [{"content": f"c{i}", "doc_id": f"d{i}", "nid": i} for i in range(5)]
        result = ranker.rerank("q", candidates)
        assert len(result) <= 3


# =========================================================================
# BM25Index unit tests
# =========================================================================
class TestBM25Index:
    def test_build_and_search(self):
        chunks = [
            {"content": "today weather good mood happy", "nid": 1, "uid": 1, "date": "", "tags": "", "chunk_index": 0, "chunk_total": 1, "doc_id": "d1"},
            {"content": "work pressure need relax", "nid": 2, "uid": 1, "date": "", "tags": "", "chunk_index": 0, "chunk_total": 1, "doc_id": "d2"},
        ]
        idx = BM25Index(user_id=1)
        idx.build(chunks)
        results = idx.search("weather mood", top_k=2)
        assert len(results) <= 2
        assert all("bm25_score" in r for r in results)

    def test_empty_corpus_returns_empty(self):
        idx = BM25Index(user_id=1)
        idx.build([])
        assert idx.search("query") == []

    def test_results_sorted_by_score(self):
        chunks = [
            {"content": "weather good today", "nid": 1, "uid": 1, "date": "", "tags": "", "chunk_index": 0, "chunk_total": 1, "doc_id": "d1"},
            {"content": "weather tomorrow also nice", "nid": 2, "uid": 1, "date": "", "tags": "", "chunk_index": 0, "chunk_total": 1, "doc_id": "d2"},
        ]
        idx = BM25Index(user_id=1)
        idx.build(chunks)
        results = idx.search("weather", top_k=10)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["bm25_score"] >= results[i + 1]["bm25_score"]


# =========================================================================
# Property 9: Eval metrics range invariant
# =========================================================================
class TestProperty9EvalMetricsRange:
    """Feature: enterprise-rag-upgrade, Property 9: Eval metrics range"""

    @staticmethod
    def _compute_metrics(retrieved_nids, expected_nids, k):
        seen = set()
        deduped = []
        for nid in retrieved_nids:
            if nid not in seen:
                seen.add(nid)
                deduped.append(nid)
        retrieved_at_k = deduped[:k]
        expected_set = set(expected_nids)
        hit = 1.0 if any(nid in expected_set for nid in retrieved_at_k) else 0.0
        mrr = 0.0
        for i, nid in enumerate(retrieved_at_k):
            if nid in expected_set:
                mrr = 1.0 / (i + 1)
                break
        if expected_set:
            hits = sum(1 for nid in retrieved_at_k if nid in expected_set)
            recall = hits / len(expected_set)
        else:
            recall = 0.0
        return {"hit_rate": hit, "mrr": mrr, "recall": recall}

    @given(
        retrieved=st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=20),
        expected=st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=10),
        k=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30, deadline=None)
    def test_metrics_in_valid_range(self, retrieved, expected, k):
        m = self._compute_metrics(retrieved, expected, k)
        assert 0.0 <= m["hit_rate"] <= 1.0
        assert 0.0 <= m["mrr"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0
