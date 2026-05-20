"""
Knowledge Extractor 单元测试
============================

测试知识抽取器的核心逻辑：
- 内容长度过滤（≤ 100 字符跳过）
- 抽取结果验证和规范化
- 数据库存储逻辑
- LLM 失败时的降级行为
- user_id 强制过滤

Requirements: 17.1, 17.2, 17.4, 17.5, 22.2, 23.3
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.extractor import (
    KnowledgeExtractor,
    extract_knowledge_async,
    MIN_CONTENT_LENGTH,
)


# ===== 测试 KnowledgeExtractor._validate_result =====


class TestValidateResult:
    def setup_method(self):
        self.extractor = KnowledgeExtractor(api_key="test-key")

    def test_valid_full_result(self):
        """完整有效的抽取结果应正确解析。"""
        raw = {
            "persons": [
                {"name": "小明", "relation": "同事", "sentiment": 0.6}
            ],
            "events": [
                {"description": "开会讨论项目", "inferred_date": "2024-01-15", "emotion": "焦虑"}
            ],
            "places": ["公司", "咖啡厅"],
            "topics": ["工作", "项目管理"],
            "mood_score": -0.3,
        }
        result = self.extractor._validate_result(raw)

        assert len(result["persons"]) == 1
        assert result["persons"][0]["name"] == "小明"
        assert result["persons"][0]["relation"] == "同事"
        assert result["persons"][0]["sentiment"] == 0.6

        assert len(result["events"]) == 1
        assert result["events"][0]["description"] == "开会讨论项目"

        assert result["places"] == ["公司", "咖啡厅"]
        assert result["topics"] == ["工作", "项目管理"]
        assert result["mood_score"] == -0.3

    def test_empty_result(self):
        """空结果应返回默认结构。"""
        result = self.extractor._validate_result({})

        assert result["persons"] == []
        assert result["events"] == []
        assert result["places"] == []
        assert result["topics"] == []
        assert result["mood_score"] == 0.0

    def test_mood_score_clamped(self):
        """mood_score 应被限制在 [-1.0, 1.0] 范围内。"""
        result = self.extractor._validate_result({"mood_score": 5.0})
        assert result["mood_score"] == 1.0

        result = self.extractor._validate_result({"mood_score": -3.0})
        assert result["mood_score"] == -1.0

    def test_invalid_mood_score_type(self):
        """无效的 mood_score 类型应默认为 0.0。"""
        result = self.extractor._validate_result({"mood_score": "invalid"})
        assert result["mood_score"] == 0.0

    def test_persons_missing_name_filtered(self):
        """缺少 name 字段的人物应被过滤。"""
        raw = {
            "persons": [
                {"name": "小红", "relation": "朋友", "sentiment": 0.8},
                {"relation": "同事", "sentiment": 0.5},  # 缺少 name
            ]
        }
        result = self.extractor._validate_result(raw)
        assert len(result["persons"]) == 1
        assert result["persons"][0]["name"] == "小红"

    def test_events_missing_description_filtered(self):
        """缺少 description 字段的事件应被过滤。"""
        raw = {
            "events": [
                {"description": "加班", "emotion": "疲惫"},
                {"inferred_date": "2024-01-01"},  # 缺少 description
            ]
        }
        result = self.extractor._validate_result(raw)
        assert len(result["events"]) == 1

    def test_empty_places_and_topics_filtered(self):
        """空字符串的地点和话题应被过滤。"""
        raw = {
            "places": ["北京", "", None, "上海"],
            "topics": ["工作", "", None, "健康"],
        }
        result = self.extractor._validate_result(raw)
        assert result["places"] == ["北京", "上海"]
        assert result["topics"] == ["工作", "健康"]


# ===== 测试 KnowledgeExtractor.extract =====


class TestExtract:
    def setup_method(self):
        self.extractor = KnowledgeExtractor(api_key="test-key")

    @pytest.mark.asyncio
    async def test_short_content_returns_none(self):
        """内容 ≤ 100 字符时应返回 None（Requirement 17.1）。"""
        result = await self.extractor.extract("短内容")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_content_returns_none(self):
        """空内容应返回 None。"""
        result = await self.extractor.extract("")
        assert result is None

        result = await self.extractor.extract(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_exactly_100_chars_returns_none(self):
        """恰好 100 字符的内容应返回 None（阈值为 > 100）。"""
        content = "a" * 100
        result = await self.extractor.extract(content)
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """成功的 LLM 调用应返回结构化结果。"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "persons": [{"name": "小明", "relation": "同事", "sentiment": 0.5}],
            "events": [{"description": "开会", "inferred_date": "", "emotion": "平静"}],
            "places": ["办公室"],
            "topics": ["工作"],
            "mood_score": 0.2,
        })

        with patch.object(self.extractor, "_build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_build.return_value = mock_llm

            content = "今天和同事小明一起在办公室开会讨论了新项目的进展，感觉还不错，虽然有些细节需要继续完善，但整体方向是对的。" + "x" * 50
            result = await self.extractor.extract(content)

        assert result is not None
        assert result["persons"][0]["name"] == "小明"
        assert result["places"] == ["办公室"]
        assert result["mood_score"] == 0.2

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        """LLM 调用失败时应返回 None（Requirement 17.5, 23.3）。"""
        with patch.object(self.extractor, "_build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API timeout"))
            mock_build.return_value = mock_llm

            content = "a" * 150
            result = await self.extractor.extract(content)

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        """LLM 返回无效 JSON 时应返回 None。"""
        mock_response = MagicMock()
        mock_response.content = "这不是有效的 JSON"

        with patch.object(self.extractor, "_build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_build.return_value = mock_llm

            content = "a" * 150
            result = await self.extractor.extract(content)

        assert result is None

    @pytest.mark.asyncio
    async def test_markdown_wrapped_json_parsed(self):
        """LLM 返回 markdown 包裹的 JSON 应正确解析。"""
        mock_response = MagicMock()
        mock_response.content = '```json\n{"persons": [], "events": [], "places": [], "topics": ["测试"], "mood_score": 0.5}\n```'

        with patch.object(self.extractor, "_build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_build.return_value = mock_llm

            content = "a" * 150
            result = await self.extractor.extract(content)

        assert result is not None
        assert result["topics"] == ["测试"]
        assert result["mood_score"] == 0.5


# ===== 测试 KnowledgeExtractor.store_extraction =====


class TestStoreExtraction:
    def setup_method(self):
        self.extractor = KnowledgeExtractor(api_key="test-key")
        self.mock_db = MagicMock()

    def test_stores_all_entity_types(self):
        """应为每种非空实体类型创建一条 KnowledgeEntry。"""
        extraction = {
            "persons": [{"name": "小明", "relation": "同事", "sentiment": 0.5}],
            "events": [{"description": "开会", "inferred_date": "", "emotion": "平静"}],
            "places": ["办公室"],
            "topics": ["工作"],
            "mood_score": 0.3,
        }

        entries = self.extractor.store_extraction(
            db=self.mock_db,
            user_id=1,
            diary_nid=100,
            extraction=extraction,
        )

        # 5 种实体类型都有数据：person, event, place, topic, mood
        assert len(entries) == 5
        entity_types = {e.entity_type for e in entries}
        assert entity_types == {"person", "event", "place", "topic", "mood"}

        # 验证 user_id 和 diary_nid 正确关联
        for entry in entries:
            assert entry.user_id == 1
            assert entry.diary_nid == 100

        # 验证 db.add 和 db.commit 被调用
        assert self.mock_db.add.call_count == 5
        self.mock_db.commit.assert_called_once()

    def test_skips_empty_entities(self):
        """空实体类型不应创建记录。"""
        extraction = {
            "persons": [],
            "events": [],
            "places": [],
            "topics": ["工作"],
            "mood_score": 0.0,  # 0.0 不存储 mood
        }

        entries = self.extractor.store_extraction(
            db=self.mock_db,
            user_id=1,
            diary_nid=100,
            extraction=extraction,
        )

        # 只有 topic 有数据
        assert len(entries) == 1
        assert entries[0].entity_type == "topic"

    def test_zero_mood_score_not_stored(self):
        """mood_score 为 0.0 时不存储 mood 条目。"""
        extraction = {
            "persons": [],
            "events": [],
            "places": [],
            "topics": [],
            "mood_score": 0.0,
        }

        entries = self.extractor.store_extraction(
            db=self.mock_db,
            user_id=1,
            diary_nid=100,
            extraction=extraction,
        )

        assert len(entries) == 0
        self.mock_db.commit.assert_not_called()

    def test_entity_data_is_json(self):
        """entity_data 应为有效的 JSON 字符串。"""
        extraction = {
            "persons": [{"name": "小红", "relation": "朋友", "sentiment": 0.8}],
            "events": [],
            "places": [],
            "topics": [],
            "mood_score": 0.0,
        }

        entries = self.extractor.store_extraction(
            db=self.mock_db,
            user_id=1,
            diary_nid=100,
            extraction=extraction,
        )

        assert len(entries) == 1
        data = json.loads(entries[0].entity_data)
        assert data[0]["name"] == "小红"


# ===== 测试 KnowledgeExtractor.query_by_user =====


class TestQueryByUser:
    def setup_method(self):
        self.extractor = KnowledgeExtractor(api_key="test-key")

    def test_query_forces_user_id_filter(self):
        """查询应强制 user_id 过滤（Requirement 22.2）。"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        self.extractor.query_by_user(db=mock_db, user_id=42)

        # 验证 filter 被调用（user_id 过滤）
        mock_db.query.assert_called_once()
        mock_query.filter.assert_called()

    def test_query_with_entity_type_filter(self):
        """按实体类型过滤应正常工作。"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        self.extractor.query_by_user(
            db=mock_db, user_id=42, entity_type="person"
        )

        # filter 应被调用两次（user_id + entity_type）
        assert mock_query.filter.call_count == 2


# ===== 测试 extract_knowledge_async =====


class TestExtractKnowledgeAsync:
    @pytest.mark.asyncio
    async def test_short_content_skipped(self):
        """短内容应直接跳过，不调用 LLM。"""
        # 不应抛出异常
        await extract_knowledge_async(
            user_id=1,
            diary_nid=100,
            content="短内容",
        )

    @pytest.mark.asyncio
    async def test_empty_content_skipped(self):
        """空内容应直接跳过。"""
        await extract_knowledge_async(
            user_id=1,
            diary_nid=100,
            content="",
        )

    @pytest.mark.asyncio
    async def test_llm_failure_does_not_raise(self):
        """LLM 失败不应抛出异常（Requirement 23.3）。"""
        with patch(
            "app.knowledge.extractor.KnowledgeExtractor.extract",
            new_callable=AsyncMock,
            side_effect=Exception("LLM 不可用"),
        ):
            # 不应抛出异常
            await extract_knowledge_async(
                user_id=1,
                diary_nid=100,
                content="a" * 150,
            )

    @pytest.mark.asyncio
    async def test_successful_extraction_stores_results(self):
        """成功抽取应存储结果到数据库。"""
        mock_extraction = {
            "persons": [{"name": "测试", "relation": "", "sentiment": 0.0}],
            "events": [],
            "places": [],
            "topics": [],
            "mood_score": 0.5,
        }

        mock_db = MagicMock()

        with patch(
            "app.knowledge.extractor.KnowledgeExtractor.extract",
            new_callable=AsyncMock,
            return_value=mock_extraction,
        ), patch(
            "app.knowledge.extractor.SessionLocal",
            return_value=mock_db,
        ):
            await extract_knowledge_async(
                user_id=1,
                diary_nid=100,
                content="a" * 150,
            )

        # 验证 db.add 和 db.commit 被调用
        assert mock_db.add.called
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()
