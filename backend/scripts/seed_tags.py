"""
种子标签脚本：导入常用日记标签

运行方式：
  cd backend
  .\venv\Scripts\python.exe -m scripts.seed_tags
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.tag import Tag

# 常用日记标签（已审核状态）
SEED_TAGS = [
    # 生活类
    {"tag_name": "日常", "color": "#6B7280", "creator": "admin"},
    {"tag_name": "工作", "color": "#3B82F6", "creator": "admin"},
    {"tag_name": "学习", "color": "#8B5CF6", "creator": "admin"},
    {"tag_name": "运动", "color": "#10B981", "creator": "admin"},
    {"tag_name": "美食", "color": "#F59E0B", "creator": "admin"},
    {"tag_name": "旅行", "color": "#06B6D4", "creator": "admin"},
    {"tag_name": "阅读", "color": "#6366F1", "creator": "admin"},
    {"tag_name": "音乐", "color": "#EC4899", "creator": "admin"},
    {"tag_name": "电影", "color": "#EF4444", "creator": "admin"},
    {"tag_name": "购物", "color": "#F97316", "creator": "admin"},
    # 情绪类
    {"tag_name": "开心", "color": "#FBBF24", "creator": "admin"},
    {"tag_name": "感恩", "color": "#34D399", "creator": "admin"},
    {"tag_name": "焦虑", "color": "#F87171", "creator": "admin"},
    {"tag_name": "疲惫", "color": "#9CA3AF", "creator": "admin"},
    {"tag_name": "平静", "color": "#93C5FD", "creator": "admin"},
    {"tag_name": "期待", "color": "#C084FC", "creator": "admin"},
    # 社交类
    {"tag_name": "家人", "color": "#FB923C", "creator": "admin"},
    {"tag_name": "朋友", "color": "#A78BFA", "creator": "admin"},
    {"tag_name": "恋爱", "color": "#F472B6", "creator": "admin"},
    # 成长类
    {"tag_name": "反思", "color": "#64748B", "creator": "admin"},
    {"tag_name": "目标", "color": "#14B8A6", "creator": "admin"},
    {"tag_name": "灵感", "color": "#E879F9", "creator": "admin"},
    {"tag_name": "梦境", "color": "#818CF8", "creator": "admin"},
    {"tag_name": "健康", "color": "#22C55E", "creator": "admin"},
    {"tag_name": "财务", "color": "#EAB308", "creator": "admin"},
]


def seed_tags():
    db = SessionLocal()
    created = 0
    skipped = 0

    try:
        for tag_data in SEED_TAGS:
            existing = db.query(Tag).filter(Tag.tag_name == tag_data["tag_name"]).first()
            if existing:
                # 确保已有标签状态为 approved
                if existing.status != "approved":
                    existing.status = "approved"
                skipped += 1
                continue

            tag = Tag(
                tag_name=tag_data["tag_name"],
                color=tag_data["color"],
                creator=tag_data["creator"],
                status="approved",
                usage_count=0,
            )
            db.add(tag)
            created += 1

        db.commit()
        print(f"✅ 标签导入完成: 新增 {created} 个, 跳过 {skipped} 个已存在")
        print(f"   总计 {db.query(Tag).count()} 个标签")

    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_tags()
