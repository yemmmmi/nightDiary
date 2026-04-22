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
from typing import Dict, Optional, List

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
SYSTEM_PROMPT = """你是"夜记助手"，一个心理陪伴助手，调用工具的目的是为了
更好地理解用户处境或提供客观建议、减少人机感。你的输出应控制在50-150字的中文。"""

# Agent 模式专用 System Prompt（多了工具说明）
AGENT_SYSTEM_PROMPT = SYSTEM_PROMPT + """
可用工具:
- search_diary(搜索历史日记，支持关键词/日期/标签多维度查询)
- get_weather_info(查天气，自动获取用户地址)
- analyze_sentiment(分析文本情感倾向、强度和关键词)
- get_user_address(获取用户地址信息)
不需要就直接回应。"""

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
# ║  纯函数（便于独立测试）                                         ║
# ╚══════════════════════════════════════════════════════════════╝

def should_use_cache(last_time: Optional[datetime], now: datetime, threshold_minutes: int = 30) -> bool:
    """
    判断是否应使用缓存。
    - last_time 为 None → False (无活跃记录，应调用 API)
    - now - last_time < threshold_minutes 分钟 → True (近期活跃，用缓存)
    -                                     否则 → False (超过阈值, 应刷新)
    """
    if last_time is None:
        return False
    return (now - last_time).total_seconds() < threshold_minutes * 60


def filter_diary_results(
    results: List[Dict],
    start_date: str = "",
    end_date: str = "",
    tag: str = "",
) -> List[Dict]:
    """
    对日记检索结果进行多维度过滤（纯函数，便于独立测试）。

    所有提供的条件取交集：
    - start_date 非空时，仅保留 item["date"] >= start_date 的结果
    - end_date 非空时，仅保留 item["date"] <= end_date 的结果
    - tag 非空时，仅保留 item["tags"] 中包含该 tag 的结果

    :param results: Chroma 检索返回的结果列表，每项含 date、tags、content 等字段
    :param start_date: 开始日期 "YYYY-MM-DD"（可选）
    :param end_date: 结束日期 "YYYY-MM-DD"（可选）
    :param tag: 标签名称（可选）
    :return: 过滤后的结果列表
    """
    filtered = results
    if start_date:
        filtered = [item for item in filtered if item.get("date", "") >= start_date]
    if end_date:
        filtered = [item for item in filtered if item.get("date", "") <= end_date]
    if tag:
        filtered = [item for item in filtered if tag in item.get("tags", "")]
    return filtered


def format_diary_result(item: Dict) -> str:
    """
    格式化单条日记结果为展示字符串（纯函数，便于独立测试）。

    格式: [{date}]{tag_part} {snippet}
    - tag_part: 有标签时为 " {tags}"，无标签时为空
    - snippet: 内容前 150 字，超出部分用 "..." 截断

    :param item: 日记结果字典，含 date、tags、content 字段
    :return: 格式化后的字符串
    """
    date_str = item.get("date", "未知日期")
    content = item.get("content", "")
    tags = item.get("tags", "")
    snippet = content[:150] + "..." if len(content) > 150 else content
    tag_part = f" {tags}" if tags else ""
    return f"[{date_str}]{tag_part} {snippet}"


# ╔══════════════════════════════════════════════════════════════╗
# ║  LangChain Tools（ReAct Agent 的工具集）                       ║
# ╚══════════════════════════════════════════════════════════════╝

