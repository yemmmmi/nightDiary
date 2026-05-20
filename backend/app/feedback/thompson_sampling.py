"""
Thompson Sampling 模块 — 基于 Beta 分布的多臂老虎机算法

为每个用户的每种回应风格维护 Beta(alpha, beta) 分布参数。
通过采样选择最优风格，通过反馈更新分布参数，实现探索与利用的平衡。

风格类型：
- empathetic（共情型）
- practical（务实型）
- philosophical（哲思型）
- humorous（幽默型）
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models.style_preference import StylePreference

logger = logging.getLogger(__name__)

# 可用的回应风格
STYLES = ["empathetic", "practical", "philosophical", "humorous"]

# 默认风格（参数无法加载时的降级选择）
DEFAULT_STYLE = "empathetic"


class ThompsonSampling:
    """
    基于 Beta 分布的 Thompson Sampling 策略选择器。

    为每个用户的每种回应风格维护 Beta(alpha, beta) 参数：
    - alpha: 正向反馈累计次数 + 1（先验）
    - beta: 负向反馈累计次数 + 1（先验）
    - 新用户初始 alpha=1, beta=1（均匀先验）

    采样时从每种风格的 Beta 分布中抽样，选择采样值最高的风格。
    """

    STYLES = STYLES
    DEFAULT_STYLE = DEFAULT_STYLE

    def __init__(self, db: Session):
        """
        初始化 Thompson Sampling 实例。

        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db

    def sample_style(self, user_id: int) -> str:
        """
        从每种风格的 Beta 分布中采样，选择采样值最高的风格。

        对于新用户（无历史记录），会先初始化所有风格的参数为 alpha=1, beta=1。
        如果参数无法加载（数据库异常），返回默认风格（共情型）。

        Args:
            user_id: 用户 ID

        Returns:
            选中的风格名称（empathetic/practical/philosophical/humorous）
        """
        try:
            preferences = self._get_or_create_preferences(user_id)

            # 从每种风格的 Beta 分布中采样
            samples = {}
            for pref in preferences:
                sample_value = np.random.beta(pref.alpha, pref.beta)
                samples[pref.style] = sample_value

            # 选择采样值最高的风格
            selected_style = max(samples, key=samples.get)
            logger.debug(
                f"Thompson Sampling for user {user_id}: "
                f"samples={samples}, selected={selected_style}"
            )
            return selected_style

        except Exception as e:
            logger.warning(
                f"Thompson Sampling 参数加载失败 (user_id={user_id}): {e}. "
                f"使用默认偏好: {self.DEFAULT_STYLE}"
            )
            return self.DEFAULT_STYLE

    def update_reward(self, user_id: int, style: str, is_positive: bool) -> None:
        """
        根据反馈信号更新 Beta 分布参数。

        正向反馈：alpha + 1
        负向反馈：beta + 1

        Args:
            user_id: 用户 ID
            style: 被评价的风格名称
            is_positive: True 为正向反馈，False 为负向反馈
        """
        try:
            preference = (
                self.db.query(StylePreference)
                .filter(
                    StylePreference.user_id == user_id,
                    StylePreference.style == style,
                )
                .first()
            )

            if preference is None:
                # 如果该风格记录不存在，先初始化所有风格
                self._get_or_create_preferences(user_id)
                preference = (
                    self.db.query(StylePreference)
                    .filter(
                        StylePreference.user_id == user_id,
                        StylePreference.style == style,
                    )
                    .first()
                )

            if preference is None:
                logger.error(
                    f"无法找到或创建 StylePreference: "
                    f"user_id={user_id}, style={style}"
                )
                return

            if is_positive:
                preference.alpha += 1
            else:
                preference.beta += 1

            preference.updated_at = datetime.utcnow()
            self.db.commit()

            logger.debug(
                f"Updated reward for user {user_id}, style={style}, "
                f"positive={is_positive}: alpha={preference.alpha}, beta={preference.beta}"
            )

        except Exception as e:
            logger.error(
                f"Thompson Sampling 参数更新失败 "
                f"(user_id={user_id}, style={style}): {e}"
            )
            self.db.rollback()

    def get_style_params(self, user_id: int) -> dict:
        """
        获取用户所有风格的 Beta 分布参数。

        Args:
            user_id: 用户 ID

        Returns:
            字典，key 为风格名称，value 为 {"alpha": float, "beta": float}
        """
        try:
            preferences = self._get_or_create_preferences(user_id)
            return {
                pref.style: {"alpha": pref.alpha, "beta": pref.beta}
                for pref in preferences
            }
        except Exception as e:
            logger.warning(
                f"获取风格参数失败 (user_id={user_id}): {e}. 返回默认参数"
            )
            return {style: {"alpha": 1.0, "beta": 1.0} for style in self.STYLES}

    def _get_or_create_preferences(self, user_id: int) -> list:
        """
        获取用户的风格偏好记录，如果不存在则初始化。

        新用户所有风格初始 alpha=1, beta=1（均匀先验）。

        Args:
            user_id: 用户 ID

        Returns:
            StylePreference 对象列表
        """
        preferences = (
            self.db.query(StylePreference)
            .filter(StylePreference.user_id == user_id)
            .all()
        )

        existing_styles = {pref.style for pref in preferences}
        missing_styles = set(self.STYLES) - existing_styles

        if missing_styles:
            for style in missing_styles:
                new_pref = StylePreference(
                    user_id=user_id,
                    style=style,
                    alpha=1.0,
                    beta=1.0,
                    updated_at=datetime.utcnow(),
                )
                self.db.add(new_pref)
            self.db.commit()

            # 重新查询以获取完整列表
            preferences = (
                self.db.query(StylePreference)
                .filter(StylePreference.user_id == user_id)
                .all()
            )

        return preferences
