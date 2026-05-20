"""
Multi-Agent AI Upgrade 数据库迁移脚本
对应 spec: multi-agent-ai-upgrade
要求: 9.4, 10.3, 12.5, 17.2, 24.8

用法:
    cd backend
    python -m scripts.migrate_multi_agent
"""

import sys
import os
from pathlib import Path

# 确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.core.database import engine


MIGRATIONS = [
    # 1. analysis 表新增列
    {
        "name": "Add agent_mode column to analysis",
        "check": "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_NAME='analysis' AND COLUMN_NAME='agent_mode'",
        "sql": "ALTER TABLE `analysis` ADD COLUMN `agent_mode` VARCHAR(20) DEFAULT NULL COMMENT '分析模式: chain | agent | multi_agent'",
    },
    {
        "name": "Add activated_agents column to analysis",
        "check": "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_NAME='analysis' AND COLUMN_NAME='activated_agents'",
        "sql": "ALTER TABLE `analysis` ADD COLUMN `activated_agents` TEXT DEFAULT NULL COMMENT 'JSON数组: [\"retrieval\",\"empathy\",\"insight\"]'",
    },
    # 2. users 表新增列
    {
        "name": "Add long_term_profile column to users",
        "check": "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_NAME='users' AND COLUMN_NAME='long_term_profile'",
        "sql": "ALTER TABLE `users` ADD COLUMN `long_term_profile` JSON DEFAULT NULL COMMENT '长期用户画像 JSON (UserProfile)'",
    },
    # 3. feedback 表
    {
        "name": "Create feedback table",
        "check": "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_NAME='feedback'",
        "sql": """
            CREATE TABLE IF NOT EXISTS `feedback` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `user_id` INT NOT NULL,
                `diary_nid` INT NOT NULL,
                `response_style` VARCHAR(30) NOT NULL COMMENT 'empathetic | practical | philosophical | humorous',
                `feedback_type` VARCHAR(10) NOT NULL COMMENT 'positive | negative',
                `reason` VARCHAR(50) DEFAULT NULL COMMENT 'too_long | too_short | irrelevant | too_generic | lacks_suggestion',
                `source` VARCHAR(10) NOT NULL COMMENT 'explicit | implicit',
                `signal_type` VARCHAR(30) DEFAULT NULL COMMENT 'read_complete | inspired_writing | frequent_usage',
                `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                INDEX `idx_feedback_user_id` (`user_id`),
                INDEX `idx_feedback_diary_nid` (`diary_nid`),
                CONSTRAINT `fk_feedback_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`UID`) ON DELETE CASCADE,
                CONSTRAINT `fk_feedback_diary` FOREIGN KEY (`diary_nid`) REFERENCES `diary_entries` (`NID`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈记录表'
        """,
    },
    # 4. style_preferences 表
    {
        "name": "Create style_preferences table",
        "check": "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_NAME='style_preferences'",
        "sql": """
            CREATE TABLE IF NOT EXISTS `style_preferences` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `user_id` INT NOT NULL,
                `style` VARCHAR(30) NOT NULL COMMENT 'empathetic | practical | philosophical | humorous',
                `alpha` FLOAT NOT NULL DEFAULT 1.0 COMMENT 'Beta分布 alpha 参数',
                `beta` FLOAT NOT NULL DEFAULT 1.0 COMMENT 'Beta分布 beta 参数',
                `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                INDEX `idx_style_pref_user_id` (`user_id`),
                UNIQUE INDEX `uq_style_pref_user_style` (`user_id`, `style`),
                CONSTRAINT `fk_style_pref_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`UID`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户风格偏好 Thompson Sampling 参数'
        """,
    },
    # 5. knowledge_entries 表
    {
        "name": "Create knowledge_entries table",
        "check": "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_NAME='knowledge_entries'",
        "sql": """
            CREATE TABLE IF NOT EXISTS `knowledge_entries` (
                `id` INT NOT NULL AUTO_INCREMENT,
                `user_id` INT NOT NULL,
                `diary_nid` INT NOT NULL,
                `entity_type` VARCHAR(20) NOT NULL COMMENT 'person | event | place | topic',
                `entity_data` JSON NOT NULL COMMENT '实体数据 JSON',
                `extracted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                INDEX `idx_knowledge_user_id` (`user_id`),
                INDEX `idx_knowledge_diary_nid` (`diary_nid`),
                INDEX `idx_knowledge_entity_type` (`entity_type`),
                CONSTRAINT `fk_knowledge_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`UID`) ON DELETE CASCADE,
                CONSTRAINT `fk_knowledge_diary` FOREIGN KEY (`diary_nid`) REFERENCES `diary_entries` (`NID`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='结构化知识条目表'
        """,
    },
]


def run_migrations():
    """执行所有迁移（幂等，已存在则跳过）"""
    print("=" * 60)
    print("Multi-Agent AI Upgrade - 数据库迁移")
    print("=" * 60)

    with engine.connect() as conn:
        for migration in MIGRATIONS:
            name = migration["name"]
            check_sql = migration["check"]
            exec_sql = migration["sql"]

            # 检查是否已执行
            result = conn.execute(text(check_sql))
            count = result.scalar()

            if count and count > 0:
                print(f"  [SKIP] {name} (已存在)")
                continue

            # 执行迁移
            try:
                conn.execute(text(exec_sql))
                conn.commit()
                print(f"  [OK]   {name}")
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                raise

    print("\n迁移完成！")


if __name__ == "__main__":
    run_migrations()