def create_diary_search_tool(db: Session, user_id: int):
    """
    工厂函数：创建日记语义搜索工具（基于 Chroma 向量检索 + 多维过滤）。

    为什么用工厂函数？
    - LangChain 的 @tool 装饰器创建的是全局工具
    - 但我们需要每次调用时绑定不同的 user_id
    - 工厂函数通过闭包捕获上下文，实现用户数据隔离

    RAG 实现说明：
    - 使用 Chroma 向量数据库 + text2vec-base-chinese Embedding 模型
    - 查询时将关键词转为向量，在用户的 Collection 中做余弦相似度检索
    - 支持多维度过滤：时间范围、标签、关键词，取交集
    - 相比 SQL LIKE, 语义检索能理解"意思"而非仅匹配"字面"
    """
    @tool
    def search_diary(
        query: str = "",
        start_date: str = "",
        end_date: str = "",
        tag: str = "",
    ) -> str:
        """搜索用户的历史日记。支持多维度查询：
        - query: 关键词或描述，进行语义搜索
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        - tag: 标签名称，如"工作"
        至少提供一个参数。返回匹配的历史日记摘要。"""
        try:
            from app.services.vector_service import search_similar_diaries

            # 使用 Chroma 语义检索，top_k=10 多取一些用于后续过滤
            results = search_similar_diaries( # 此处暂时不理解，需后续深入了解，比如top_k的值的含义
                user_id=user_id,
                query=query or "",
                top_k=10,
            )

            # 多维度过滤（日期范围 + 标签）
            results = filter_diary_results(results, start_date=start_date, end_date=end_date, tag=tag)

            # 取前 5 条
            results = results[:5]

            if not results:
                # 构建查询条件描述
                conditions = []
                if query:
                    conditions.append(query)
                if start_date:
                    conditions.append(f"从{start_date}")
                if end_date:
                    conditions.append(f"到{end_date}")
                if tag:
                    conditions.append(f"标签:{tag}")
                conditions_str = "、".join(conditions) if conditions else "指定条件"
                return f"未找到与「{conditions_str}」匹配的历史日记。"

            lines = [format_diary_result(item) for item in results]
            return "\n".join(lines)
        except Exception as exc:
            logger.error("日记语义搜索工具执行失败: %s", exc)
            return "日记搜索暂时不可用"

    return search_diary


def _fetch_weather_from_api(city: str) -> Optional[str]:
    """
    同步调用高德地图 API 获取天气数据。
    成功返回天气描述字符串，失败返回 None。
    """
    import httpx

    api_key = os.getenv("WEATHER_API_KEY", "")
    if not api_key:
        return None

    try:
        geo_url = "https://restapi.amap.com/v3/geocode/geo"
        geo_params = {"address": city, "key": api_key, "output": "JSON"}

        with httpx.Client(timeout=5.0) as client:
            geo_resp = client.get(geo_url, params=geo_params)
            geo_data = geo_resp.json()

        if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
            return None

        adcode = geo_data["geocodes"][0].get("adcode")

        weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        weather_params = {"city": adcode, "key": api_key, "extensions": "base", "output": "JSON"}

        with httpx.Client(timeout=5.0) as client:
            w_resp = client.get(weather_url, params=weather_params)
            w_data = w_resp.json()

        if w_data.get("status") != "1" or not w_data.get("lives"):
            return None

        live = w_data["lives"][0]
        return f"{live.get('weather', '未知')} {live.get('temperature', '--')}°C 湿度{live.get('humidity', '--')}%"
    except Exception as exc:
        logger.error("高德 API 调用失败: %s", exc)
        return None


def create_weather_tool(db: Session, user_id: int):
    """
    工厂函数：创建天气查询工具（缓存优化版）。

    通过闭包绑定 db 和 user_id, 实现用户数据隔离。
    工具内部根据 User.last_time 智能选择 Redis 缓存或高德 API:
    - last_time < 30min → 优先读 Redis 缓存
    - last_time >= 30min 或为空 → 直接调用高德 API
    - 缓存未命中或 Redis 不可用 → 回退调用高德 API
    - API 成功后回填 Redis(有效结果 TTL=3600s,无效结果 TTL=300s)
    """
    @tool
    def get_weather_info() -> str:
        """查询当前用户所在城市的天气信息。无需参数，自动获取用户地址，注意考虑地址不存在的情况。
        可以在回应中提及天气，让分析更贴近用户的真实生活场景。"""
        try:
            from app.models.user import User

            user = db.query(User).filter(User.UID == user_id).first()
            if user is None:
                return "天气查询失败, 未查询到用户名。"

            address = user.address
            if not address or not address.strip():
                return "未设置地址。"

            last_time = user.last_time
            now = datetime.now()
            cache_key = f"weather:{user_id}"

            # 判断是否应使用缓存
            if should_use_cache(last_time, now):
                try:
                    import redis as sync_redis
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                    r = sync_redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                    cached = r.get(cache_key)
                    if cached:
                        return cached
                except Exception as exc:
                    logger.warning("Redis 缓存读取失败，回退 API: %s", exc)

            # 缓存未命中或不应使用缓存 → 调用高德 API
            result = _fetch_weather_from_api(address)

            if result:
                # 有效结果，回填 Redis，TTL=3600s
                try:
                    import redis as sync_redis
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                    r = sync_redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                    r.setex(cache_key, 3600, result)
                except Exception as exc:
                    logger.warning("Redis 缓存回填失败: %s", exc)
                return result
            else:
                # 无效结果，短 TTL 缓存避免频繁请求
                try:
                    import redis as sync_redis
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                    r = sync_redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
                    r.setex(cache_key, 300, "天气获取失败")
                except Exception as exc:
                    logger.warning("Redis 缓存回填失败: %s", exc)
                return "天气获取失败"

        except Exception as exc:
            logger.error("天气工具执行失败: %s", exc)
            return "天气查询失败"

    return get_weather_info


