"""
数据迁移脚本：将现有整篇日记向量迁移到 Chunk 模式
==========================================================

使用场景：
- 升级到企业级 RAG 架构后，需要将旧的整篇日记向量（diary_{nid}）
  迁移为新的 chunk 向量（diary_{nid}_chunk_{i}）
- 支持增量迁移：已有 chunk 向量的日记会被跳过

运行方式（在 backend 目录下）：
    python -m scripts.migrate_to_enterprise_rag

注意事项：
- 首次运行会下载 Embedding 模型(约 400MB)，请确保网络通畅
- 迁移过程中不会修改 MySQL 数据，只操作 Chroma 向量库
- 可以重复运行（增量迁移，跳过已处理的日记）
- 异常时记录失败的日记 ID 并继续处理剩余日记
"""

import sys
import os
import time

# 确保能导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal
from app.models.user import User
from app.models.diary import DiaryEntry
from app.services.vector_service import (
    ChunkSplitter,
    _get_user_collection,
)


def _is_diary_already_migrated(collection, nid: int) -> bool:
    """
    检查某篇日记是否已经迁移到 chunk 模式。
    通过查询 doc_id 中包含 '_chunk_' 的文档来判断。
    """
    try:
        # 查询该 nid 的所有文档
        results = collection.get(
            where={"nid": nid},
            include=[],
        )
        if results and results["ids"]:
            # 检查是否有 chunk 格式的 doc_id
            for doc_id in results["ids"]:
                if "_chunk_" in doc_id:
                    return True
        return False
    except Exception:
        return False


def _delete_old_whole_diary_vector(collection, nid: int) -> bool:
    """
    删除旧的整篇日记向量（doc_id 格式为 diary_{nid}，不含 _chunk_）。
    返回是否成功删除。
    """
    old_doc_id = f"diary_{nid}"
    try:
        # 尝试删除旧格式的整篇向量
        collection.delete(ids=[old_doc_id])
        return True
    except Exception:
        # 旧向量可能不存在，忽略错误
        return False


def migrate():
    """
    将现有整篇日记向量迁移到 chunk 模式。

    流程：
    1. 遍历所有用户的日记
    2. 对每篇日记检查是否已迁移（增量迁移）
    3. 删除旧的整篇向量（diary_{nid}）
    4. 使用 ChunkSplitter 切分日记内容
    5. 写入新的 chunk 向量（diary_{nid}_chunk_{i}）
    6. 异常时记录失败 ID，继续处理
    7. 最终输出迁移报告
    """
    print("=" * 60)
    print("  企业级 RAG 迁移：整篇日记向量 → Chunk 模式")
    print("=" * 60)

    start_time = time.time()
    db = SessionLocal()
    splitter = ChunkSplitter()

    # 统计数据
    total_users = 0
    total_diaries = 0
    migrated_count = 0
    skipped_count = 0
    failed_ids: list[tuple[int, int, str]] = []  # (uid, nid, error_msg)

    try:
        # 获取所有用户
        users = db.query(User).all()
        total_users = len(users)
        print(f"\n共 {total_users} 个用户")

        for user in users:
            # 获取该用户的所有日记
            entries = (
                db.query(DiaryEntry)
                .filter(DiaryEntry.UID == user.UID)
                .all()
            )

            if not entries:
                print(f"  用户 {user.user_name}(UID={user.UID}): 无日记，跳过")
                continue

            user_migrated = 0
            user_skipped = 0
            user_failed = 0

            try:
                collection = _get_user_collection(user.UID)
            except Exception as exc:
                error_msg = f"获取 Collection 失败: {exc}"
                print(f"  用户 {user.user_name}(UID={user.UID}): {error_msg}")
                for entry in entries:
                    failed_ids.append((user.UID, entry.NID, error_msg))
                continue

            for entry in entries:
                total_diaries += 1
                nid = entry.NID

                try:
                    # 增量迁移：检查是否已有 chunk 向量
                    if _is_diary_already_migrated(collection, nid):
                        user_skipped += 1
                        skipped_count += 1
                        continue

                    content = entry.content or ""
                    if not content.strip():
                        user_skipped += 1
                        skipped_count += 1
                        continue

                    # 构建标签字符串
                    tags_str = ""
                    if entry.tags:
                        tags_str = "、".join(
                            f"#{t.tag_name}" for t in entry.tags if t.tag_name
                        )

                    date_str = (
                        entry.create_time.strftime("%Y-%m-%d")
                        if entry.create_time
                        else ""
                    )

                    # 1. 删除旧的整篇向量
                    _delete_old_whole_diary_vector(collection, nid)

                    # 2. 使用 ChunkSplitter 切分
                    chunk_dicts = splitter.split_with_metadata(
                        content,
                        nid=nid,
                        uid=user.UID,
                        date_str=date_str,
                        tags_str=tags_str,
                    )

                    # 3. 写入新的 chunk 向量
                    ids = [
                        f"diary_{nid}_chunk_{cd['chunk_index']}"
                        for cd in chunk_dicts
                    ]
                    documents = [cd["content"] for cd in chunk_dicts]
                    metadatas = [
                        {
                            "nid": nid,
                            "uid": user.UID,
                            "date": cd["date"],
                            "tags": cd["tags"],
                            "chunk_index": cd["chunk_index"],
                            "chunk_total": cd["chunk_total"],
                        }
                        for cd in chunk_dicts
                    ]

                    collection.upsert(
                        ids=ids, documents=documents, metadatas=metadatas
                    )

                    user_migrated += 1
                    migrated_count += 1

                except Exception as exc:
                    error_msg = str(exc)
                    failed_ids.append((user.UID, nid, error_msg))
                    user_failed += 1
                    print(
                        f"    ✗ 日记 NID={nid} 迁移失败: {error_msg}"
                    )

            print(
                f"  用户 {user.user_name}(UID={user.UID}): "
                f"迁移 {user_migrated} 篇, "
                f"跳过 {user_skipped} 篇, "
                f"失败 {user_failed} 篇"
            )

        # ── 输出迁移报告 ──
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("  迁移报告")
        print("=" * 60)
        print(f"  总用户数:     {total_users}")
        print(f"  总日记数:     {total_diaries}")
        print(f"  成功迁移:     {migrated_count}")
        print(f"  跳过(已迁移): {skipped_count}")
        print(f"  失败:         {len(failed_ids)}")
        print(f"  耗时:         {elapsed:.2f} 秒")

        if failed_ids:
            print("\n  失败详情:")
            for uid, nid, err in failed_ids:
                print(f"    - UID={uid}, NID={nid}: {err}")

        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
