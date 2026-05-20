"""
BaseSkill 抽象基类
=================

定义所有 Skill 必须实现的接口：
- execute(): 执行 Skill 逻辑，返回结果文本
- should_activate(): 根据日记内容和意图返回激活概率 (0.0-1.0)
"""

from abc import ABC, abstractmethod

from app.schemas.skill import SkillMetadata


class BaseSkill(ABC):
    """
    Skill 抽象基类。

    所有 Skill 实现必须：
    1. 设置 metadata 属性（SkillMetadata 实例）
    2. 实现 execute() 方法
    3. 实现 should_activate() 方法
    """

    metadata: SkillMetadata

    @abstractmethod
    def execute(self, context: dict, **kwargs) -> str:
        """
        执行 Skill 逻辑。

        Args:
            context: 包含 diary_content, user_id, intent 等上下文信息的字典
            **kwargs: 额外参数

        Returns:
            Skill 执行结果的文本描述
        """
        ...

    @abstractmethod
    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        判断当前 Skill 是否应被激活。

        Args:
            diary_content: 日记内容
            intent: 分类意图 (pure_record/emotional_support/retrospective_review/habit_tracking)

        Returns:
            激活概率，范围 0.0-1.0
        """
        ...
