"""
AI 分析服务模块
使用 LangChain + ChatOpenAI 调用 LLM，对用户日记进行积极向上的评价分析
支持 LM Studio 本地模型（OpenAI 兼容接口）
"""

import logging
import os
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.models.diary import DiaryEntry

# 日志记录器
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 预设 Prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """
    你是用户的朋友，你话不多但关心着他。你的任务是阅读用户的日记，
    结合他们最近一周的记录，给出真诚友善的评价。
    评价应该：
        1. 回应用户今天的记录
        2. 如果有历史目标，分析完成情况并给予反馈
        3. 语气温和友善，话语简洁
        5. 使用中文回复
"""

USER_PROMPT_TEMPLATE = """【今天的日记】
{current_content}

【最近一周的日记记录】
{history}

【历史目标完成情况分析】
{goal_analysis}

请根据以上内容，给出你的评价和鼓励："""

# LLM 不可用时的降级文本
FALLBACK_FEEDBACK = "感谢你今天的记录！坚持写日记是一件很棒的事，每一天的记录都是珍贵的回忆。继续加油，期待明天的故事！"


# ──────────────────────────────────────────────
# 自定义异常
# ──────────────────────────────────────────────

class AIServiceUnavailableError(Exception):
    """LLM 服务不可用时抛出此异常"""
    pass


# ──────────────────────────────────────────────
# AIService 主类
# ──────────────────────────────────────────────

class AIService:
    """
    AI 分析服务，封装 LangChain LLM 调用逻辑。
    通过环境变量读取配置，支持 LM Studio 本地模型（OpenAI 兼容接口）。
    """

    def __init__(self) -> None:
        # 从环境变量读取配置
        self._provider: str = os.getenv("LLM_PROVIDER", "openai")
        self._api_key: str = os.getenv("LLM_API_KEY", "lm-studio")
        self._model: str = os.getenv("LLM_MODEL", "qwen/qwen3.5-9b")
        self._base_url: Optional[str] = os.getenv(
            "LLM_BASE_URL", "http://localhost:1234/v1"
        )

        # 构建 LangChain chain（懒初始化，首次调用时才真正连接）
        self._chain = self._build_chain()

    def _build_llm(self) -> ChatOpenAI:
        """
        根据配置构建 ChatOpenAI 实例。
        LM Studio 使用 OpenAI 兼容接口，只需设置 base_url 即可。
        """
        kwargs: dict = {
            "api_key": self._api_key,
            "model": self._model,
            # "max_tokens": 512,       # 限制输出长度，避免模型过度生成
        }
        # 如果配置了 base_url（LM Studio / DeepSeek 等兼容接口），则传入
        if self._base_url:
            kwargs["base_url"] = self._base_url

        return ChatOpenAI(**kwargs)

    def _build_chain(self):
        """构建 LangChain 处理链：Prompt → LLM → 字符串输出解析器"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT_TEMPLATE),
        ])
        llm = self._build_llm()
        return prompt | llm | StrOutputParser()

    # ──────────────────────────────────────────
    # 上下文构建辅助方法
    # ──────────────────────────────────────────

    def _format_history(self, recent_entries: list[DiaryEntry]) -> str:
        """
        将历史日记列表格式化为可读文本，供 LLM 理解上下文。
        跳过当天（最新）条目，避免重复。
        """
        if not recent_entries:
            return "（暂无历史记录）"

        lines: list[str] = []
        for entry in recent_entries:
            date_str = entry.created_at.strftime("%Y-%m-%d")
            # 截取前 200 字，避免 token 过多
            snippet = entry.content[:200]
            if len(entry.content) > 200:
                snippet += "..."
            lines.append(f"[{date_str}] {snippet}")

        return "\n".join(lines)

    def _extract_goal_analysis(self, recent_entries: list[DiaryEntry]) -> str:
        """
        从历史日记中提取 tomorrow_goal，分析目标完成情况。
        如果某天设置了明日目标，检查后续日记是否提及相关内容。
        """
        goals: list[str] = []
        for entry in recent_entries:
            if entry.tomorrow_goal and entry.tomorrow_goal.strip():
                date_str = entry.created_at.strftime("%Y-%m-%d")
                goals.append(f"[{date_str} 设定的目标] {entry.tomorrow_goal}")

        if not goals:
            return "（历史记录中未设定明日目标）"

        return "\n".join(goals)

    def _build_context(
        self,
        current_entry: DiaryEntry,
        recent_entries: list[DiaryEntry],
    ) -> dict:
        """
        构建传入 LLM 的上下文字典。
        包含当前日记内容、最近7天历史摘要、历史目标分析。
        """
        # 历史条目中排除当前条目（避免重复）
        history_entries = [e for e in recent_entries if e.id != current_entry.id]

        return {
            "current_content": current_entry.content,
            "history": self._format_history(history_entries),
            "goal_analysis": self._extract_goal_analysis(history_entries),
        }

    # ──────────────────────────────────────────
    # 核心分析方法
    # ──────────────────────────────────────────

    def analyze(
        self,
        current_entry: DiaryEntry,
        recent_entries: list[DiaryEntry],
    ) -> str:
        """
        分析当前日记，结合最近7天历史，生成积极向上的 AI 评价。

        :param current_entry: 当前日记条目
        :param recent_entries: 最近7天的日记列表（含当前条目）
        :return: AI 生成的评价文本（150-300字中文）
        :raises AIServiceUnavailableError: 当 LLM 服务完全不可用时（配置缺失等）
        """
        # 检查基本配置是否存在
        if not self._api_key:
            logger.warning("LLM_API_KEY 未配置，AI 服务不可用")
            raise AIServiceUnavailableError("AI 服务未配置，无法提供分析")

        try:
            context = self._build_context(current_entry, recent_entries)
            result: str = self._chain.invoke(context)
            logger.info("AI 分析成功，返回评价文本（%d 字）", len(result))
            return result
        except AIServiceUnavailableError:
            # 重新抛出，不降级
            raise
        except Exception as exc:
            # LLM 调用失败（网络错误、超时、API 错误等），记录日志并返回降级文本
            logger.error("LLM 调用失败，使用降级文本。错误：%s", exc, exc_info=True)
            return FALLBACK_FEEDBACK
