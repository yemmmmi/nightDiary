"""
AI 分析服务模块 — ReAct Agent 架构
====================================

核心设计思路：
1. 每个用户可以配置自己的 LLM 模型(ModelProvider),AI 服务优先使用用户配置的模型
2. 如果用户没有配置模型，则回退到系统默认的环境变量配置(DeepSeek / OpenAI 等）
3. 使用 LangChain 的 ReAct Agent 模式，支持工具调用（天气查询、历史日记检索）
4. 标签作为 Few-shot 上下文注入 Prompt, 帮助 AI 更好地理解日记内容
5. LLM 不可用时抛出 AIServiceUnavailableError, 由路由层返回 503

模块结构：
- AIServiceUnavailableError: 自定义异常, LLM 不可用时抛出
- DiarySearchTool: LangChain Tool, 用于检索用户历史日记(RAG)
- WeatherTool: LangChain Tool, 用于查询天气信息(MCP 概念的简化实现）
- AIService: 主服务类，封装 ReAct Agent 的构建和调用逻辑
"""

import logging
import os
from datetime import datetime
from typing import Optional, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.models.diary import DiaryEntry
from app.models.tag import Tag

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  自定义异常                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

class AIServiceUnavailableError(Exception):
    """
    LLM 服务不可用时抛出此异常。
    路由层捕获后返回 HTTP 503 Service Unavailable。
    触发场景：
    - 用户未配置模型且系统默认配置也缺失
    - LLM API 连接失败、超时
    - API Key 无效
    """
    pass


# ╔══════════════════════════════════════════════════════════════╗
# ║  Prompt 模板                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

# System Prompt — 精简版，减少输入 token
SYSTEM_PROMPT = """你是"夜记助手"，用户的朋友。阅读日记后给出简短的回应。
回应要求：回应核心情感,语气正常少人机味,中文,50-150字。"""

# Agent 模式专用 System Prompt（多了工具说明）
AGENT_SYSTEM_PROMPT = SYSTEM_PROMPT + """
可用工具:search_diary(搜索历史日记)、get_weather_info(查天气)。不需要就直接回应。"""

# 用户消息模板 — 精简，去掉空区块
USER_PROMPT_TEMPLATE = """日记：{current_content}
标签：{tags_context}
历史：{history_summary}
天气：{weather_info}
请回应："""

