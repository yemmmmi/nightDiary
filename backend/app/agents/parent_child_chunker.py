"""
ParentChildChunker — 父子文档切分器
====================================

实现"小 chunk 检索 + 大 chunk 返回"策略：
- 父文档：每篇日记的完整内容（一篇日记 = 一个父文档）
- 子文档：200-300 字符的语义聚焦块，元数据中包含 parent_id 引用

当语义搜索命中子块时，可通过 retrieve_parents 方法检索完整父文档，
为 LLM 提供连贯的上下文，避免截断造成的信息割裂。

与现有 ChunkSplitter 后向兼容：
- ParentChildChunker 作为可选增强模式，可按用户或全局开关启用
- 未启用时，系统继续使用原有 ChunkSplitter 行为
- 启用时，同时维护父文档和子文档，更新操作原子执行

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  数据模型                                                     ║
# ╚══════════════════════════════════════════════════════════════╝

@dataclass
class ParentDoc:
    """父文档：对应一篇完整日记。"""
    doc_id: str          # 格式: "parent_{nid}"
    nid: int             # 日记 NID
    uid: int             # 用户 ID
    content: str         # 完整日记内容
    date: str = ""       # 日期字符串
    tags: str = ""       # 标签字符串

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "nid": self.nid,
            "uid": self.uid,
            "date": self.date,
            "tags": self.tags,
            "doc_type": "parent",
            "chunk_index": 0,
            "chunk_total": 1,
        }


@dataclass
class ChildDoc:
    """子文档：父文档的语义聚焦切片。"""
    doc_id: str          # 格式: "child_{nid}_{chunk_index}"
    parent_id: str       # 引用父文档 ID: "parent_{nid}"
    nid: int             # 日记 NID
    uid: int             # 用户 ID
    content: str         # 子块内容（200-300 字符）
    chunk_index: int     # 子块序号
    chunk_total: int     # 子块总数
    date: str = ""
    tags: str = ""

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "nid": self.nid,
            "uid": self.uid,
            "date": self.date,
            "tags": self.tags,
            "doc_type": "child",
            "parent_id": self.parent_id,
            "chunk_index": self.chunk_index,
            "chunk_total": self.chunk_total,
        }


# ╔══════════════════════════════════════════════════════════════╗
# ║  ParentChildChunker                                           ║
# ╚══════════════════════════════════════════════════════════════╝

class ParentChildChunker:
    """
    父子文档切分器：以日记为父文档，切分为 200-300 字符的子文档。

    使用方式：
        chunker = ParentChildChunker()
        parent, children = chunker.chunk_diary(nid=1, content="...", uid=1)
        parents = chunker.retrieve_parents(child_ids=["child_1_0", "child_1_2"])

    与 ChunkSplitter 的关系：
    - ChunkSplitter：通用切分器，chunk_size 默认 512，用于标准 RAG
    - ParentChildChunker：增强模式，子块 200-300 字符用于精确检索，
      父块（完整日记）用于提供上下文
    """

    # 子文档切分参数
    CHILD_CHUNK_SIZE = 250    # 目标子块大小（字符）
    CHILD_CHUNK_MIN = 200     # 子块最小长度
    CHILD_CHUNK_MAX = 300     # 子块最大长度
    CHILD_OVERLAP = 30        # 相邻子块重叠字符数
    MIN_CONTENT_LENGTH = 50   # 低于此长度不切分子块，直接作为单个子块

    def __init__(
        self,
        child_chunk_size: Optional[int] = None,
        child_overlap: Optional[int] = None,
    ):
        """
        :param child_chunk_size: 子块目标大小，默认 250 字符
        :param child_overlap: 子块重叠大小，默认 30 字符
        """
        self.child_chunk_size = child_chunk_size or int(
            os.getenv("PARENT_CHILD_CHUNK_SIZE", str(self.CHILD_CHUNK_SIZE))
        )
        self.child_overlap = child_overlap or int(
            os.getenv("PARENT_CHILD_OVERLAP", str(self.CHILD_OVERLAP))
        )

        # 中文标点优化的分隔符优先级
        self._separators = ["\n\n", "\n", "。", "！", "？", "；", "，", ".", "!", "?", " ", ""]

        # 内存中的父文档索引：parent_id -> ParentDoc
        self._parent_store: Dict[str, ParentDoc] = {}

    def _split_text(self, text: str) -> List[str]:
        """
        递归字符切分：按分隔符优先级切分文本为 child_chunk_size 大小的块。

        算法逻辑：
        1. 依次尝试分隔符，找到能将文本拆分的最高优先级分隔符
        2. 按该分隔符拆分后，贪心合并相邻片段直到达到 chunk_size
        3. 相邻块之间保留 child_overlap 的重叠

        :param text: 待切分文本
        :return: 切分后的文本块列表
        """
        return self._recursive_split(text, self._separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """递归切分实现"""
        if len(text) <= self.child_chunk_size:
            return [text] if text.strip() else []

        # 找到能有效拆分的分隔符
        separator = ""
        for sep in separators:
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                break

        # 按分隔符拆分
        if separator:
            splits = text.split(separator)
            # 保留分隔符（附加到前一段末尾）
            if separator != "":
                merged_splits = []
                for i, s in enumerate(splits):
                    if i < len(splits) - 1:
                        merged_splits.append(s + separator)
                    else:
                        if s:
                            merged_splits.append(s)
                splits = merged_splits
        else:
            # 空字符串分隔符 = 逐字符切分
            splits = list(text)

        # 贪心合并相邻片段
        chunks = []
        current_chunk = ""

        for split in splits:
            if not split:
                continue
            if len(current_chunk) + len(split) <= self.child_chunk_size:
                current_chunk += split
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    # 重叠：取当前块末尾的 overlap 字符作为下一块开头
                    if self.child_overlap > 0 and len(current_chunk) > self.child_overlap:
                        overlap_text = current_chunk[-self.child_overlap:]
                        current_chunk = overlap_text + split
                    else:
                        current_chunk = split
                else:
                    # 单个片段超过 chunk_size，需要进一步切分
                    if len(split) > self.child_chunk_size:
                        # 用下一级分隔符递归切分
                        remaining_seps = separators[separators.index(separator) + 1:] if separator in separators else [""]
                        sub_chunks = self._recursive_split(split, remaining_seps if remaining_seps else [""])
                        chunks.extend(sub_chunks[:-1] if sub_chunks else [])
                        current_chunk = sub_chunks[-1] if sub_chunks else ""
                    else:
                        current_chunk = split

        if current_chunk.strip():
            chunks.append(current_chunk)

        return [c for c in chunks if c.strip()]

    def chunk_diary(
        self,
        nid: int,
        content: str,
        uid: int = 0,
        date_str: str = "",
        tags_str: str = "",
    ) -> Tuple[ParentDoc, List[ChildDoc]]:
        """
        将一篇日记切分为父文档 + 子文档列表。

        :param nid: 日记 NID
        :param content: 日记完整内容
        :param uid: 用户 ID
        :param date_str: 日期字符串
        :param tags_str: 标签字符串
        :return: (ParentDoc, [ChildDoc, ...])
        """
        parent_id = f"parent_{nid}"

        # 创建父文档
        parent = ParentDoc(
            doc_id=parent_id,
            nid=nid,
            uid=uid,
            content=content,
            date=date_str,
            tags=tags_str,
        )

        # 存入内存索引
        self._parent_store[parent_id] = parent

        # 切分子文档
        if len(content) < self.MIN_CONTENT_LENGTH:
            # 短文本不切分，直接作为一个子块
            children = [
                ChildDoc(
                    doc_id=f"child_{nid}_0",
                    parent_id=parent_id,
                    nid=nid,
                    uid=uid,
                    content=content,
                    chunk_index=0,
                    chunk_total=1,
                    date=date_str,
                    tags=tags_str,
                )
            ]
        else:
            chunks = self._split_text(content)
            total = len(chunks)
            children = [
                ChildDoc(
                    doc_id=f"child_{nid}_{i}",
                    parent_id=parent_id,
                    nid=nid,
                    uid=uid,
                    content=chunk,
                    chunk_index=i,
                    chunk_total=total,
                    date=date_str,
                    tags=tags_str,
                )
                for i, chunk in enumerate(chunks)
            ]

        return parent, children

    def retrieve_parents(self, child_ids: List[str]) -> List[ParentDoc]:
        """
        从子块 ID 列表检索对应的父文档。

        :param child_ids: 子块 ID 列表，格式 "child_{nid}_{chunk_index}"
        :return: 去重后的父文档列表
        """
        parent_ids = set()
        for child_id in child_ids:
            parent_id = self._extract_parent_id(child_id)
            if parent_id:
                parent_ids.add(parent_id)

        parents = []
        for pid in parent_ids:
            parent = self._parent_store.get(pid)
            if parent:
                parents.append(parent)
            else:
                logger.warning("父文档不在内存索引中: %s", pid)

        return parents

    def retrieve_parents_from_collection(
        self,
        child_ids: List[str],
        collection,
    ) -> List[ParentDoc]:
        """
        从 Chroma Collection 中根据子块 ID 检索父文档。

        当内存索引未命中时（如服务重启后），从 Chroma 持久化存储中检索。

        :param child_ids: 子块 ID 列表
        :param collection: Chroma Collection 对象
        :return: 去重后的父文档列表
        """
        parent_ids = set()
        for child_id in child_ids:
            parent_id = self._extract_parent_id(child_id)
            if parent_id:
                parent_ids.add(parent_id)

        if not parent_ids:
            return []

        parents = []
        for pid in parent_ids:
            # 优先查内存
            if pid in self._parent_store:
                parents.append(self._parent_store[pid])
                continue

            # 从 Chroma 查询
            try:
                result = collection.get(
                    ids=[pid],
                    include=["documents", "metadatas"],
                )
                if result and result["ids"]:
                    doc = result["documents"][0] if result["documents"] else ""
                    meta = result["metadatas"][0] if result["metadatas"] else {}
                    parent = ParentDoc(
                        doc_id=pid,
                        nid=meta.get("nid", 0),
                        uid=meta.get("uid", 0),
                        content=doc,
                        date=meta.get("date", ""),
                        tags=meta.get("tags", ""),
                    )
                    # 缓存到内存索引
                    self._parent_store[pid] = parent
                    parents.append(parent)
            except Exception as exc:
                logger.warning("从 Chroma 检索父文档失败 %s: %s", pid, exc)

        return parents

    def store_to_collection(
        self,
        parent: ParentDoc,
        children: List[ChildDoc],
        collection,
    ) -> None:
        """
        将父文档和子文档原子性写入 Chroma Collection。

        先删除该 nid 的所有旧文档（父+子），再批量写入新文档。
        确保更新操作的原子性：不会出现只有子块没有父块的情况。

        :param parent: 父文档
        :param children: 子文档列表
        :param collection: Chroma Collection 对象
        """
        nid = parent.nid

        # 1. 删除该 nid 的所有旧文档（父+子）
        try:
            collection.delete(where={"nid": nid})
        except Exception as exc:
            logger.warning("删除旧父子文档失败 nid=%d: %s", nid, exc)

        # 2. 批量写入父文档 + 子文档
        ids = [parent.doc_id] + [child.doc_id for child in children]
        documents = [parent.content] + [child.content for child in children]
        metadatas = [parent.to_metadata()] + [child.to_metadata() for child in children]

        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            logger.debug(
                "父子文档写入 Chroma: nid=%d, 1 parent + %d children",
                nid, len(children),
            )
        except Exception as exc:
            logger.error("父子文档写入 Chroma 失败 nid=%d: %s", nid, exc)
            raise

    def delete_from_collection(self, nid: int, collection) -> None:
        """
        从 Chroma Collection 中删除指定 nid 的所有父子文档。

        :param nid: 日记 NID
        :param collection: Chroma Collection 对象
        """
        try:
            collection.delete(where={"nid": nid})
            # 同时清理内存索引
            parent_id = f"parent_{nid}"
            self._parent_store.pop(parent_id, None)
            logger.debug("父子文档已删除: nid=%d", nid)
        except Exception as exc:
            logger.error("删除父子文档失败 nid=%d: %s", nid, exc)

    @staticmethod
    def _extract_parent_id(child_id: str) -> Optional[str]:
        """
        从子块 ID 提取父文档 ID。

        child_id 格式: "child_{nid}_{chunk_index}"
        parent_id 格式: "parent_{nid}"
        """
        if not child_id or not child_id.startswith("child_"):
            return None

        parts = child_id.split("_")
        if len(parts) >= 3:
            # parts: ["child", "{nid}", "{chunk_index}"]
            nid_str = parts[1]
            return f"parent_{nid_str}"
        return None

    @staticmethod
    def is_enabled() -> bool:
        """
        检查父子文档模式是否全局启用。

        通过环境变量 PARENT_CHILD_CHUNKING_ENABLED 控制，
        默认关闭（保持与现有 ChunkSplitter 的后向兼容）。
        """
        return os.getenv("PARENT_CHILD_CHUNKING_ENABLED", "false").lower() in (
            "true", "1", "yes",
        )


# 全局 ParentChildChunker 单例
_parent_child_chunker: Optional[ParentChildChunker] = None


def get_parent_child_chunker() -> ParentChildChunker:
    """获取 ParentChildChunker 全局单例。"""
    global _parent_child_chunker
    if _parent_child_chunker is None:
        _parent_child_chunker = ParentChildChunker()
    return _parent_child_chunker
