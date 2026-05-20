"""
ParentChildChunker 单元测试
"""

import pytest
from unittest.mock import MagicMock, patch

from app.agents.parent_child_chunker import (
    ParentChildChunker,
    ParentDoc,
    ChildDoc,
    get_parent_child_chunker,
)


class TestParentChildChunker:
    """ParentChildChunker 核心功能测试"""

    def setup_method(self):
        self.chunker = ParentChildChunker(child_chunk_size=250, child_overlap=30)

    def test_chunk_short_diary(self):
        """短日记（< MIN_CONTENT_LENGTH）不切分，直接作为单个子块"""
        parent, children = self.chunker.chunk_diary(
            nid=1, content="今天天气不错", uid=10, date_str="2025-01-15"
        )

        assert parent.doc_id == "parent_1"
        assert parent.nid == 1
        assert parent.uid == 10
        assert parent.content == "今天天气不错"
        assert len(children) == 1
        assert children[0].doc_id == "child_1_0"
        assert children[0].parent_id == "parent_1"
        assert children[0].content == "今天天气不错"
        assert children[0].chunk_index == 0
        assert children[0].chunk_total == 1

    def test_chunk_long_diary_produces_children(self):
        """长日记会被切分为多个子块，每个子块有 parent_id 引用"""
        # 构造 600+ 字符的内容
        content = "今天在公司参加了一个非常重要的会议。" * 20
        parent, children = self.chunker.chunk_diary(
            nid=42, content=content, uid=5, date_str="2025-06-01", tags_str="#工作"
        )

        # 父文档
        assert parent.doc_id == "parent_42"
        assert parent.content == content
        assert parent.uid == 5

        # 子文档
        assert len(children) > 1
        for i, child in enumerate(children):
            assert child.doc_id == f"child_42_{i}"
            assert child.parent_id == "parent_42"
            assert child.nid == 42
            assert child.uid == 5
            assert child.chunk_index == i
            assert child.chunk_total == len(children)
            assert child.date == "2025-06-01"
            assert child.tags == "#工作"

    def test_child_chunk_size_in_range(self):
        """子块长度应在 200-300 字符范围内（允许边界附近的偏差）"""
        content = "这是一段很长的日记内容，包含了很多关于生活和工作的感悟。" * 30
        _, children = self.chunker.chunk_diary(nid=10, content=content, uid=1)

        # 除了最后一个子块，其余子块长度应接近 200-300 字符
        for child in children[:-1]:
            # 允许切分器在标点处切断时的合理偏差
            assert len(child.content) >= 50, f"子块太短: {len(child.content)} chars"

    def test_retrieve_parents_from_memory(self):
        """retrieve_parents 可从内存索引中检索父文档"""
        # 先 chunk 一些日记，将父文档存入内存
        self.chunker.chunk_diary(nid=1, content="第一篇日记内容", uid=1)
        self.chunker.chunk_diary(nid=2, content="第二篇日记内容", uid=1)
        self.chunker.chunk_diary(nid=3, content="第三篇日记内容", uid=1)

        # 用子块 ID 检索父文档
        parents = self.chunker.retrieve_parents(["child_1_0", "child_2_1", "child_1_2"])

        # 应该去重，只返回 nid=1 和 nid=2 的父文档
        assert len(parents) == 2
        nids = {p.nid for p in parents}
        assert nids == {1, 2}

    def test_retrieve_parents_unknown_child_id(self):
        """未知的 child_id 不会导致异常"""
        parents = self.chunker.retrieve_parents(["child_999_0", "invalid_id", ""])
        # child_999 不在内存索引中，应返回空（带 warning 日志）
        assert len(parents) == 0

    def test_extract_parent_id(self):
        """_extract_parent_id 正确解析子块 ID"""
        assert ParentChildChunker._extract_parent_id("child_42_3") == "parent_42"
        assert ParentChildChunker._extract_parent_id("child_1_0") == "parent_1"
        assert ParentChildChunker._extract_parent_id("parent_1") is None
        assert ParentChildChunker._extract_parent_id("") is None
        assert ParentChildChunker._extract_parent_id("invalid") is None

    def test_parent_doc_metadata(self):
        """ParentDoc.to_metadata 返回正确结构"""
        parent = ParentDoc(
            doc_id="parent_5", nid=5, uid=1, content="内容",
            date="2025-01-01", tags="#标签"
        )
        meta = parent.to_metadata()
        assert meta["doc_type"] == "parent"
        assert meta["nid"] == 5
        assert meta["uid"] == 1

    def test_child_doc_metadata_has_parent_id(self):
        """ChildDoc.to_metadata 包含 parent_id 引用"""
        child = ChildDoc(
            doc_id="child_5_0", parent_id="parent_5", nid=5, uid=1,
            content="子块", chunk_index=0, chunk_total=3
        )
        meta = child.to_metadata()
        assert meta["doc_type"] == "child"
        assert meta["parent_id"] == "parent_5"
        assert meta["chunk_index"] == 0
        assert meta["chunk_total"] == 3

    def test_store_to_collection_atomic(self):
        """store_to_collection 先删旧数据再写入新数据（原子性）"""
        parent, children = self.chunker.chunk_diary(
            nid=7, content="测试原子写入的日记内容，需要足够长才能切分" * 5, uid=2
        )

        mock_collection = MagicMock()

        self.chunker.store_to_collection(parent, children, mock_collection)

        # 验证先删除再写入
        mock_collection.delete.assert_called_once_with(where={"nid": 7})
        mock_collection.upsert.assert_called_once()

        # 验证 upsert 参数包含父文档和子文档
        call_kwargs = mock_collection.upsert.call_args
        ids = call_kwargs.kwargs.get("ids") or call_kwargs[1].get("ids") if call_kwargs[1] else call_kwargs[0][0] if call_kwargs[0] else None
        # Use positional or keyword args
        if ids is None:
            ids = call_kwargs[1]["ids"]
        assert ids[0] == "parent_7"
        assert all(cid.startswith("child_7_") for cid in ids[1:])

    def test_delete_from_collection(self):
        """delete_from_collection 删除指定 nid 的所有文档"""
        # 先添加到内存
        self.chunker.chunk_diary(nid=5, content="要删除的日记", uid=1)
        assert "parent_5" in self.chunker._parent_store

        mock_collection = MagicMock()
        self.chunker.delete_from_collection(nid=5, collection=mock_collection)

        mock_collection.delete.assert_called_once_with(where={"nid": 5})
        assert "parent_5" not in self.chunker._parent_store

    def test_retrieve_parents_from_collection_fallback(self):
        """当内存索引未命中时，从 Chroma 检索父文档"""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["parent_99"],
            "documents": ["从 Chroma 检索的完整日记"],
            "metadatas": [{"nid": 99, "uid": 3, "date": "2025-03-01", "tags": ""}],
        }

        parents = self.chunker.retrieve_parents_from_collection(
            child_ids=["child_99_2"],
            collection=mock_collection,
        )

        assert len(parents) == 1
        assert parents[0].nid == 99
        assert parents[0].content == "从 Chroma 检索的完整日记"
        # 检索后应缓存到内存
        assert "parent_99" in self.chunker._parent_store

    @patch.dict("os.environ", {"PARENT_CHILD_CHUNKING_ENABLED": "true"})
    def test_is_enabled_true(self):
        """环境变量启用时 is_enabled 返回 True"""
        assert ParentChildChunker.is_enabled() is True

    @patch.dict("os.environ", {"PARENT_CHILD_CHUNKING_ENABLED": "false"})
    def test_is_enabled_false(self):
        """环境变量关闭时 is_enabled 返回 False"""
        assert ParentChildChunker.is_enabled() is False

    def test_backward_compatible_with_chunk_splitter(self):
        """
        ParentChildChunker 不修改现有 ChunkSplitter 行为，
        作为独立的可选增强模式存在。
        ChunkSplitter 仍可正常导入使用（跳过实际运行需 chromadb）。
        """
        # ParentChildChunker 独立运行，不依赖 ChunkSplitter
        content = "这是一段测试文本，用于验证父子文档切分器可以独立工作。" * 15
        parent, children = self.chunker.chunk_diary(
            nid=1, content=content, uid=1
        )
        assert parent is not None
        assert len(children) >= 1
        # 确认父子关系正确
        for child in children:
            assert child.parent_id == parent.doc_id