# LLM 不可用时的降级文本
FALLBACK_FEEDBACK = (
    "感谢你今天的记录！坚持写日记是一件很棒的事，"
    "每一天的记录都是珍贵的回忆。继续加油，期待明天的故事！"
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  LangChain Tools（ReAct Agent 的工具集）                       ║
# ╚══════════════════════════════════════════════════════════════╝

def create_diary_search_tool(db: Session, user_id: int):
    """
    工厂函数：创建日记语义搜索工具（基于 Chroma 向量检索）。

    为什么用工厂函数？
    - LangChain 的 @tool 装饰器创建的是全局工具
    - 但我们需要每次调用时绑定不同的 user_id
    - 工厂函数通过闭包捕获上下文，实现用户数据隔离

    RAG 实现说明：
    - 使用 Chroma 向量数据库 + text2vec-base-chinese Embedding 模型
    - 查询时将关键词转为向量，在用户的 Collection 中做余弦相似度检索
    - 相比 SQL LIKE, 语义检索能理解"意思"而非仅匹配"字面"
    - 例如搜索"开心"能匹配到"今天心情很好"、"感到快乐"等语义相近的日记
    """
    @tool
    def search_diary(query: str) -> str:
        """搜索用户的历史日记。输入关键词或描述，返回语义最相关的历史日记摘要。
        用于了解用户过去提到的事件、目标、情绪等上下文信息。"""
        try:
            from app.services.vector_service import search_similar_diaries

            results = search_similar_diaries(
                user_id=user_id,
                query=query,
                top_k=5,
            )

            if not results:
                return f"未找到与「{query}」相关的历史日记。"

            lines = []
            for item in results:
                date_str = item.get("date", "未知日期")
                content = item.get("content", "")
                tags = item.get("tags", "")
                snippet = content[:150] + "..." if len(content) > 150 else content

                tag_part = f" {tags}" if tags else ""
                lines.append(f"[{date_str}]{tag_part} {snippet}")

            return "\n".join(lines)
        except Exception as exc:
            logger.error("日记语义搜索工具执行失败: %s", exc)
            return "搜索历史日记时出现错误。"

    return search_diary


def create_weather_tool():
    """
    工厂函数：创建天气查询工具。

    MCP(Model Context Protocol)概念说明:
    - MCP 是一种让 AI Agent 调用外部服务的协议
    - 这里的天气工具是 MCP 概念的简化实现
    - Agent 可以在分析日记时主动查询天气，丰富回应内容
    """
    @tool
    def get_weather_info(city: str) -> str:
        """查询指定城市的天气信息。输入城市名称，返回当前天气描述。
        可以在回应中提及天气，让分析更贴近用户的真实生活场景。"""
        try:
            # 同步调用天气服务（Agent 工具需要同步接口）
            # 注意：weather_service.get_weather 是异步的，这里用 httpx 同步版本
            import httpx

            api_key = os.getenv("WEATHER_API_KEY", "")
            if not api_key:
                return "天气服务未配置"

            # 先地理编码
            geo_url = "https://restapi.amap.com/v3/geocode/geo"
            geo_params = {"address": city, "key": api_key, "output": "JSON"}

            with httpx.Client(timeout=5.0) as client:
                geo_resp = client.get(geo_url, params=geo_params)
                geo_data = geo_resp.json()

            if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
                return f"无法识别城市「{city}」"

            adcode = geo_data["geocodes"][0].get("adcode")

            # 再查天气
            weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            weather_params = {"city": adcode, "key": api_key, "extensions": "base", "output": "JSON"}

            with httpx.Client(timeout=5.0) as client:
                w_resp = client.get(weather_url, params=weather_params)
                w_data = w_resp.json()

            if w_data.get("status") != "1" or not w_data.get("lives"):
                return "天气获取失败"

            live = w_data["lives"][0]
            return f"{live.get('weather', '未知')} {live.get('temperature', '--')}°C 湿度{live.get('humidity', '--')}%"

        except Exception as exc:
            logger.error("天气工具执行失败: %s", exc)
            return "天气查询失败"

    return get_weather_info


# ╔══════════════════════════════════════════════════════════════╗
# ║  AIService 主类                                               ║
# ╚══════════════════════════════════════════════════════════════╝

class AIService:
    """
    AI 分析服务 — ReAct Agent 架构

    工作流程：
    ┌──────────────┐     ┌──────────────┐      ┌─────────────┐
    │ 读取日记+标签 │ ──→ │ 构建 Prompt   │ ──→ │ ReAct Agent │
    └──────────────┘     └──────────────┘      └──────┬──────┘
                                                     │
                                              ┌──────┴──────┐
                                              │  需要工具？   │
                                              └──────┬──────┘
                                           ┌────Yes──┴──No────┐
                                           ▼                   ▼
                                    ┌─────────────┐    ┌──────────────┐
                                    │ 调用工具     │    │ 直接生成回应  │
                                    │ (搜索/天气)  │    └──────────────┘
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │ 综合生成回应  │
                                    └──────────────┘

    关键设计决策：
    1. 优先使用用户配置的 ModelProvider(base_url + model_key)
    2. 回退到系统环境变量配置(LLM_BASE_URL + LLM_API_KEY)
    3. 工具通过工厂函数创建，每次调用绑定当前用户的 db session(数据隔离)
    4. 使用 LangChain 的 create_react_agent 或手动 chain 实现 ReAct 循环
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """
        初始化 AI 服务。

        参数优先级：
        1. 显式传入的参数（来自用户配置的 ModelProvider)
        2. 环境变量配置（系统默认）

        :param base_url: LLM API 地址，如 https://api.deepseek.com
        :param api_key: LLM API Key
        :param model_name: 模型名称，如 deepseek-chat
        """
        # 配置来源：显式参数 > 环境变量
        self._base_url: Optional[str] = base_url or os.getenv("LLM_BASE_URL")
        self._api_key: str = api_key or os.getenv("LLM_API_KEY", "")
        self._model: str = model_name or os.getenv("LLM_MODEL", "deepseek-chat")

        # 校验必要配置
        if not self._api_key:
            raise AIServiceUnavailableError(
                "AI 服务未配置：缺少 API Key。请在「模型管理」中配置模型，或设置环境变量 LLM_API_KEY。"
            )

        # 构建 LLM 实例（懒初始化，此时不会真正连接）
        self._llm = self._build_llm()

        logger.info(
            "AIService 初始化完成 — model=%s, base_url=%s",
            self._model,
            self._base_url or "(默认)",
        )

    def _build_llm(self) -> ChatOpenAI:
        """
        构建 ChatOpenAI 实例。

        为什么用 ChatOpenAI？
        - LangChain 的 ChatOpenAI 兼容所有 OpenAI API 格式的服务
        - DeepSeek、通义千问、LM Studio 等都提供 OpenAI 兼容接口
        - 只需修改 base_url 即可切换不同的 LLM 提供商
        """
        kwargs = {
            "api_key": self._api_key,
            "model": self._model,
            "temperature": 0.7,
            "max_tokens": 300,      # 日记回应不需要太长
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url

        return ChatOpenAI(**kwargs)

    # ──────────────────────────────────────────────────────────
    # 上下文构建方法
    # ──────────────────────────────────────────────────────────

    def _format_tags_context(self, tags: List[Tag]) -> str:
        """
        将标签列表格式化为 Few-shot 上下文。

        Few-shot 的作用：
        - 标签反映了用户对日记的分类和情感标注
        - 例如标签「工作压力」「加班」告诉 AI 这篇日记的主题
        - AI 可以据此调整回应的方向和语气
        """
        if not tags:
            return "（未设置标签）"
        return "、".join(f"#{tag.tag_name}" for tag in tags if tag.tag_name)

    def _format_history(self, entries: List[DiaryEntry], exclude_id: Optional[int] = None) -> str:
        """
        将历史日记格式化为摘要文本。

        :param entries: 日记列表
        :param exclude_id: 要排除的日记 ID（通常是当前日记，避免重复）
        :return: 格式化的历史摘要
        """
        if not entries:
            return "（暂无历史记录）"

        lines = []
        for entry in entries:
            if exclude_id and entry.NID == exclude_id:
                continue
            date_str = entry.create_time.strftime("%Y-%m-%d") if entry.create_time else "未知"
            # 截取前 200 字，避免 Token 过多
            content = entry.content or ""
            snippet = content[:200] + "..." if len(content) > 200 else content

            # 如果有标签，附上标签信息
            tag_str = ""
            if entry.tags:
                tag_str = " [" + ", ".join(f"#{t.tag_name}" for t in entry.tags if t.tag_name) + "]"

            lines.append(f"[{date_str}]{tag_str} {snippet}")

        return "\n".join(lines) if lines else "（暂无历史记录）"

    # ──────────────────────────────────────────────────────────
    # Token 提取辅助方法
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_token_usage(response) -> dict:
        """
        从 LangChain AIMessage 的 response_metadata 中提取详细 token 消耗。

        DeepSeek API 返回的 usage 结构：
        {
            "prompt_tokens": 600,           # 总输入 token
            "completion_tokens": 280,       # 输出 token（付费）
            "total_tokens": 880,
            "prompt_cache_hit_tokens": 400,  # 缓存命中（免费）
            "prompt_cache_miss_tokens": 200  # 缓存未命中（付费输入）
        }
        """
        usage = {}
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})

        return {
            "total_tokens": usage.get("total_tokens", 0),
            "cache_hit_tokens": usage.get("prompt_cache_hit_tokens", 0),    # 免费
            "cache_miss_tokens": usage.get("prompt_cache_miss_tokens", 0),  # 付费输入
            "output_tokens": usage.get("completion_tokens", 0),             # 付费输出
        }

    # ──────────────────────────────────────────────────────────
    # 核心分析方法
    # ──────────────────────────────────────────────────────────

    def analyze(
        self,
        current_entry: DiaryEntry,
        recent_entries: List[DiaryEntry],
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        分析当前日记，生成 AI 回应。

        这是整个 AI 模块的核心入口方法。

        流程：
        1. 构建上下文(标签 Few-shot + 历史摘要 + 天气)
        2. 如果提供了 db 和 user_id, 创建 ReAct Agent(带工具)
        3. 否则使用简单 Chain(Prompt → LLM → 输出)
        4. 调用 LLM 生成分析结果
        5. 返回结果字典(包含分析文本和 Token 消耗)

        :param current_entry: 当前要分析的日记条目
        :param recent_entries: 最近 7 天的日记列表(含当前条目)
        :param db: 数据库会话(可选, 提供后启用 RAG 工具)
        :param user_id: 当前用户 ID(可选, 提供后启用 RAG 工具)
        :return: {"ai_ans": str, "token_cost": int, "cache_hit_tokens": int, "cache_miss_tokens": int, "output_tokens": int, "thk_log": str}
        :raises AIServiceUnavailableError: LLM 服务不可用
        """
        try:
            # ── Step 1: 构建上下文 ──
            tags_context = self._format_tags_context(
                current_entry.tags if current_entry.tags else []
            )
            history_summary = self._format_history(recent_entries, exclude_id=current_entry.NID)
            weather_info = current_entry.weather or "未获取天气信息"

            context = {
                "current_content": current_entry.content or "",
                "tags_context": tags_context,
                "history_summary": history_summary,
                "weather_info": weather_info,
            }

            # ── Step 2: 智能选择执行模式 ──
            # 短日记（< 200 字）且历史少于 3 篇 → Chain 模式（省 token）
            # 长日记或历史丰富 → Agent 模式（可调用工具检索）
            content_len = len(current_entry.content or "")
            history_count = len([e for e in recent_entries if e.NID != current_entry.NID])
            use_agent = (db is not None and user_id is not None
                         and (content_len >= 200 or history_count >= 3))

            if use_agent:
                result_text, token_info, thk_log = self._run_agent(context, db, user_id)
            else:
                result_text, token_info, thk_log = self._run_chain(context)

            logger.info(
                "AI 分析完成 — 总 %d tokens（免费缓存 %d + 付费输入 %d + 付费输出 %d）",
                token_info["total_tokens"], token_info["cache_hit_tokens"],
                token_info["cache_miss_tokens"], token_info["output_tokens"],
            )

            return {
                "ai_ans": result_text,
                "token_cost": token_info["total_tokens"],
                "cache_hit_tokens": token_info["cache_hit_tokens"],
                "cache_miss_tokens": token_info["cache_miss_tokens"],
                "output_tokens": token_info["output_tokens"],
                "thk_log": thk_log,
            }

        except AIServiceUnavailableError:
            raise
        except Exception as exc:
            logger.error("AI 分析失败: %s", exc, exc_info=True)
            return {
                "ai_ans": FALLBACK_FEEDBACK,
                "token_cost": 0,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 0,
                "output_tokens": 0,
                "thk_log": f"[降级] LLM 调用失败: {str(exc)}",
            }

    def _run_chain(self, context: dict) -> tuple[str, dict, str]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT_TEMPLATE),
        ])

        chain = prompt | self._llm
        response = chain.invoke(context)

        token_info = self._extract_token_usage(response)
        result_text = response.content if hasattr(response, "content") else str(response)
        thk_log = f"[Chain] tokens={token_info['total_tokens']} (cache_hit={token_info['cache_hit_tokens']}, miss={token_info['cache_miss_tokens']}, output={token_info['output_tokens']})"

        return result_text, token_info, thk_log

    def _run_agent(self, context: dict, db: Session, user_id: int) -> tuple[str, dict, str]:
        tools = [
            create_diary_search_tool(db, user_id),
            create_weather_tool(),
        ]

        llm_with_tools = self._llm.bind_tools(tools)

        prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
            ("human", USER_PROMPT_TEMPLATE),
        ])

        chain = prompt | llm_with_tools
        response = chain.invoke(context)

        # 累计 token 信息
        token_info = self._extract_token_usage(response)
        thk_log_parts = []

        tool_calls = response.tool_calls if hasattr(response, "tool_calls") else []

        if tool_calls:
            thk_log_parts.append("[Agent] tools called:")
            tool_map = {t.name: t for t in tools}
            tool_results = []

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                thk_log_parts.append(f"  - {tool_name}({tool_args})")

                if tool_name in tool_map:
                    try:
                        result = tool_map[tool_name].invoke(tool_args)
                        tool_results.append(f"[{tool_name}]: {result}")
                        thk_log_parts.append(f"    -> ok")
                    except Exception as exc:
                        tool_results.append(f"[{tool_name} error]: {str(exc)}")
                        thk_log_parts.append(f"    -> fail: {exc}")

            tool_context = "\n".join(tool_results)
            followup_prompt = ChatPromptTemplate.from_messages([
                ("system", AGENT_SYSTEM_PROMPT),
                ("human", USER_PROMPT_TEMPLATE + "\n\n## Tool Results\n" + tool_context),
            ])

            followup_chain = followup_prompt | self._llm
            final_response = followup_chain.invoke(context)

            # 累加第二轮 token
            t2 = self._extract_token_usage(final_response)
            for k in token_info:
                token_info[k] += t2[k]

            result_text = final_response.content if hasattr(final_response, "content") else str(final_response)
        else:
            thk_log_parts.append("[Agent] no tools needed")
            result_text = response.content if hasattr(response, "content") else str(response)

        thk_log_parts.append(f"[Token] total={token_info['total_tokens']} cache_hit={token_info['cache_hit_tokens']} miss={token_info['cache_miss_tokens']} output={token_info['output_tokens']}")
        thk_log = "\n".join(thk_log_parts)

        return result_text, token_info, thk_log


