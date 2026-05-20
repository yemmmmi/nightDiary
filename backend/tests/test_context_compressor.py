"""
ContextCompressor 单元测试
============================

测试智能上下文压缩器的核心逻辑：
- 低信息密度过滤
- Token 估算
- 贪心填充 Token 上限
- 摘要生成（无 LLM 时截断）
- Episodic Memory 优先
"""

import pytest
from app.agents.context_compressor import (
    ContextCompressor,
    estimate_tokens,
    _is_low_density,
    _generate_summary,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  estimate_tokens 测试                                         ║
# ╚══════════════════════════════════════════════════════════════╝

class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_chinese_text(self):
        # 10 个中文字符 → 约 15 tokens
        tokens = estimate_tokens("今天天气真好啊我很开心")
        assert 12 <= tokens <= 18

    def test_english_text(self):
        # "hello world" → ~3 tokens (11 alpha chars / 4 + punctuation)
        tokens = estimate_tokens("hello world")
        assert 2 <= tokens <= 5

    def test_mixed_text(self):
        tokens = estimate_tokens("今天学了Python编程")
        assert tokens > 0


# ╔══════════════════════════════════════════════════════════════╗
# ║  _is_low_density 测试                                         ║
# ╚══════════════════════════════════════════════════════════════╝

class TestIsLowDensity:
    def test_empty_string(self):
        assert _is_low_density("") is True

    def test_short_string(self):
        assert _is_low_density("短") is True

    def test_greeting_only(self):
        assert _is_low_density("早安") is True
        assert _is_low_density("晚安！") is True
        assert _is_low_density("你好") is True
        assert _is_low_density("签到") is True

    def test_normal_content(self):
        assert _is_low_density("今天和朋友去了公园散步，感觉心情好了很多") is False

    def test_exactly_20_chars(self):
        # 20 字符不应被过滤
        text = "a" * 20
        assert _is_low_density(text) is False

    def test_19_chars(self):
        text = "a" * 19
        assert _is_low_density(text) is True


# ╔══════════════════════════════════════════════════════════════╗
# ║  _generate_summary 测试                                       ║
# ╚══════════════════════════════════════════════════════════════╝

class TestGenerateSummary:
    def test_truncation_at_sentence_boundary(self):
        # 生成超过 200 字符的文本，包含句号
        content = "第一句话内容比较长需要超过八十个字符。" * 15 + "最后一段结尾。"
        assert len(content) > 200
        summary = _generate_summary(content, llm=None)
        assert summary.endswith("...")
        assert len(summary) < len(content)

    def test_truncation_without_sentence_boundary(self):
        # 没有合适的句子边界（连续无标点文本）
        content = "哈" * 250
        summary = _generate_summary(content, llm=None)
        assert summary.endswith("...")
        assert len(summary) <= 184  # 180 + "..."


# ╔══════════════════════════════════════════════════════════════╗
# ║  ContextCompressor.compress 测试                               ║
# ╚══════════════════════════════════════════════════════════════╝

class TestContextCompressor:
    def setup_method(self):
        self.compressor = ContextCompressor(max_tokens=800, llm=None)

    def test_empty_input(self):
        result = self.compressor.compress("", candidates=[], episodic=[])
        assert result == ""

    def test_no_candidates(self):
        result = self.compressor.compress("今天心情不好", candidates=[], episodic=[])
        assert result == ""

    def test_filters_low_density(self):
        """低信息密度条目应被跳过"""
        candidates = [
            {"content": "早安"},  # 低信息密度 — 问候
            {"content": "短"},  # 低信息密度 — 太短
            {"content": "今天和同事讨论了项目进度，感觉项目挺顺利的，大家配合得不错"},  # 正常 (>20字符)
        ]
        result = self.compressor.compress(
            "工作总结和项目复盘，今天要整理一下",
            candidates=candidates,
            episodic=[],
        )
        # 只有第三个条目应被包含
        assert "项目进度" in result
        assert "早安" not in result

    def test_episodic_entries_included(self):
        """Episodic Memory 条目应被优先使用"""
        episodic = [
            {"event": "上周和老板讨论了晋升的事情，感觉比较紧张，不知道结果如何"},
        ]
        candidates = [
            {"content": "今天吃了火锅，味道不错，和朋友聊了很多关于生活的话题"},
        ]
        result = self.compressor.compress(
            "今天又想到了晋升的事情，心里有些忐忑不安",
            candidates=candidates,
            episodic=episodic,
        )
        assert result != ""
        # episodic 条目应出现在结果中
        assert "晋升" in result

    def test_token_limit_respected(self):
        """上下文不应超过 Token 上限"""
        # 创建一个小上限的压缩器
        small_compressor = ContextCompressor(max_tokens=50, llm=None)
        # 很多条候选
        candidates = [
            {"content": f"这是第{i}条日记，内容是关于工作和生活的记录"} for i in range(20)
        ]
        result = small_compressor.compress(
            "今天的日记内容",
            candidates=candidates,
            episodic=[],
        )
        # 结果的 token 数应大致在限制内
        tokens = estimate_tokens(result)
        # 允许一些溢出（因为分隔符 \n---\n 也占 token）
        assert tokens <= 80  # 50 + 一些余量

    def test_long_entries_get_summarized(self):
        """超过 200 字符的条目应被摘要"""
        long_content = "今天参加了一个很长的会议。" * 20  # 远超 200 字符
        candidates = [
            {"content": long_content},
        ]
        result = self.compressor.compress(
            "会议相关",
            candidates=candidates,
            episodic=[],
        )
        # 结果应比原文短很多
        assert len(result) < len(long_content)
        assert "..." in result

    def test_compress_with_dates(self):
        """条目中的日期信息不影响压缩"""
        candidates = [
            {"content": "去公园跑步锻炼身体，跑了五公里感觉很好很畅快", "date": "2025-01-10", "nid": 1},
            {"content": "今天加班到很晚才回家，有点累但总算完成了任务", "date": "2025-01-12", "nid": 2},
        ]
        result = self.compressor.compress(
            "今天也去公园跑步了，坚持锻炼让我感觉不错",
            candidates=candidates,
            episodic=[],
        )
        assert result != ""

    def test_current_content_empty_returns_empty(self):
        """当前日记内容为空时返回空字符串"""
        result = self.compressor.compress(
            "",
            candidates=[{"content": "有内容的日记"}],
            episodic=[],
        )
        assert result == ""
