"""
Knowledge Extractor — 结构化知识抽取器
======================================

从日记内容中提取结构化信息：人物、事件、地点、话题、mood_score。
使用单次 LLM 调用 + 结构化输出提示，每次抽取消耗不超过 500 tokens。

核心设计：
- 异步执行，fire-and-forget 模式，不阻塞日记保存
- LLM 调用失败时静默跳过，不影响主流程（Requirement 23.3）
- 所有数据库操作强制 user_id 过滤（Requirement 22.2）
- 仅对 > 100 字符的日记触发抽取（Requirement 17.1）

Requirements: 17.1, 17.2, 17.4, 17.5, 22.2, 23.3
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.knowledge_entry import KnowledgeEntry

logger = logging.getLogger(__name__)

# 最小日记长度阈值：低于此长度不触发抽取
MIN_CONTENT_LENGTH = 100

# 抽取 Prompt — 要求 LLM 输出严格 JSON 格式
EXTRACTION_PROMPT = """请从以下日记内容中提取结构化信息，严格按照 JSON 格式输出。

要求：
1. persons: 提取提到的人物，每个人物包含 name（姓名/称呼）、relation（关系，如同事/朋友/家人，未知则为空）、sentiment（情感倾向，-1.0到1.0）
2. events: 提取主要事件，每个事件包含 description（简短描述）、inferred_date（推断日期，格式YYYY-MM-DD，无法推断则为空）、emotion（情绪标签，如开心/难过/焦虑）
3. places: 提取提到的地点名称列表
4. topics: 提取主要话题/主题列表（如工作、健康、感情）
5. mood_score: 整体情绪分数，-1.0（极度负面）到 1.0（极度正面）

如果某个类别没有相关信息，返回空列表或 0.0。

日记内容：
{content}

