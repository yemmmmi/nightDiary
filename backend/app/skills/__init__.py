"""
可插拔 Skill 架构
================

提供 BaseSkill 抽象基类和 SkillRegistry 注册表，
支持动态加载、Token 预算贪心选择和运行时注册。
"""

from app.skills.base import BaseSkill
from app.skills.registry import SkillRegistry

__all__ = ["BaseSkill", "SkillRegistry"]