def create_address_tool(db: Session, user_id: int):
    """
    工厂函数：创建用户地址获取工具。

    通过闭包绑定 db 和 user_id, 实现用户数据隔离。
    Agent 可调用此工具获取用户地址，为天气查询等场景提供地理上下文。
    """
    @tool
    def get_user_address() -> str:
        """获取当前用户的地址信息。无需参数，自动查询当前用户。
        可用于了解用户所在地区，为天气查询等提供地理上下文。"""
        try:
            from app.models.user import User

            user = db.query(User).filter(User.UID == user_id).first()
            if user is None or not user.address:
                return "用户未设置地址信息"
            return user.address
        except Exception as exc:
            logger.error("获取用户地址失败: %s", exc)
            return "获取地址信息失败"

    return get_user_address


def create_sentiment_tool(llm: ChatOpenAI):
    """
    工厂函数：创建情感分析工具。

    通过闭包绑定 LLM 实例，复用 AIService 的模型配置。
    Agent 可调用此工具对日记文本进行结构化情感分析。
    """
    @tool
    def analyze_sentiment(text: str) -> str:
        """分析文本的情感倾向。输入日记文本内容，返回情感倾向（正面/负面/中性）、情感强度（1-5分）和关键情感词。用于更精准地理解用户情绪状态。"""
        if not text or not text.strip():
            return "无法分析空内容"

        try:
            prompt = f"""请对以下文本进行情感分析，严格按照以下格式输出：
情感倾向：[正面/负面/中性]
情感强度：[1-5]（1=很弱，5=很强）
关键情感词：[词1, 词2, ...]（最多5个）

文本：{text}"""
            response = llm.invoke(prompt)
            return response.content
        except Exception as exc:
            logger.error("情感分析工具执行失败: %s", exc)
            return "情感分析暂时不可用"

    return analyze_sentiment


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
                                              │  需要工具？  │
                                              └──────┬──────┘
                                           ┌────Yes──┴──No────┐
                                           ▼                   ▼
                                    ┌─────────────┐    ┌──────────────┐
                                    │ 调用工具     │    │ 直接生成回应  │
                                    │             │    └──────────────┘
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
                "AI 服务未配置：缺少 API Key。请在「模型管理」中配置模型, 或设置环境变量 LLM_API_KEY。"
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

        为什么用 ChatOpenAI ?
        - LangChain 的 ChatOpenAI 兼容所有 OpenAI API 格式的服务
        - DeepSeek、通义千问、LM Studio 等都提供 OpenAI 兼容接口
        - 只需修改 base_url 即可切换不同的 LLM 提供商
        """
        kwargs = {
            "api_key": self._api_key,
            "model": self._model,
            "temperature": 0.7,     # 温度参数
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
        :param exclude_id: 要排除的日记 ID(通常是当前日记，避免重复)
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
            create_weather_tool(db, user_id),
            create_sentiment_tool(self._llm),
            create_address_tool(db, user_id),
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
# ║  工厂函数：根据用户配置创建 AIService 实例                      ║
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
