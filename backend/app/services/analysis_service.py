"""
分析服务层（AnalysisService）
==============================

职责：
- 管理 AI 分析记录的 CRUD 操作
- 协调 AIService 和数据库之间的交互
- 实现智能防重机制（避免重复分析浪费 Token）

核心流程：
┌──────────┐     ┌────────────────┐       ┌───────────┐      ┌──────────┐
│ 路由层    │ ──→ │AnalysisService │ ──→   │AIService  │ ──→ │  LLM API  │
│ (Router) │     │ (本模块)        │       │ (ReAct)   │     │ (DeepSeek)│
└──────────┘     └────────┬───────┘       └───────────┘      └──────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ MySQL        │
                 │ analysis 表  │
                 └──────────────┘

防重机制说明：
- 每次分析时记录日记内容的长度(diary_length)
- 重新分析时，比较当前日记内容长度与上次分析时的长度
- 如果长度相同，进一步比较内容哈希值
- 内容无变化则拒绝重新分析，节省 Token 费用
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.diary import DiaryEntry
from app.services.ai_service import AIService, AIServiceUnavailableError, create_ai_service_for_user

logger = logging.getLogger(__name__)


def _content_hash(content: str) -> str:
    """
    计算日记内容的 MD5 哈希值，用于防重比对。
    为什么用 MD5 而不是 SHA256 ?
    - 这里不是安全场景，只是内容变化检测
    - MD5 足够快且碰撞概率极低
    """
    return hashlib.md5(content.encode("utf-8")).hexdigest()


# ╔══════════════════════════════════════════════════════════════╗
# ║  创建分析（Create）                                           ║
# ╚══════════════════════════════════════════════════════════════╝

def create_analysis(
    db: Session,
    user_id: int,
    nid: int,
) -> Analysis:
    """
    为指定日记创建 AI 分析。

    完整流程：
    1. 验证日记存在且属于当前用户（数据隔离）
    2. 检查是否已有分析记录（避免重复创建）
    3. 读取日记关联的标签（作为 Few-shot 上下文）
    4. 获取用户最近 7 天的日记（作为历史上下文）
    5. 创建 AIService 实例（优先用户配置的模型）
    6. 调用 AI 生成分析
    7. 将分析结果存入 analysis 表
    8. 将 AI 回应同步写入日记的 AI_ans 字段

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param nid: 日记 ID
    :return: 新创建的 Analysis 对象
    :raises ValueError: 日记不存在、不属于当前用户、已有分析
    :raises AIServiceUnavailableError: AI 服务不可用
    """
    # ── Step 1: 验证日记归属 ──
    diary_entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.NID == nid, DiaryEntry.UID == user_id)
        .first()
    )
    if diary_entry is None:
        raise ValueError("日记不存在或无权访问")

    # ── Step 2: 检查是否已有分析 ──
    existing = db.query(Analysis).filter(Analysis.NID == nid).first()
    if existing is not None:
        raise ValueError("该日记已有分析记录，如需重新分析请使用更新接口")

    # ── Step 3: 获取历史日记（最近 7 天，用于上下文） ──
    from sqlalchemy import desc
    from datetime import timedelta

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_entries = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.UID == user_id,  # 严格用户隔离
            DiaryEntry.create_time >= seven_days_ago,
        )
        .order_by(desc(DiaryEntry.create_time))
        .limit(10)
        .all()
    )

    # ── Step 4: 创建 AI 服务并执行分析 ──
    ai_service = create_ai_service_for_user(db, user_id)
    result = ai_service.analyze(
        current_entry=diary_entry,
        recent_entries=recent_entries,
        db=db,
        user_id=user_id,
    )

    # ── Step 5: 存储分析结果 ──
    analysis = Analysis(
        NID=nid,
        Thk_time=datetime.utcnow(),
        Token_cost=result.get("token_cost", 0),
        cache_hit_tokens=result.get("cache_hit_tokens", 0),
        cache_miss_tokens=result.get("cache_miss_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        Thk_log=result.get("thk_log", ""),
        diary_length=len(diary_entry.content or ""),
    )
    db.add(analysis)

    # ── Step 6: 同步更新日记的 AI_ans 字段 ──
    diary_entry.AI_ans = result.get("ai_ans", "")

    db.commit()
    db.refresh(analysis)

    logger.info("分析创建成功: NID=%d, Thk_ID=%d, tokens=%d", nid, analysis.Thk_ID, analysis.Token_cost or 0)
    return analysis


# ╔══════════════════════════════════════════════════════════════╗
# ║  查询分析（Read）                                             ║
# ╚══════════════════════════════════════════════════════════════╝

def get_analysis(db: Session, nid: int) -> Optional[Analysis]:
    """
    获取指定日记的分析结果。

    :param db: 数据库会话
    :param nid: 日记 ID
    :return: Analysis 对象，不存在则返回 None
    """
    return db.query(Analysis).filter(Analysis.NID == nid).first()


def get_analysis_by_id(db: Session, thk_id: int) -> Optional[Analysis]:
    """
    通过分析 ID 获取分析记录。

    :param db: 数据库会话
    :param thk_id: 分析记录 ID
    :return: Analysis 对象，不存在则返回 None
    """
    return db.query(Analysis).filter(Analysis.Thk_ID == thk_id).first()


# ╔══════════════════════════════════════════════════════════════╗
# ║  更新分析 — 智能防重机制（Update）                              ║
# ╚══════════════════════════════════════════════════════════════╝

def update_analysis(
    db: Session,
    user_id: int,
    nid: int,
) -> Analysis:
    """
    重新生成日记分析（智能防重）。

    防重机制工作原理：
    ┌─────────────────────────────────────────────────┐
    │ 1. 获取上次分析时记录的 diary_length               │
    │ 2. 获取当前日记内容的长度                          │
    │ 3. 如果长度相同 → 内容大概率没变 → 拒绝重新分析      │
    │ 4. 如果长度不同 → 内容有变化 → 允许重新分析         │
    └─────────────────────────────────────────────────┘

    为什么用长度而不是哈希？
    - 长度比较是 O(1) 操作，非常快
    - 大多数编辑都会改变长度
    - 如果用户只是修改了几个字（长度不变），也不太需要重新分析

    :param db: 数据库会话
    :param user_id: 当前用户 ID
    :param nid: 日记 ID
    :return: 更新后的 Analysis 对象
    :raises ValueError: 日记不存在、无权访问、无分析记录、内容未变化
    :raises AIServiceUnavailableError: AI 服务不可用
    """
    # ── Step 1: 验证日记归属 ──
    diary_entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.NID == nid, DiaryEntry.UID == user_id)
        .first()
    )
    if diary_entry is None:
        raise ValueError("日记不存在或无权访问")

    # ── Step 2: 获取已有分析记录 ──
    existing = db.query(Analysis).filter(Analysis.NID == nid).first()
    if existing is None:
        raise ValueError("该日记尚无分析记录，请先创建分析")

    # ── Step 3: 防重检查 ──
    current_length = len(diary_entry.content or "")
    if existing.diary_length is not None and existing.diary_length == current_length:
        raise ValueError("日记内容未变化，无需重新分析")

    # ── Step 4: 重新分析 ──
    from sqlalchemy import desc
    from datetime import timedelta

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_entries = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.UID == user_id,
            DiaryEntry.create_time >= seven_days_ago,
        )
        .order_by(desc(DiaryEntry.create_time))
        .limit(10)
        .all()
    )

    ai_service = create_ai_service_for_user(db, user_id)
    result = ai_service.analyze(
        current_entry=diary_entry,
        recent_entries=recent_entries,
        db=db,
        user_id=user_id,
    )

    # ── Step 5: 更新分析记录 ──
    existing.Thk_time = datetime.utcnow()
    existing.Token_cost = result.get("token_cost", 0)
    existing.cache_hit_tokens = result.get("cache_hit_tokens", 0)
    existing.cache_miss_tokens = result.get("cache_miss_tokens", 0)
    existing.output_tokens = result.get("output_tokens", 0)
    existing.Thk_log = result.get("thk_log", "")
    existing.diary_length = current_length

    # 同步更新日记的 AI_ans
    diary_entry.AI_ans = result.get("ai_ans", "")

    db.commit()
    db.refresh(existing)

    logger.info("分析更新成功: NID=%d, Thk_ID=%d", nid, existing.Thk_ID)
    return existing


# ╔══════════════════════════════════════════════════════════════╗
# ║  删除分析（Delete）                                           ║
# ╚══════════════════════════════════════════════════════════════╝

def delete_analysis(db: Session, thk_id: int) -> bool:
    """
    通过分析 ID 删除分析记录。

    注意：删除分析记录不会删除日记本身，
    但会清空日记的 AI_ans 字段。

    :param db: 数据库会话
    :param thk_id: 分析记录 ID
    :return: True 删除成功，False 记录不存在
    """
    analysis = db.query(Analysis).filter(Analysis.Thk_ID == thk_id).first()
    if analysis is None:
        return False

    # 清空关联日记的 AI_ans 字段
    diary_entry = db.query(DiaryEntry).filter(DiaryEntry.NID == analysis.NID).first()
    if diary_entry:
        diary_entry.AI_ans = None

    db.delete(analysis)
    db.commit()

    logger.info("分析删除成功: Thk_ID=%d", thk_id)
    return True


def delete_analysis_by_nid(db: Session, nid: int) -> bool:
    """
    通过日记 ID 删除分析记录。

    :param db: 数据库会话
    :param nid: 日记 ID
    :return: True 删除成功, False 记录不存在
    """
    analysis = db.query(Analysis).filter(Analysis.NID == nid).first()
    if analysis is None:
        return False

    # 清空关联日记的 AI_ans 字段
    diary_entry = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()
    if diary_entry:
        diary_entry.AI_ans = None

    db.delete(analysis)
    db.commit()

    logger.info("分析删除成功(by NID): NID=%d", nid)
    return True
