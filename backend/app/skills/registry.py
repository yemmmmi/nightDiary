"""
SkillRegistry - Skill 注册表
============================

管理可插拔 Skill 组件的注册、选择和动态加载。

核心功能：
- register(): 运行时注册新 Skill
- select_skills(): 按 activation_score * priority 贪心选择，受 Token 预算约束
- load_from_config(): 从配置文件动态加载 Skill 模块
"""

import importlib
import logging
from typing import List, Optional

from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 激活概率阈值：低于此值的 Skill 不参与选择
ACTIVATION_THRESHOLD = 0.3


class SkillRegistry:
    """
    Skill 注册表。

    负责管理所有已注册的 Skill，并在分析请求时根据
    激活概率、优先级和 Token 预算进行贪心选择。
    """

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    @property
    def skills(self) -> dict[str, BaseSkill]:
        """返回所有已注册的 Skill（只读视图）。"""
        return dict(self._skills)

    def register(self, skill: BaseSkill) -> None:
        """
        注册一个 Skill 实例。

        支持运行时动态添加，无需重启服务。
        如果同名 Skill 已存在，将被覆盖并记录警告。

        Args:
            skill: BaseSkill 实现实例
        """
        name = skill.metadata.name
        if name in self._skills:
            logger.warning(
                f"Skill '{name}' 已存在，将被覆盖"
            )
        self._skills[name] = skill
        logger.info(
            f"已注册 Skill: {name} "
            f"(category={skill.metadata.category}, "
            f"token_cost={skill.metadata.token_cost_estimate}, "
            f"priority={skill.metadata.priority})"
        )

    def select_skills(
        self,
        intent: str,
        token_budget: int,
        diary_content: str,
    ) -> List[BaseSkill]:
        """
        贪心选择 Skills。

        算法：
        1. 对每个已注册 Skill 调用 should_activate() 获取激活概率
        2. 过滤掉激活概率 < ACTIVATION_THRESHOLD 的 Skill
        3. 按 activation_score * priority 降序排列
        4. 贪心累加：逐个检查 token_cost_estimate，
           如果加入后不超预算则选中，否则跳过
        5. 记录激活/跳过日志

        Args:
            intent: 分类意图
            token_budget: 剩余 Token 预算
            diary_content: 日记内容

        Returns:
            按优先级排序的已选 Skill 列表
        """
        candidates: list[tuple[float, BaseSkill]] = []

        for skill in self._skills.values():
            try:
                activation_score = skill.should_activate(diary_content, intent)
            except Exception as e:
                logger.warning(
                    f"Skill '{skill.metadata.name}' should_activate 异常: {e}"
                )
                continue

            if activation_score < ACTIVATION_THRESHOLD:
                logger.debug(
                    f"Skill '{skill.metadata.name}' 激活概率 {activation_score:.2f} "
                    f"低于阈值 {ACTIVATION_THRESHOLD}，跳过"
                )
                continue

            # 排序分数 = activation_score * priority
            sort_score = activation_score * skill.metadata.priority
            candidates.append((sort_score, skill))

        # 按 sort_score 降序排列
        candidates.sort(key=lambda x: x[0], reverse=True)

        selected: List[BaseSkill] = []
        remaining_budget = token_budget
        total_token_cost = 0

        for sort_score, skill in candidates:
            cost = skill.metadata.token_cost_estimate
            if cost <= remaining_budget:
                selected.append(skill)
                remaining_budget -= cost
                total_token_cost += cost
                logger.info(
                    f"激活 Skill '{skill.metadata.name}' "
                    f"(score={sort_score:.3f}, "
                    f"token_cost={cost}, "
                    f"remaining_budget={remaining_budget})"
                )
            else:
                logger.info(
                    f"跳过 Skill '{skill.metadata.name}' "
                    f"(score={sort_score:.3f}, "
                    f"token_cost={cost}, "
                    f"超出剩余预算 {remaining_budget})"
                )

        logger.info(
            f"Skill 选择完成: 激活 {len(selected)}/{len(self._skills)} 个, "
            f"总 Token 消耗预估: {total_token_cost}/{token_budget}"
        )

        return selected

    def load_from_config(self, config_path: str) -> None:
        """
        从配置文件加载 Skill 模块。

        配置文件格式（每行一个 Python 模块路径）：
            app.skills.search_diary_skill.SearchDiarySkill
            app.skills.weather_skill.WeatherSkill

        每个模块路径格式为 "module.path.ClassName"，
        Registry 会导入模块并实例化 Skill 类，然后注册。

        Args:
            config_path: 配置文件路径
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            logger.warning(f"Skill 配置文件不存在: {config_path}")
            return
        except Exception as e:
            logger.error(f"读取 Skill 配置文件失败: {e}")
            return

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                self._load_skill_class(line)
            except Exception as e:
                logger.error(
                    f"加载 Skill '{line}' 失败: {e}"
                )

    def _load_skill_class(self, class_path: str) -> None:
        """
        动态导入并实例化一个 Skill 类。

        Args:
            class_path: 完整类路径，如 "app.skills.weather_skill.WeatherSkill"
        """
        # 分离模块路径和类名
        module_path, class_name = class_path.rsplit(".", 1)

        module = importlib.import_module(module_path)
        skill_class = getattr(module, class_name)

        # 实例化并注册
        skill_instance = skill_class()

        if not isinstance(skill_instance, BaseSkill):
            raise TypeError(
                f"{class_path} 不是 BaseSkill 的子类"
            )

        self.register(skill_instance)
        logger.info(f"从配置动态加载 Skill: {class_path}")

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        按名称获取已注册的 Skill。

        Args:
            name: Skill 名称

        Returns:
            BaseSkill 实例，未找到时返回 None
        """
        return self._skills.get(name)

    def unregister(self, name: str) -> bool:
        """
        注销一个已注册的 Skill。

        Args:
            name: Skill 名称

        Returns:
            是否成功注销
        """
        if name in self._skills:
            del self._skills[name]
            logger.info(f"已注销 Skill: {name}")
            return True
        return False