# ╔══════════════════════════════════════════════════════════════╗
# ║  工厂函数：根据用户配置创建 AIService 实例                       ║
# ╚══════════════════════════════════════════════════════════════╝

def create_ai_service_for_user(
    db: Session,
    user_id: int,
) -> AIService:
    """
    为指定用户创建 AIService 实例。

    当前 model_providers 表没有 UID 列，所以查找全局活跃模型。
    如果有活跃模型则使用，否则回退到系统环境变量配置。
    """
    from app.models.model_provider import ModelProvider
    from app.services.model_service import _decrypt

    # 查找活跃模型（表中无 UID 列，查全局）
    active_model = (
        db.query(ModelProvider)
        .filter(ModelProvider.is_active == True)
        .first()
    )

    if active_model and active_model.model_key_encrypted:
        try:
            decrypted_key = _decrypt(active_model.model_key_encrypted)
            logger.info(
                "使用活跃模型: %s (%s)",
                active_model.model_name, active_model.base_url,
            )
            return AIService(
                base_url=active_model.base_url,
                api_key=decrypted_key,
                model_name=active_model.model_name,
            )
        except Exception as exc:
            logger.warning("模型配置解密失败，回退到系统默认: %s", exc)

    # 回退到系统默认配置
    logger.info("无活跃模型配置，使用系统默认配置")
    return AIService()
