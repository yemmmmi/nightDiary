"""
Thompson Sampling 模块单元测试
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from app.feedback.thompson_sampling import ThompsonSampling, STYLES, DEFAULT_STYLE
from app.models.style_preference import StylePreference


class TestThompsonSampling:
    """Thompson Sampling 核心逻辑测试"""

    def _make_preference(self, user_id: int, style: str, alpha: float = 1.0, beta: float = 1.0):
        """创建模拟的 StylePreference 对象"""
        pref = MagicMock(spec=StylePreference)
        pref.user_id = user_id
        pref.style = style
        pref.alpha = alpha
        pref.beta = beta
        pref.updated_at = datetime.utcnow()
        return pref

    def _make_db_with_preferences(self, preferences):
        """创建带有预设查询结果的模拟 db session"""
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()

        db.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        filter_mock.all.return_value = preferences
        filter_mock.first.return_value = preferences[0] if preferences else None

        return db

    def test_sample_style_returns_valid_style(self):
        """sample_style 应返回有效的风格名称"""
        preferences = [
            self._make_preference(1, style) for style in STYLES
        ]
        db = self._make_db_with_preferences(preferences)
        ts = ThompsonSampling(db)

        result = ts.sample_style(user_id=1)
        assert result in STYLES

    def test_sample_style_favors_high_alpha(self):
        """高 alpha 值的风格应更频繁被选中"""
        # 给 empathetic 一个非常高的 alpha，使其几乎必然被选中
        preferences = [
            self._make_preference(1, "empathetic", alpha=100.0, beta=1.0),
            self._make_preference(1, "practical", alpha=1.0, beta=100.0),
            self._make_preference(1, "philosophical", alpha=1.0, beta=100.0),
            self._make_preference(1, "humorous", alpha=1.0, beta=100.0),
        ]
        db = self._make_db_with_preferences(preferences)
        ts = ThompsonSampling(db)

        # 多次采样，高 alpha 的风格应占绝大多数
        results = [ts.sample_style(user_id=1) for _ in range(50)]
        empathetic_count = results.count("empathetic")
        assert empathetic_count >= 45, f"Expected empathetic to dominate, got {empathetic_count}/50"

    def test_sample_style_default_on_exception(self):
        """数据库异常时应返回默认风格（共情型）"""
        db = MagicMock()
        db.query.side_effect = Exception("DB connection failed")
        ts = ThompsonSampling(db)

        result = ts.sample_style(user_id=1)
        assert result == DEFAULT_STYLE

    def test_sample_style_creates_preferences_for_new_user(self):
        """新用户应自动初始化所有风格的参数"""
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()

        db.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock

        # 第一次查询返回空（新用户），第二次返回初始化后的结果
        new_prefs = [self._make_preference(1, style) for style in STYLES]
        filter_mock.all.side_effect = [[], new_prefs]

        ts = ThompsonSampling(db)
        result = ts.sample_style(user_id=1)

        # 应该调用了 db.add 来创建新记录
        assert db.add.call_count == len(STYLES)
        assert db.commit.called
        assert result in STYLES

    def test_update_reward_positive(self):
        """正向反馈应使 alpha + 1"""
        pref = self._make_preference(1, "empathetic", alpha=3.0, beta=2.0)
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()

        db.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = pref

        ts = ThompsonSampling(db)
        ts.update_reward(user_id=1, style="empathetic", is_positive=True)

        assert pref.alpha == 4.0
        assert pref.beta == 2.0
        assert db.commit.called

    def test_update_reward_negative(self):
        """负向反馈应使 beta + 1"""
        pref = self._make_preference(1, "practical", alpha=2.0, beta=3.0)
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()

        db.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = pref

        ts = ThompsonSampling(db)
        ts.update_reward(user_id=1, style="practical", is_positive=False)

        assert pref.alpha == 2.0
        assert pref.beta == 4.0
        assert db.commit.called

    def test_update_reward_rollback_on_exception(self):
        """更新失败时应回滚事务"""
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()

        db.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = None

        # 模拟 _get_or_create_preferences 也失败
        filter_mock.all.side_effect = Exception("DB error")

        ts = ThompsonSampling(db)
        ts.update_reward(user_id=1, style="empathetic", is_positive=True)

        # 应该调用了 rollback
        assert db.rollback.called

    def test_get_style_params_returns_all_styles(self):
        """get_style_params 应返回所有风格的参数"""
        preferences = [
            self._make_preference(1, "empathetic", alpha=5.0, beta=2.0),
            self._make_preference(1, "practical", alpha=3.0, beta=4.0),
            self._make_preference(1, "philosophical", alpha=2.0, beta=1.0),
            self._make_preference(1, "humorous", alpha=1.0, beta=6.0),
        ]
        db = self._make_db_with_preferences(preferences)
        ts = ThompsonSampling(db)

        params = ts.get_style_params(user_id=1)

        assert params["empathetic"] == {"alpha": 5.0, "beta": 2.0}
        assert params["practical"] == {"alpha": 3.0, "beta": 4.0}
        assert params["philosophical"] == {"alpha": 2.0, "beta": 1.0}
        assert params["humorous"] == {"alpha": 1.0, "beta": 6.0}

    def test_get_style_params_default_on_exception(self):
        """参数获取失败时应返回默认参数"""
        db = MagicMock()
        db.query.side_effect = Exception("DB error")
        ts = ThompsonSampling(db)

        params = ts.get_style_params(user_id=1)

        for style in STYLES:
            assert params[style] == {"alpha": 1.0, "beta": 1.0}

    def test_uniform_prior_for_new_user(self):
        """新用户所有风格应初始化为 alpha=1, beta=1（均匀先验）"""
        db = MagicMock()
        query_mock = MagicMock()
        filter_mock = MagicMock()

        db.query.return_value = query_mock
        query_mock.filter.return_value = filter_mock
        filter_mock.all.return_value = []

        ts = ThompsonSampling(db)

        # 调用 _get_or_create_preferences 触发初始化
        # 由于 all() 返回空列表，会创建新记录
        # 检查 db.add 被调用时传入的参数
        try:
            ts._get_or_create_preferences(user_id=99)
        except Exception:
            pass  # commit 后的重新查询可能失败，但我们只关心 add 调用

        # 验证每个 add 调用的参数
        for call in db.add.call_args_list:
            pref = call[0][0]
            assert pref.alpha == 1.0
            assert pref.beta == 1.0
            assert pref.style in STYLES
            assert pref.user_id == 99

    def test_styles_constant(self):
        """STYLES 常量应包含四种风格"""
        assert set(STYLES) == {"empathetic", "practical", "philosophical", "humorous"}

    def test_default_style_is_empathetic(self):
        """默认风格应为共情型"""
        assert DEFAULT_STYLE == "empathetic"
