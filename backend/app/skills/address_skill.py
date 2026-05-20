"""
AddressSkill - 用户地址获取 Skill
==================================

将 ai_service.py 中的 get_user_address 工具封装为 BaseSkill 实现。
查询用户地址信息，为天气查询等场景提供地理上下文。
"""

import logging

from app.schemas.skill import SkillMetadata
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 地理/位置相关关键词
_LOCATION_KEYWORDS = (
    "天气", "出门", "回家", "上班", "通勤", "路上", "公司", "学校",
    "地铁", "公交", "打车", "外面", "户外", "散步", "跑步",
    "搬家", "旅行", "出差", "回老家",
)


class AddressSkill(BaseSkill):
    """
    用户地址获取 Skill。

    封装用户地址查询逻辑，为天气查询等提供地理上下文。
    通常作为其他 Skill（如 WeatherSkill）的辅助信息来源。
    """

    metadata = SkillMetadata(
        name="get_user_address",
        description="获取用户地址信息，为天气查询等提供地理上下文",
        category="retrieval",
        token_cost_estimate=30,
        requires_db=True,
        requires_network=False,
        priority=0.6,
    )

    def execute(self, context: dict, **kwargs) -> str:
        """
        执行地址查询。

        context 需包含:
            - user_id: int
            - db: SQLAlchemy Session
        """
        user_id = context.get("user_id")
        db = context.get("db")

        if not user_id or not db:
            return "获取地址信息失败：缺少必要上下文"

        try:
            from app.models.user import User

            user = db.query(User).filter(User.UID == user_id).first()
            if user is None or not user.address:
                return "用户未设置地址信息"
            return user.address
        except Exception as exc:
            logger.error("AddressSkill 执行失败: %s", exc)
            return "获取地址信息失败"

    def should_activate(self, diary_content: str, intent: str) -> float:
        """
        激活判断逻辑：
        - 包含地理/位置关键词: 0.7
        - emotional_support 意图 (地理上下文辅助共情): 0.35
        - 其他: 0.1 (较少独立需要地址)

        注意：AddressSkill 通常由 WeatherSkill 间接触发，
        独立激活的场景较少，因此整体概率偏低。
        """
        if any(kw in diary_content for kw in _LOCATION_KEYWORDS):
            return 0.7

        if intent == "emotional_support":
            return 0.35

        return 0.1
