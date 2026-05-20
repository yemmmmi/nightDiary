"""
长期记忆模块 — Long-Term Memory (MySQL JSON)
=============================================

基于 User.long_term_profile JSON 字段，管理用户长期画像。

功能：
- get_profile(): 读取用户画像
- update_profile(): 更新画像并记录变更前后值
- promote_from_episodic(): 连续 3 天出现的情绪主题/话题提升到画像

画像字段：
- personality_tags: 性格标签
- emotion_baseline: 情绪基线（平均情感值、波动性、主导情绪）
- important_people: 重要人物
- recurring_topics: 反复出现的话题
- preferred_response_style: 偏好回应风格
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.memory import EpisodicEntry, UserProfile

logger = logging.getLogger(__name__)


class LongTermMemory:
    """长期记忆，基于 MySQL User.long_term_profile JSON 字段。"""

    # 连续出现天数阈值，达到此值后将话题/情绪提升到画像
    PROMOTION_THRESHOLD_DAYS = 3

    def get_profile(self, db: Session, user_id: int) -> UserProfile:
        """
        从 User.long_term_profile JSON 字段读取用户画像。

        如果字段为空或解析失败，返回默认空画像。
        """
        user = db.query(User).filter(User.UID == user_id).first()
        if not user:
            logger.warning(f"用户 {user_id} 不存在，返回默认画像")
            return UserProfile()

        if not user.long_term_profile:
            logger.info(f"用户 {user_id} 尚无长期画像，返回默认画像")
            return UserProfile()

        try:
            profile = UserProfile.model_validate_json(user.long_term_profile)
            return profile
        except Exception as e:
            logger.error(f"解析用户 {user_id} 长期画像失败: {e}，返回默认画像")
            return UserProfile()

    def update_profile(self, db: Session, user_id: int, profile: UserProfile) -> None:
        """
        更新用户画像并记录变更前后值（用于审计）。

        Args:
            db: 数据库会话
            user_id: 用户 ID
            profile: 新的用户画像
        """
        user = db.query(User).filter(User.UID == user_id).first()
        if not user:
            logger.error(f"用户 {user_id} 不存在，无法更新画像")
            return

        # 读取旧画像用于审计日志
        old_profile_json = user.long_term_profile
        if old_profile_json:
            try:
                old_profile = UserProfile.model_validate_json(old_profile_json)
            except Exception:
                old_profile = UserProfile()
        else:
            old_profile = UserProfile()

        # 序列化并保存新画像
        new_profile_json = profile.model_dump_json()
        user.long_term_profile = new_profile_json
        db.commit()

        # 记录变更前后值
        self._log_profile_changes(user_id, old_profile, profile)

    def promote_from_episodic(
        self,
        db: Session,
        user_id: int,
        episodic_entries: list[EpisodicEntry],
    ) -> None:
        """
        从情景记忆中提升连续 3 天出现的情绪主题/话题到长期画像。

        规则：如果同一 emotion 或 event 关键词在连续 3 天（或以上）
        的 EpisodicEntry 中出现，则将其提升到用户画像的
        recurring_topics 或更新 emotion_baseline。

        Args:
            db: 数据库会话
            user_id: 用户 ID
            episodic_entries: 近期情景记忆条目列表
        """
        if not episodic_entries:
            logger.info(f"用户 {user_id} 无情景记忆条目，跳过提升")
            return

        profile = self.get_profile(db, user_id)

        # 按日期分组条目
        entries_by_date: dict[str, list[EpisodicEntry]] = {}
        for entry in episodic_entries:
            date_key = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d")
            entries_by_date.setdefault(date_key, []).append(entry)

        # 提取每天的情绪和话题
        daily_emotions: dict[str, set[str]] = {}
        daily_topics: dict[str, set[str]] = {}
        for date_key, entries in entries_by_date.items():
            daily_emotions[date_key] = {e.emotion for e in entries if e.emotion}
            daily_topics[date_key] = {e.event for e in entries if e.event}

        # 找出连续出现 >= PROMOTION_THRESHOLD_DAYS 天的情绪
        promoted_emotions = self._find_consecutive_items(
            daily_emotions, self.PROMOTION_THRESHOLD_DAYS
        )

        # 找出连续出现 >= PROMOTION_THRESHOLD_DAYS 天的话题
        promoted_topics = self._find_consecutive_items(
            daily_topics, self.PROMOTION_THRESHOLD_DAYS
        )

        updated = False

        # 提升话题到 recurring_topics
        for topic in promoted_topics:
            if topic not in profile.recurring_topics:
                profile.recurring_topics.append(topic)
                logger.info(
                    f"用户 {user_id}: 话题 '{topic}' 连续出现 "
                    f">= {self.PROMOTION_THRESHOLD_DAYS} 天，提升到画像"
                )
                updated = True

        # 提升情绪到 emotion_baseline.dominant_emotion（如果频率最高）
        if promoted_emotions:
            # 统计所有被提升情绪的出现频率
            emotion_counts: Counter[str] = Counter()
            for date_key, emotions in daily_emotions.items():
                for emotion in emotions:
                    if emotion in promoted_emotions:
                        emotion_counts[emotion] += 1

            most_common_emotion = emotion_counts.most_common(1)[0][0]
            if profile.emotion_baseline.dominant_emotion != most_common_emotion:
                profile.emotion_baseline.dominant_emotion = most_common_emotion
                logger.info(
                    f"用户 {user_id}: 情绪 '{most_common_emotion}' 连续出现 "
                    f">= {self.PROMOTION_THRESHOLD_DAYS} 天，更新为主导情绪"
                )
                updated = True

        if updated:
            self.update_profile(db, user_id, profile)
        else:
            logger.info(f"用户 {user_id}: 无需提升，画像无变更")

    def _find_consecutive_items(
        self,
        daily_items: dict[str, set[str]],
        threshold: int,
    ) -> set[str]:
        """
        找出在连续 >= threshold 天中都出现的项目。

        Args:
            daily_items: 按日期分组的项目集合 {"2024-01-01": {"item1", "item2"}, ...}
            threshold: 连续天数阈值

        Returns:
            满足连续天数条件的项目集合
        """
        if not daily_items:
            return set()

        # 按日期排序
        sorted_dates = sorted(daily_items.keys())
        promoted: set[str] = set()

        # 收集所有出现过的项目
        all_items: set[str] = set()
        for items in daily_items.values():
            all_items.update(items)

        # 对每个项目检查是否连续出现
        for item in all_items:
            consecutive_count = 0
            max_consecutive = 0
            prev_date: Optional[datetime] = None

            for date_str in sorted_dates:
                current_date = datetime.strptime(date_str, "%Y-%m-%d")

                if item in daily_items[date_str]:
                    if prev_date is None or (current_date - prev_date).days == 1:
                        consecutive_count += 1
                    else:
                        consecutive_count = 1
                    max_consecutive = max(max_consecutive, consecutive_count)
                    prev_date = current_date
                else:
                    consecutive_count = 0
                    prev_date = None

            if max_consecutive >= threshold:
                promoted.add(item)

        return promoted

    def _log_profile_changes(
        self,
        user_id: int,
        old_profile: UserProfile,
        new_profile: UserProfile,
    ) -> None:
        """记录画像变更的前后值，用于审计。"""
        changes: list[str] = []

        if old_profile.personality_tags != new_profile.personality_tags:
            changes.append(
                f"personality_tags: {old_profile.personality_tags} -> {new_profile.personality_tags}"
            )

        if old_profile.emotion_baseline != new_profile.emotion_baseline:
            changes.append(
                f"emotion_baseline: {old_profile.emotion_baseline.model_dump()} "
                f"-> {new_profile.emotion_baseline.model_dump()}"
            )

        if old_profile.important_people != new_profile.important_people:
            old_people = [p.model_dump() for p in old_profile.important_people]
            new_people = [p.model_dump() for p in new_profile.important_people]
            changes.append(f"important_people: {old_people} -> {new_people}")

        if old_profile.recurring_topics != new_profile.recurring_topics:
            changes.append(
                f"recurring_topics: {old_profile.recurring_topics} -> {new_profile.recurring_topics}"
            )

        if old_profile.preferred_response_style != new_profile.preferred_response_style:
            changes.append(
                f"preferred_response_style: {old_profile.preferred_response_style!r} "
                f"-> {new_profile.preferred_response_style!r}"
            )

        if changes:
            logger.info(
                f"用户 {user_id} 画像更新 — 变更项:\n  " + "\n  ".join(changes)
            )
        else:
            logger.debug(f"用户 {user_id} 画像更新但无实际变更")
