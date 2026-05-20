"""
SummaryGeneratorSkill 单元测试
==============================

测试摘要生成 Skill 的核心逻辑：
- should_activate 激活概率判断
- _detect_report_type 报告类型检测
- _build_diary_summary_text 数据格式化
- execute 降级行为

Requirements: 20.6
"""

import sys
sys.path.insert(0, r"d:\work\夜记\backend")

from unittest.mock import patch, MagicMock

from app.skills.summary_generator import (
    SummaryGeneratorSkill,
    _detect_report_type,
    _get_time_range,
    _build_diary_summary_text,
)


class TestShouldActivate:
    """测试 should_activate 激活概率判断"""

    def setup_method(self):
        self.skill = SummaryGeneratorSkill()

    def test_weekly_keyword_high_probability(self):
        """包含周报关键词时应返回高概率"""
        assert self.skill.should_activate("帮我生成本周周报", "retrospective_review") == 0.95
        assert self.skill.should_activate("这周总结一下", "pure_record") == 0.95
        assert self.skill.should_activate("过去七天的情况", "habit_tracking") == 0.95

    def test_monthly_keyword_high_probability(self):
        """包含月报关键词时应返回高概率"""
        assert self.skill.should_activate("生成月报", "retrospective_review") == 0.95
        assert self.skill.should_activate("本月总结", "pure_record") == 0.95
        assert self.skill.should_activate("过去三十天", "emotional_support") == 0.95

    def test_retrospective_with_summary_hints(self):
        """retrospective_review 意图 + 总结相关词汇应返回 0.7"""
        assert self.skill.should_activate("帮我总结一下", "retrospective_review") == 0.7
        assert self.skill.should_activate("回顾最近的状态", "retrospective_review") == 0.7
        assert self.skill.should_activate("复盘一下", "retrospective_review") == 0.7

    def test_retrospective_without_hints(self):
        """retrospective_review 意图但无总结词汇应返回 0.4"""
        assert self.skill.should_activate("最近怎么样", "retrospective_review") == 0.4

    def test_no_match_low_probability(self):
        """无匹配时应返回低概率"""
        assert self.skill.should_activate("今天心情不错", "pure_record") == 0.05
        assert self.skill.should_activate("好难过啊", "emotional_support") == 0.05
        assert self.skill.should_activate("跑步打卡", "habit_tracking") == 0.05


class TestDetectReportType:
    """测试报告类型检测"""

    def test_detect_weekly(self):
        assert _detect_report_type("帮我看看本周情况") == "weekly"
        assert _detect_report_type("这周怎么样") == "weekly"
        assert _detect_report_type("过去7天") == "weekly"

    def test_detect_monthly(self):
        assert _detect_report_type("生成月报") == "monthly"
        assert _detect_report_type("这个月总结") == "monthly"
        assert _detect_report_type("过去30天") == "monthly"

    def test_detect_none(self):
        assert _detect_report_type("今天很开心") is None
        assert _detect_report_type("明天要加油") is None

    def test_monthly_priority_over_weekly(self):
        """当同时包含周和月关键词时，月报优先（月报关键词先检测）"""
        assert _detect_report_type("本月和本周的情况") == "monthly"


class TestGetTimeRange:
    """测试时间范围计算"""

    def test_weekly_range(self):
        start, end = _get_time_range("weekly")
        diff = (end - start).days
        assert diff == 7

    def test_monthly_range(self):
        start, end = _get_time_range("monthly")
        diff = (end - start).days
        assert diff == 30


