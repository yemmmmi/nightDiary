"""
种子数据脚本：生成 100 个用户 + 对应日记 + AI 分析记录
同时创建一个管理员账号 admin/admin123

运行方式：
  cd backend
  .\venv\Scripts\python.exe -m scripts.seed_users
"""

import random
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.analysis import Analysis
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ═══════════════════════════════════════════════════
# 数据模板
# ═══════════════════════════════════════════════════

FIRST_NAMES = [
    "小明", "小红", "小华", "小丽", "小强", "小芳", "小刚", "小美", "小军", "小燕",
    "志远", "雨萱", "浩然", "诗涵", "子轩", "梓涵", "一诺", "欣怡", "宇轩", "可馨",
    "思远", "雅琪", "博文", "语嫣", "天佑", "紫萱", "俊杰", "梦瑶", "文博", "雨桐",
]

DIARY_TEMPLATES = [
    "今天天气不错，心情也跟着好了起来。下午去公园散了步，看到了很多花开了。",
    "工作上遇到了一些挑战，但最终还是解决了。感觉自己在成长。",
    "和朋友聚了餐，聊了很多近况。好久没有这么开心了。",
    "今天学了新东西，虽然有点难，但很有成就感。",
    "有点累，但想想明天又是新的一天，就觉得还好。",
    "读了一本好书，里面有句话让我印象深刻：生活不止眼前的苟且。",
    "今天做了一顿好吃的饭，自己动手丰衣足食的感觉真好。",
    "下雨了，窝在家里看了部电影，很温馨的故事。",
    "跑步5公里，虽然很累但跑完后整个人都精神了。",
    "和家人视频通话了，虽然不在身边但感觉很温暖。",
    "今天加班到很晚，有点疲惫。但项目终于上线了，值得庆祝。",
    "周末去了趟图书馆，安静地看了一下午书，很充实。",
    "尝试了冥想，虽然只有10分钟，但感觉内心平静了很多。",
    "收到了一个好消息，努力终于有了回报！",
    "今天有点焦虑，不过写下来之后感觉好多了。",
    "去超市买了些水果，回来做了果汁，生活需要仪式感。",
    "和同事讨论了一个技术方案，碰撞出了不少好想法。",
    "今天早起看了日出，那一刻觉得世界很美好。",
    "整理了房间，扔掉了很多不需要的东西，感觉轻松了。",
    "晚上散步时看到了满天星星，好久没有这么宁静的感觉了。",
]

AI_RESPONSES = [
    "看到你今天过得充实，为你感到高兴。保持这样的节奏，每一天都在积累美好。",
    "工作中的挑战是成长的催化剂，你已经展现了很强的解决问题能力。",
    "社交连接对心理健康很重要，和朋友的相聚是很好的情绪充电。",
    "学习新事物的过程虽然辛苦，但你的坚持本身就值得肯定。",
    "允许自己疲惫是一种自我关怀，明天又是崭新的开始。",
    "阅读是很好的精神滋养，那些触动你的文字会在未来某个时刻给你力量。",
    "为自己做饭是一种很好的自我照顾方式，享受这个过程吧。",
    "雨天适合放慢脚步，给自己一些安静的时间也很重要。",
    "运动后的愉悦感是身体给你的奖励，坚持下去会越来越好。",
    "家人的陪伴即使隔着屏幕也能传递温暖，珍惜这份连接。",
]

WEATHERS = [
    "晴 28°C 湿度 45% 南风 2级",
    "多云 25°C 湿度 60% 东风 3级",
    "小雨 22°C 湿度 80% 北风 2级",
    "阴 20°C 湿度 70% 西风 1级",
    "晴 32°C 湿度 35% 南风 3级",
    "多云 27°C 湿度 55% 东南风 2级",
    None,
]

