-- ============================================================
-- Multi-Agent AI Upgrade 数据库迁移脚本
-- 对应 spec: multi-agent-ai-upgrade
-- 要求: 9.4, 10.3, 12.5, 17.2, 24.8
-- ============================================================

-- 1. 为 analysis 表添加 agent_mode 和 activated_agents 列
ALTER TABLE `analysis`
  ADD COLUMN `agent_mode` VARCHAR(20) DEFAULT NULL COMMENT '分析模式: chain | agent | multi_agent',
  ADD COLUMN `activated_agents` TEXT DEFAULT NULL COMMENT 'JSON数组: ["retrieval","empathy","insight"]';

-- 2. 为 users 表添加 long_term_profile 列
ALTER TABLE `users`
  ADD COLUMN `long_term_profile` JSON DEFAULT NULL COMMENT '长期用户画像 JSON (UserProfile)';

-- 3. 创建 feedback 表 (用户反馈 / Thompson Sampling 信号)
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈记录表';

-- 4. 创建 style_preferences 表 (Thompson Sampling Beta 分布参数)
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户风格偏好 Thompson Sampling 参数';

-- 5. 创建 knowledge_entries 表 (结构化知识抽取)
CREATE TABLE IF NOT EXISTS `knowledge_entries` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `diary_nid` INT NOT NULL,
  `entity_type` VARCHAR(20) NOT NULL COMMENT 'person | event | place | topic',
  `entity_data` JSON NOT NULL COMMENT '实体数据 JSON: {"name":"...","relation":"...","sentiment":0.6}',
  `extracted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_knowledge_user_id` (`user_id`),
  INDEX `idx_knowledge_diary_nid` (`diary_nid`),
  INDEX `idx_knowledge_entity_type` (`entity_type`),
  CONSTRAINT `fk_knowledge_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`UID`) ON DELETE CASCADE,
  CONSTRAINT `fk_knowledge_diary` FOREIGN KEY (`diary_nid`) REFERENCES `diary_entries` (`NID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='结构化知识条目表';