请直接输出 JSON，不要包含其他文字：
{{"persons": [...], "events": [...], "places": [...], "topics": [...], "mood_score": 0.0}}"""


class KnowledgeExtractor:
    """
    知识抽取器 — 从日记中提取结构化实体信息。

    使用单次 LLM 调用配合结构化输出提示词，
    每次提取消耗不超过 500 tokens（通过 max_tokens 限制）。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        初始化抽取器。

        参数优先级：显式传入 > 环境变量。
        """
        self._base_url = base_url or os.getenv("LLM_BASE_URL")
        self._api_key = api_key or os.getenv("LLM_API_KEY", "")
        self._model = model_name or os.getenv("LLM_MODEL", "deepseek-chat")

    def _build_llm(self) -> ChatOpenAI:
        """构建用于抽取的 LLM 实例，max_tokens 限制为 500。"""
        kwargs = {
            "api_key": self._api_key,
            "model": self._model,
            "temperature": 0.1,  # 低温度确保输出稳定
            "max_tokens": 500,   # 每次抽取 ≤ 500 tokens (Requirement 17.4)
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return ChatOpenAI(**kwargs)

    async def extract(self, content: str) -> Optional[Dict[str, Any]]:
        """
        从日记内容中提取结构化信息。

        :param content: 日记文本内容
        :return: 提取结果字典，失败时返回 None
        """
        if not content or len(content) <= MIN_CONTENT_LENGTH:
            return None

        try:
            llm = self._build_llm()
            prompt = EXTRACTION_PROMPT.format(content=content)

            # 使用 ainvoke 异步调用 LLM
            response = await llm.ainvoke(prompt)
            raw_text = response.content.strip()

            # 解析 JSON 输出
            # 处理可能的 markdown 代码块包裹
            if raw_text.startswith("```"):
                # 去除 ```json 和 ``` 包裹
                lines = raw_text.split("\n")
                raw_text = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                )

            result = json.loads(raw_text)
            return self._validate_result(result)

        except json.JSONDecodeError as exc:
            logger.warning("知识抽取 JSON 解析失败: %s", exc)
            return None
        except Exception as exc:
            # LLM 调用失败时跳过抽取 (Requirement 17.5, 23.3)
            logger.warning("知识抽取 LLM 调用失败（跳过）: %s", exc)
            return None

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并规范化抽取结果。

        确保所有必要字段存在且类型正确。
        """
        validated = {
            "persons": [],
            "events": [],
            "places": [],
            "topics": [],
            "mood_score": 0.0,
        }

        # persons
        if isinstance(result.get("persons"), list):
            for p in result["persons"]:
                if isinstance(p, dict) and "name" in p:
                    validated["persons"].append({
                        "name": str(p.get("name", "")),
                        "relation": str(p.get("relation", "")),
                        "sentiment": float(p.get("sentiment", 0.0)),
                    })

        # events
        if isinstance(result.get("events"), list):
            for e in result["events"]:
                if isinstance(e, dict) and "description" in e:
                    validated["events"].append({
                        "description": str(e.get("description", "")),
                        "inferred_date": str(e.get("inferred_date", "")),
                        "emotion": str(e.get("emotion", "")),
                    })

        # places
        if isinstance(result.get("places"), list):
            validated["places"] = [
                str(p) for p in result["places"] if p
            ]

        # topics
        if isinstance(result.get("topics"), list):
            validated["topics"] = [
                str(t) for t in result["topics"] if t
            ]

        # mood_score
        try:
            score = float(result.get("mood_score", 0.0))
            validated["mood_score"] = max(-1.0, min(1.0, score))
        except (TypeError, ValueError):
            validated["mood_score"] = 0.0

        return validated

    def store_extraction(
        self,
        db: Session,
        user_id: int,
        diary_nid: int,
        extraction: Dict[str, Any],
    ) -> List[KnowledgeEntry]:
        """
        将抽取结果存储到 KnowledgeEntry 表。

        每种实体类型存储为一条记录，entity_data 为 JSON 字符串。
        所有记录关联 user_id 和 diary_nid（Requirement 17.2, 22.2）。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param diary_nid: 日记 NID
        :param extraction: 抽取结果字典
        :return: 创建的 KnowledgeEntry 列表
        """
        entries: List[KnowledgeEntry] = []
        now = datetime.utcnow()

        # 存储人物实体
        if extraction.get("persons"):
            entry = KnowledgeEntry(
                user_id=user_id,
                diary_nid=diary_nid,
                entity_type="person",
                entity_data=json.dumps(extraction["persons"], ensure_ascii=False),
                extracted_at=now,
            )
            entries.append(entry)

        # 存储事件实体
        if extraction.get("events"):
            entry = KnowledgeEntry(
                user_id=user_id,
                diary_nid=diary_nid,
                entity_type="event",
                entity_data=json.dumps(extraction["events"], ensure_ascii=False),
                extracted_at=now,
            )
            entries.append(entry)

        # 存储地点实体
        if extraction.get("places"):
            entry = KnowledgeEntry(
                user_id=user_id,
                diary_nid=diary_nid,
                entity_type="place",
                entity_data=json.dumps(extraction["places"], ensure_ascii=False),
                extracted_at=now,
            )
            entries.append(entry)

        # 存储话题实体
        if extraction.get("topics"):
            entry = KnowledgeEntry(
                user_id=user_id,
                diary_nid=diary_nid,
                entity_type="topic",
                entity_data=json.dumps(extraction["topics"], ensure_ascii=False),
                extracted_at=now,
            )
            entries.append(entry)

        # 存储 mood_score（作为特殊实体类型）
        mood_score = extraction.get("mood_score", 0.0)
        if mood_score != 0.0:
            entry = KnowledgeEntry(
                user_id=user_id,
                diary_nid=diary_nid,
                entity_type="mood",
                entity_data=json.dumps({"mood_score": mood_score}, ensure_ascii=False),
                extracted_at=now,
            )
            entries.append(entry)

        # 批量写入数据库
        if entries:
            for entry in entries:
                db.add(entry)
            db.commit()

        return entries

    def query_by_user(
        self,
        db: Session,
        user_id: int,
        entity_type: Optional[str] = None,
        diary_nid: Optional[int] = None,
    ) -> List[KnowledgeEntry]:
        """
        查询用户的知识条目，强制 user_id 过滤（Requirement 22.2）。

        :param db: 数据库会话
        :param user_id: 用户 ID（必须）
        :param entity_type: 可选，按实体类型过滤
        :param diary_nid: 可选，按日记 NID 过滤
        :return: KnowledgeEntry 列表
        """
        query = db.query(KnowledgeEntry).filter(
            KnowledgeEntry.user_id == user_id  # 强制 user_id 过滤
        )

        if entity_type:
            query = query.filter(KnowledgeEntry.entity_type == entity_type)

        if diary_nid is not None:
            query = query.filter(KnowledgeEntry.diary_nid == diary_nid)

        return query.order_by(KnowledgeEntry.extracted_at.desc()).all()

    def search_entities(
        self,
        db: Session,
        user_id: int,
        keyword: str,
        entity_type: Optional[str] = None,
    ) -> List[KnowledgeEntry]:
        """
        在用户的知识库中搜索包含关键词的实体。

        强制 user_id 过滤确保数据隔离（Requirement 22.2）。

        :param db: 数据库会话
        :param user_id: 用户 ID（必须）
        :param keyword: 搜索关键词
        :param entity_type: 可选，按实体类型过滤
        :return: 匹配的 KnowledgeEntry 列表
        """
        query = db.query(KnowledgeEntry).filter(
            KnowledgeEntry.user_id == user_id,  # 强制 user_id 过滤
            KnowledgeEntry.entity_data.contains(keyword),
        )

        if entity_type:
            query = query.filter(KnowledgeEntry.entity_type == entity_type)

        return query.order_by(KnowledgeEntry.extracted_at.desc()).all()


