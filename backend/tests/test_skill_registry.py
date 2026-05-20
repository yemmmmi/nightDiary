"""
Skill Registry 单元测试
"""

import os
import tempfile

import pytest

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill
from app.skills.registry import SkillRegistry, ACTIVATION_THRESHOLD


# ===== 测试用 Skill 实现 =====


class MockHighPrioritySkill(BaseSkill):
    """高优先级 Skill，总是激活。"""

    metadata = SkillMetadata(
        name="high_priority",
        description="高优先级测试 Skill",
        category="analysis",
        token_cost_estimate=200,
        priority=2.0,
    )

    def execute(self, context: dict, **kwargs) -> str:
        return "high_priority result"

    def should_activate(self, diary_content: str, intent: str) -> float:
        return 0.9


class MockLowPrioritySkill(BaseSkill):
    """低优先级 Skill，总是激活。"""

    metadata = SkillMetadata(
        name="low_priority",
        description="低优先级测试 Skill",
        category="retrieval",
        token_cost_estimate=100,
        priority=0.5,
    )

    def execute(self, context: dict, **kwargs) -> str:
        return "low_priority result"

    def should_activate(self, diary_content: str, intent: str) -> float:
        return 0.8


class MockExpensiveSkill(BaseSkill):
    """高 Token 消耗 Skill。"""

    metadata = SkillMetadata(
        name="expensive",
        description="高消耗测试 Skill",
        category="generation",
        token_cost_estimate=500,
        priority=1.5,
    )

    def execute(self, context: dict, **kwargs) -> str:
        return "expensive result"

    def should_activate(self, diary_content: str, intent: str) -> float:
        return 0.7


class MockInactiveSkill(BaseSkill):
    """不激活的 Skill（概率低于阈值）。"""

    metadata = SkillMetadata(
        name="inactive",
        description="不激活的测试 Skill",
        category="external",
        token_cost_estimate=50,
        priority=1.0,
    )

    def execute(self, context: dict, **kwargs) -> str:
        return "inactive result"

    def should_activate(self, diary_content: str, intent: str) -> float:
        return 0.1  # 低于 ACTIVATION_THRESHOLD


class MockErrorSkill(BaseSkill):
    """should_activate 会抛异常的 Skill。"""

    metadata = SkillMetadata(
        name="error_skill",
        description="异常测试 Skill",
        category="memory",
        token_cost_estimate=100,
        priority=1.0,
    )

    def execute(self, context: dict, **kwargs) -> str:
        return "error result"

    def should_activate(self, diary_content: str, intent: str) -> float:
        raise RuntimeError("模拟异常")


# ===== 测试 =====


class TestSkillRegistryRegister:
    def test_register_skill(self):
        registry = SkillRegistry()
        skill = MockHighPrioritySkill()
        registry.register(skill)

        assert "high_priority" in registry.skills
        assert registry.get_skill("high_priority") is skill

    def test_register_overwrites_existing(self):
        registry = SkillRegistry()
        skill1 = MockHighPrioritySkill()
        skill2 = MockHighPrioritySkill()
        registry.register(skill1)
        registry.register(skill2)

        assert registry.get_skill("high_priority") is skill2

    def test_unregister(self):
        registry = SkillRegistry()
        registry.register(MockHighPrioritySkill())
        assert registry.unregister("high_priority") is True
        assert registry.get_skill("high_priority") is None
        assert registry.unregister("nonexistent") is False


class TestSkillRegistrySelectSkills:
    def setup_method(self):
        self.registry = SkillRegistry()
        self.registry.register(MockHighPrioritySkill())
        self.registry.register(MockLowPrioritySkill())
        self.registry.register(MockExpensiveSkill())
        self.registry.register(MockInactiveSkill())

    def test_selects_by_score_priority(self):
        """按 activation_score * priority 排序选择。"""
        selected = self.registry.select_skills(
            intent="emotional_support",
            token_budget=1000,
            diary_content="今天心情不好",
        )

        names = [s.metadata.name for s in selected]
        # high_priority: 0.9 * 2.0 = 1.8
        # expensive: 0.7 * 1.5 = 1.05
        # low_priority: 0.8 * 0.5 = 0.4
        # inactive: 被过滤掉
        assert names[0] == "high_priority"
        assert "inactive" not in names

    def test_token_budget_constraint(self):
        """Token 预算约束：不超过预算。"""
        selected = self.registry.select_skills(
            intent="pure_record",
            token_budget=300,
            diary_content="简单记录",
        )

        total_cost = sum(s.metadata.token_cost_estimate for s in selected)
        assert total_cost <= 300

    def test_token_budget_skips_expensive(self):
        """预算不足时跳过高消耗 Skill。"""
        selected = self.registry.select_skills(
            intent="pure_record",
            token_budget=250,
            diary_content="简单记录",
        )

        names = [s.metadata.name for s in selected]
        # high_priority (200) fits, expensive (500) doesn't, low_priority (100) doesn't after high
        assert "expensive" not in names

    def test_inactive_skill_filtered(self):
        """激活概率低于阈值的 Skill 被过滤。"""
        selected = self.registry.select_skills(
            intent="emotional_support",
            token_budget=10000,
            diary_content="测试",
        )

        names = [s.metadata.name for s in selected]
        assert "inactive" not in names

    def test_error_in_should_activate_handled(self):
        """should_activate 异常不影响其他 Skill 选择。"""
        self.registry.register(MockErrorSkill())

        selected = self.registry.select_skills(
            intent="emotional_support",
            token_budget=1000,
            diary_content="测试",
        )

        names = [s.metadata.name for s in selected]
        assert "error_skill" not in names
        assert len(selected) > 0

    def test_empty_registry_returns_empty(self):
        """空注册表返回空列表。"""
        empty_registry = SkillRegistry()
        selected = empty_registry.select_skills(
            intent="pure_record",
            token_budget=1000,
            diary_content="测试",
        )
        assert selected == []

    def test_zero_budget_returns_empty(self):
        """预算为 0 时返回空列表。"""
        selected = self.registry.select_skills(
            intent="pure_record",
            token_budget=0,
            diary_content="测试",
        )
        assert selected == []


class TestSkillRegistryLoadFromConfig:
    def test_load_from_nonexistent_config(self):
        """不存在的配置文件不报错。"""
        registry = SkillRegistry()
        registry.load_from_config("/nonexistent/path.txt")
        assert len(registry.skills) == 0

    def test_load_from_config_with_comments(self):
        """配置文件中的注释和空行被忽略。"""
        config_content = "# This is a comment\n\n# Another comment\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(config_content)
            config_path = f.name

        try:
            registry = SkillRegistry()
            registry.load_from_config(config_path)
            assert len(registry.skills) == 0
        finally:
            os.unlink(config_path)

    def test_load_from_config_invalid_module(self):
        """无效模块路径不影响 registry 正常工作。"""
        config_content = "nonexistent.module.FakeSkill\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(config_content)
            config_path = f.name

        try:
            registry = SkillRegistry()
            registry.load_from_config(config_path)
            assert len(registry.skills) == 0
        finally:
            os.unlink(config_path)
