"""
LongTermMemory 单元测试
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.memory.long_term import LongTermMemory
from app.models.user import User
from app.schemas.memory import EpisodicEntry, UserProfile, EmotionBaseline


@pytest.fixture
def memory():
    return LongTermMemory()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.UID = 1
    user.long_term_profile = None
    return user


class TestGetProfile:
    def test_returns_default_when_user_not_found(self, memory, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        profile = memory.get_profile(mock_db, user_id=999)
        assert profile == UserProfile()

    def test_returns_default_when_profile_is_none(self, memory, mock_db, mock_user):
        mock_user.long_term_profile = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        profile = memory.get_profile(mock_db, user_id=1)
        assert profile == UserProfile()

    def test_returns_default_when_profile_is_invalid_json(self, memory, mock_db, mock_user):
        mock_user.long_term_profile = "not valid json"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        profile = memory.get_profile(mock_db, user_id=1)
        assert profile == UserProfile()

    def test_parses_valid_profile(self, memory, mock_db, mock_user):
        expected = UserProfile(
            personality_tags=["内向", "敏感"],
            recurring_topics=["工作压力"],
            preferred_response_style="philosophical",
        )
        mock_user.long_term_profile = expected.model_dump_json()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        profile = memory.get_profile(mock_db, user_id=1)
        assert profile.personality_tags == ["内向", "敏感"]
        assert profile.recurring_topics == ["工作压力"]
        assert profile.preferred_response_style == "philosophical"


class TestUpdateProfile:
    def test_does_nothing_when_user_not_found(self, memory, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        profile = UserProfile(personality_tags=["test"])
        memory.update_profile(mock_db, user_id=999, profile=profile)
        mock_db.commit.assert_not_called()

    def test_saves_profile_and_commits(self, memory, mock_db, mock_user):
        mock_user.long_term_profile = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        new_profile = UserProfile(personality_tags=["乐观"])
        memory.update_profile(mock_db, user_id=1, profile=new_profile)

        assert mock_user.long_term_profile == new_profile.model_dump_json()
        mock_db.commit.assert_called_once()

    def test_logs_changes_between_old_and_new(self, memory, mock_db, mock_user):
        old_profile = UserProfile(personality_tags=["内向"])
        mock_user.long_term_profile = old_profile.model_dump_json()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        new_profile = UserProfile(personality_tags=["内向", "乐观"])
        with patch.object(memory, "_log_profile_changes") as mock_log:
            memory.update_profile(mock_db, user_id=1, profile=new_profile)
            mock_log.assert_called_once_with(1, old_profile, new_profile)


class TestPromoteFromEpisodic:
    def _make_entries_for_days(self, emotion: str, event: str, days: int, start_ts: float = None):
        """创建连续多天的情景记忆条目"""
        if start_ts is None:
            start_ts = time.time() - days * 86400
        entries = []
        for i in range(days):
            entries.append(
                EpisodicEntry(
                    event=event,
                    emotion=emotion,
                    ai_suggestion="建议",
                    timestamp=start_ts + i * 86400,
                    diary_nids=[i + 1],
                    importance=0.7,
                )
            )
        return entries

    def test_no_entries_does_nothing(self, memory, mock_db, mock_user):
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        memory.promote_from_episodic(mock_db, user_id=1, episodic_entries=[])
        mock_db.commit.assert_not_called()

    def test_promotes_topic_after_3_consecutive_days(self, memory, mock_db, mock_user):
        mock_user.long_term_profile = UserProfile().model_dump_json()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        entries = self._make_entries_for_days("焦虑", "工作压力大", days=3)
        memory.promote_from_episodic(mock_db, user_id=1, episodic_entries=entries)

        # Should have committed (update_profile calls commit)
        mock_db.commit.assert_called()
        # Verify profile was updated
        saved_json = mock_user.long_term_profile
        saved_profile = UserProfile.model_validate_json(saved_json)
        assert "工作压力大" in saved_profile.recurring_topics

    def test_does_not_promote_with_only_2_days(self, memory, mock_db, mock_user):
        mock_user.long_term_profile = UserProfile().model_dump_json()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        entries = self._make_entries_for_days("焦虑", "短期事件", days=2)
        memory.promote_from_episodic(mock_db, user_id=1, episodic_entries=entries)

        # No commit means no update
        mock_db.commit.assert_not_called()

    def test_promotes_emotion_to_dominant(self, memory, mock_db, mock_user):
        mock_user.long_term_profile = UserProfile().model_dump_json()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        entries = self._make_entries_for_days("焦虑", "不同事件1", days=3)
        memory.promote_from_episodic(mock_db, user_id=1, episodic_entries=entries)

        saved_json = mock_user.long_term_profile
        saved_profile = UserProfile.model_validate_json(saved_json)
        assert saved_profile.emotion_baseline.dominant_emotion == "焦虑"

    def test_does_not_duplicate_existing_topics(self, memory, mock_db, mock_user):
        existing_profile = UserProfile(recurring_topics=["工作压力大"])
        mock_user.long_term_profile = existing_profile.model_dump_json()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        entries = self._make_entries_for_days("焦虑", "工作压力大", days=3)
        memory.promote_from_episodic(mock_db, user_id=1, episodic_entries=entries)

        saved_json = mock_user.long_term_profile
        saved_profile = UserProfile.model_validate_json(saved_json)
        # Should only appear once
        assert saved_profile.recurring_topics.count("工作压力大") == 1


class TestFindConsecutiveItems:
    def test_empty_input(self, memory):
        result = memory._find_consecutive_items({}, threshold=3)
        assert result == set()

    def test_finds_consecutive_items(self, memory):
        daily_items = {
            "2024-01-01": {"work", "sleep"},
            "2024-01-02": {"work", "exercise"},
            "2024-01-03": {"work", "reading"},
        }
        result = memory._find_consecutive_items(daily_items, threshold=3)
        assert "work" in result
        assert "sleep" not in result

    def test_non_consecutive_days_dont_count(self, memory):
        daily_items = {
            "2024-01-01": {"topic"},
            "2024-01-02": {"topic"},
            "2024-01-04": {"topic"},  # gap on 01-03
        }
        result = memory._find_consecutive_items(daily_items, threshold=3)
        assert "topic" not in result