ADDRESSES = [
    "北京市朝阳区", "上海市浦东新区", "广州市天河区", "深圳市南山区",
    "杭州市西湖区", "成都市武侯区", "武汉市洪山区", "南京市鼓楼区",
    "西安市雁塔区", "重庆市渝北区", "苏州市工业园区", "长沙市岳麓区",
]


def seed_data():
    """生成种子数据"""
    db = SessionLocal()

    try:
        # 1. 创建管理员账号（如果不存在）
        admin = db.query(User).filter(User.user_name == "admin").first()
        if not admin:
            admin = User(
                user_name="admin",
                email="admin@yeji.com",
                password_hash=pwd_context.hash("admin123"),
                role="admin",
                gender="M",
                age=30,
                address="北京市海淀区",
            )
            db.add(admin)
            db.commit()
            print("✅ 管理员账号创建成功: admin / admin123")
        else:
            # 确保已有 admin 用户的 role 是 admin
            if admin.role != "admin":
                admin.role = "admin"
                db.commit()
            print("ℹ️  管理员账号已存在")

        # 2. 生成 100 个普通用户
        created_users = 0
        for i in range(1, 101):
            username = f"user_{i:03d}"
            existing = db.query(User).filter(User.user_name == username).first()
            if existing:
                continue

            name_base = random.choice(FIRST_NAMES)
            user = User(
                user_name=username,
                email=f"{username}@example.com",
                password_hash=pwd_context.hash("123456"),
                role="user",
                gender=random.choice(["M", "F", "Other"]),
                age=random.randint(18, 55),
                address=random.choice(ADDRESSES),
            )
            db.add(user)
            db.flush()  # 获取 UID

            # 3. 为每个用户生成 2-5 篇日记
            diary_count = random.randint(2, 5)
            for j in range(diary_count):
                days_ago = random.randint(0, 30)
                create_time = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23))

                content = random.choice(DIARY_TEMPLATES)
                # 添加一些个性化内容
                if random.random() > 0.5:
                    content += f"\n\n{random.choice(['感觉还不错。', '希望明天更好。', '继续加油！', '记录一下今天的心情。'])}"

                is_open = random.random() > 0.3  # 70% 公开

                entry = DiaryEntry(
                    UID=user.UID,
                    content=content,
                    is_open=is_open,
                    weather=random.choice(WEATHERS),
                    AI_ans=random.choice(AI_RESPONSES) if random.random() > 0.3 else None,
                    create_time=create_time,
                )
                db.add(entry)
                db.flush()

                # 4. 为有 AI 回应的日记生成分析记录
                if entry.AI_ans:
                    total_tokens = random.randint(200, 1500)
                    cache_hit = random.randint(0, int(total_tokens * 0.4))
                    output = random.randint(50, 400)
                    cache_miss = total_tokens - cache_hit - output

                    analysis = Analysis(
                        NID=entry.NID,
                        Thk_time=create_time + timedelta(seconds=random.randint(5, 30)),
                        Token_cost=total_tokens,
                        cache_hit_tokens=cache_hit,
                        cache_miss_tokens=max(0, cache_miss),
                        output_tokens=output,
                        diary_length=len(content),
                        agent_mode=random.choice(["multi_agent", "chain", "agent"]),
                        Thk_log=f"[{random.choice(['Multi-Agent', 'Chain', 'Agent'])}] intent={random.choice(['pure_record', 'emotional_support'])}",
                    )
                    db.add(analysis)

            created_users += 1

        db.commit()
        print(f"✅ 成功创建 {created_users} 个用户及对应数据")

        # 统计
        total_users = db.query(User).count()
        total_diaries = db.query(DiaryEntry).count()
        total_analyses = db.query(Analysis).count()
        print(f"\n📊 数据库统计:")
        print(f"   用户总数: {total_users}")
        print(f"   日记总数: {total_diaries}")
        print(f"   分析记录: {total_analyses}")

    except Exception as e:
        db.rollback()
        print(f"❌ 错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
