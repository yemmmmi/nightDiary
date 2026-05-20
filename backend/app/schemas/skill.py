"""
Skill 架构相关 Pydantic Schema
============================

数据结构：
- SkillMetadata: Skill 元数据描述，用于注册表管理和 Token 预算选择
"""

from typing import Literal
from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """
    Skill 元数据。
    描述 Skill 的基本信息、分类、Token 消耗预估和资源需求。
    用于 SkillRegistry 的注册、过滤和贪心选择。
    """
    name: str  # Skill 唯一标识名
    description: str  # Skill 功能描述
    category: Literal[
        "retrieval", "analysis", "generation", "external", "memory"
    ]  # Skill 分类
    token_cost_estimate: int = Field(default=100, ge=0)  # 预估 Token 消耗
    requires_db: bool = False  # 是否需要数据库访问
    requires_network: bool = False  # 是否需要网络访问
    priority: float = Field(default=1.0, ge=0.0)  # 优先级权重，用于贪心选择排序