async def extract_knowledge_async(
    user_id: int,
    diary_nid: int,
    content: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> None:
    """
    异步知识抽取入口（fire-and-forget 模式）。

    在日记保存后异步调用，不阻塞主流程。
    LLM 调用失败时静默跳过，不影响日记保存（Requirement 23.3）。

    :param user_id: 用户 ID
    :param diary_nid: 日记 NID
    :param content: 日记内容
    :param base_url: LLM API 地址（可选）
    :param api_key: LLM API Key（可选）
    :param model_name: 模型名称（可选）
    """
    # 仅对 > 100 字符的日记触发抽取 (Requirement 17.1)
    if not content or len(content) <= MIN_CONTENT_LENGTH:
        logger.debug(
            "日记内容过短（%d 字符），跳过知识抽取: diary_nid=%d",
            len(content) if content else 0, diary_nid,
        )
        return

    try:
        extractor = KnowledgeExtractor(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
        )

        # 异步调用 LLM 提取
        extraction = await extractor.extract(content)
        if extraction is None:
            logger.debug("知识抽取无结果: diary_nid=%d", diary_nid)
            return

        # 使用独立的数据库会话存储结果（避免与主流程的 session 冲突）
        db = SessionLocal()
        try:
            entries = extractor.store_extraction(
                db=db,
                user_id=user_id,
                diary_nid=diary_nid,
                extraction=extraction,
            )
            logger.info(
                "知识抽取完成: diary_nid=%d, entries=%d, types=%s",
                diary_nid,
                len(entries),
                [e.entity_type for e in entries],
            )
        finally:
            db.close()

    except Exception as exc:
        # 任何异常都不应影响日记保存 (Requirement 23.3)
        logger.warning(
            "知识抽取异步任务失败（已跳过）: diary_nid=%d, error=%s",
            diary_nid, exc,
        )


def fire_and_forget_extraction(
    user_id: int,
    diary_nid: int,
    content: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> None:
    """
    Fire-and-forget 知识抽取调度器。

    在同步上下文中调度异步抽取任务。
    适用于 FastAPI 路由中的同步代码调用。
    失败时静默跳过，不影响调用方。

    :param user_id: 用户 ID
    :param diary_nid: 日记 NID
    :param content: 日记内容
    :param base_url: LLM API 地址（可选）
    :param api_key: LLM API Key（可选）
    :param model_name: 模型名称（可选）
    """
    # 仅对 > 100 字符的日记触发
    if not content or len(content) <= MIN_CONTENT_LENGTH:
        return

    try:
        coro = extract_knowledge_async(
            user_id=user_id,
            diary_nid=diary_nid,
            content=content,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
        )
        asyncio.ensure_future(coro)
    except RuntimeError:
        # 没有运行中的事件循环（非 async 上下文），创建新的
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(
                    asyncio.run,
                    extract_knowledge_async(
                        user_id=user_id,
                        diary_nid=diary_nid,
                        content=content,
                        base_url=base_url,
                        api_key=api_key,
                        model_name=model_name,
                    ),
                )
        except Exception as exc:
            logger.warning("知识抽取调度失败（已跳过）: %s", exc)
    except Exception as exc:
        logger.warning("知识抽取调度失败（已跳过）: %s", exc)
