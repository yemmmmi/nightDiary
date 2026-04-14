"""
数据迁移脚本：将 MySQL 中已有的日记批量导入 Chroma 向量库
==========================================================

使用场景：
- 首次部署 Chroma RAG 功能时，MySQL 中已有历史日记数据
- 需要一次性将所有日记向量化并写入 Chroma

运行方式（在 backend 目录下）：
    python -m scripts.migrate_to_chroma

注意事项：
- 首次运行会下载 Embedding 模型（约 400MB），请确保网络通畅
- 迁移过程中不会修改 MySQL 数据，只是读取并写入 Chroma
- 可以重复运行（使用 upsert，不会产生重复数据）
"""

import sys
import os

# 确保能导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal
from app.models.user import User
from app.models.diary import DiaryEntry
from app.services.vector_service import bulk_import_user_diaries


def main():
    print("=" * 60)
    print("  日记数据迁移：MySQL → Chroma 向量库")
    print("=" * 60)

    db = SessionLocal()

    try:
        # 获取所有用户
        users = db.query(User).all()
        print(f"\n共 {len(users)} 个用户")

        total_imported = 0

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

            # 构建迁移数据
            diaries = []
            for entry in entries:
                tags_str = ""
                if entry.tags:
                    tags_str = "、".join(f"#{t.tag_name}" for t in entry.tags if t.tag_name)

                diaries.append({
                    "nid": entry.NID,
                    "content": entry.content or "",
                    "date": entry.create_time.strftime("%Y-%m-%d") if entry.create_time else "",
                    "tags": tags_str,
                })

            # 批量导入
            imported = bulk_import_user_diaries(
                user_id=user.UID,
                diaries=diaries,
            )
            total_imported += imported
            print(f"  用户 {user.user_name}(UID={user.UID}): 导入 {imported}/{len(entries)} 篇日记")

        print(f"\n迁移完成！共导入 {total_imported} 篇日记到 Chroma 向量库。")

    finally:
        db.close()


if __name__ == "__main__":
    main()