class TestBuildDiarySummaryText:
    """测试日记数据格式化"""

    def test_with_entries_and_memories(self):
        entries = [
            {"date": "2024-01-15", "content": "今天很开心", "weather": "晴"},
            {"date": "2024-01-16", "content": "有点累", "weather": "阴"},
        ]
        memories = [{"event": "完成了项目", "emotion": "满足"}]
        result = _build_diary_summary_text(entries, memories)
        assert "日记记录" in result
        assert "2024-01-15" in result
        assert "今天很开心" in result
        assert "重要记忆" in result
        assert "完成了项目" in result

    def test_with_entries_only(self):
        entries = [{"date": "2024-01-15", "content": "测试", "weather": ""}]
        result = _build_diary_summary_text(entries, [])
        assert "日记记录" in result
        assert "重要记忆" not in result

    def test_empty_data(self):
        result = _build_diary_summary_text([], [])
        assert "暂无日记数据" in result

    def test_long_content_truncated(self):
        """超过 200 字符的内容应被截断"""
        long_content = "a" * 300
        entries = [{"date": "2024-01-15", "content": long_content, "weather": ""}]
        result = _build_diary_summary_text(entries, [])
        assert "..." in result
        # 截断后不应包含完整的 300 字符
        assert long_content not in result


class TestMetadata:
    """测试 Skill 元数据"""

    def test_metadata_fields(self):
        skill = SummaryGeneratorSkill()
        assert skill.metadata.name == "summary_generator"
        assert skill.metadata.category == "generation"
        assert skill.metadata.token_cost_estimate == 500
        assert skill.metadata.requires_db is True
        assert skill.metadata.requires_network is True
        assert skill.metadata.priority == 1.8


class TestExecute:
    """测试 execute 方法"""

    def test_missing_user_id(self):
        """缺少 user_id 时应返回错误信息"""
        skill = SummaryGeneratorSkill()
        result = skill.execute({"diary_content": "生成周报"})
        assert "缺少用户信息" in result

    @patch("app.skills.summary_generator._fetch_diary_entries")
    @patch("app.skills.summary_generator._fetch_episodic_memories")
    @patch("app.skills.summary_generator._build_llm")
    def test_successful_execution(self, mock_llm, mock_memories, mock_entries):
        """成功执行时应返回 LLM 生成的摘要"""
        mock_entries.return_value = [
            {"date": "2024-01-15", "content": "今天很开心", "weather": "晴"},
        ]
        mock_memories.return_value = []

        mock_response = MagicMock()
        mock_response.content = "📊 主导情绪：开心\n📌 关键事件：...\n📈 趋势方向：稳定\n💡 建议：..."
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = mock_response
        mock_llm.return_value = mock_llm_instance

        skill = SummaryGeneratorSkill()
        result = skill.execute({
            "user_id": 1,
            "diary_content": "帮我生成本周周报",
        })
        assert "主导情绪" in result
        mock_llm_instance.invoke.assert_called_once()

    @patch("app.skills.summary_generator._fetch_diary_entries")
    @patch("app.skills.summary_generator._fetch_episodic_memories")
    @patch("app.skills.summary_generator._build_llm")
    def test_llm_failure_graceful_degradation(self, mock_llm, mock_memories, mock_entries):
        """LLM 调用失败时应优雅降级"""
        mock_entries.return_value = [
            {"date": "2024-01-15", "content": "今天很开心", "weather": "晴"},
        ]
        mock_memories.return_value = []
        mock_llm.side_effect = RuntimeError("LLM_API_KEY 未配置")

        skill = SummaryGeneratorSkill()
        result = skill.execute({
            "user_id": 1,
            "diary_content": "帮我生成本周周报",
        })
        assert "暂时不可用" in result

    @patch("app.skills.summary_generator._fetch_diary_entries")
    @patch("app.skills.summary_generator._fetch_episodic_memories")
    @patch("app.skills.summary_generator._build_llm")
    def test_default_to_weekly_when_no_keywords(self, mock_llm, mock_memories, mock_entries):
        """无报告关键词时默认生成周报"""
        mock_entries.return_value = []
        mock_memories.return_value = []

        mock_response = MagicMock()
        mock_response.content = "暂无足够数据生成摘要"
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = mock_response
        mock_llm.return_value = mock_llm_instance

        skill = SummaryGeneratorSkill()
        result = skill.execute({
            "user_id": 1,
            "diary_content": "帮我看看最近情况",
        })
        # 应该调用 LLM（默认周报）
        mock_llm_instance.invoke.assert_called_once()
