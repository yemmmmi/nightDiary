"""
管理员路由模块
提供用户管理、日记管理、分析数据管理等管理后台 API。
仅 role='admin' 的用户可访问。
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.models.analysis import Analysis

router = APIRouter()


# ═══════════════════════════════════════════════════
# 统计概览
# ═══════════════════════════════════════════════════

@router.get("/stats", summary="管理后台统计概览")
def get_admin_stats(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    total_users = db.query(func.count(User.UID)).scalar() or 0
    total_diaries = db.query(func.count(DiaryEntry.NID)).scalar() or 0
    total_analyses = db.query(func.count(Analysis.Thk_ID)).scalar() or 0
    public_diaries = db.query(func.count(DiaryEntry.NID)).filter(DiaryEntry.is_open == True).scalar() or 0
    total_tokens = db.query(func.sum(Analysis.Token_cost)).scalar() or 0

    return {
        "total_users": total_users,
        "total_diaries": total_diaries,
        "total_analyses": total_analyses,
        "public_diaries": public_diaries,
        "total_tokens_consumed": total_tokens,
    }


# ═══════════════════════════════════════════════════
# 用户管理
# ═══════════════════════════════════════════════════

@router.get("/users", summary="获取用户列表")
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="按用户名搜索"),
    sort_by: Optional[str] = Query(None, description="排序字段: diary_count, create_time, age"),
    sort_order: str = Query("desc", description="排序方向: asc 或 desc"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if search:
        query = query.filter(User.user_name.like(f"%{search}%"))
    total = query.count()

    # 排序
    if sort_by == "create_time":
        order_col = User.create_time.desc() if sort_order == "desc" else User.create_time.asc()
        query = query.order_by(order_col)
    elif sort_by == "age":
        order_col = User.age.desc() if sort_order == "desc" else User.age.asc()
        query = query.order_by(order_col)
    elif sort_by == "diary_count":
        # 子查询排序
        from sqlalchemy import select
        diary_count_sub = (
            db.query(func.count(DiaryEntry.NID))
            .filter(DiaryEntry.UID == User.UID)
            .correlate(User)
            .scalar_subquery()
        )
        if sort_order == "desc":
            query = query.order_by(diary_count_sub.desc())
        else:
            query = query.order_by(diary_count_sub.asc())
    else:
        query = query.order_by(User.UID.desc())

    users = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "UID": u.UID,
                "user_name": u.user_name,
                "email": u.email,
                "role": u.role,
                "gender": u.gender,
                "age": u.age,
                "address": u.address,
                "create_time": u.create_time.isoformat() if u.create_time else None,
                "diary_count": db.query(func.count(DiaryEntry.NID)).filter(DiaryEntry.UID == u.UID).scalar() or 0,
            }
            for u in users
        ],
    }


@router.delete("/users/{uid}", summary="删除用户", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    uid: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.UID == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能删除管理员账号")
    db.delete(user)
    db.commit()


@router.put("/users/{uid}/role", summary="修改用户角色")
def update_user_role(
    uid: int,
    role: str = Query(..., description="新角色: user 或 admin"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="角色只能是 user 或 admin")
    user = db.query(User).filter(User.UID == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.role = role
    db.commit()
    return {"UID": user.UID, "user_name": user.user_name, "role": user.role}


# ═══════════════════════════════════════════════════
# 日记管理（仅公开日记）
# ═══════════════════════════════════════════════════

@router.get("/diaries", summary="获取公开日记列表")
def list_diaries(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None, description="按用户 ID 过滤"),
    sort_by: Optional[str] = Query(None, description="排序字段: create_time, content_length"),
    sort_order: str = Query("desc", description="排序方向: asc 或 desc"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(DiaryEntry).filter(DiaryEntry.is_open == True)
    if user_id:
        query = query.filter(DiaryEntry.UID == user_id)
    total = query.count()

    # 排序
    if sort_by == "content_length":
        from sqlalchemy import func as sa_func
        order_expr = sa_func.length(DiaryEntry.content)
        query = query.order_by(order_expr.desc() if sort_order == "desc" else order_expr.asc())
    elif sort_by == "create_time":
        query = query.order_by(DiaryEntry.create_time.desc() if sort_order == "desc" else DiaryEntry.create_time.asc())
    else:
        query = query.order_by(DiaryEntry.create_time.desc())

    entries = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "NID": e.NID,
                "UID": e.UID,
                "user_name": e.user.user_name if e.user else None,
                "content": e.content[:200] if e.content else "",
                "content_length": len(e.content) if e.content else 0,
                "is_open": e.is_open,
                "weather": e.weather,
                "AI_ans": e.AI_ans[:100] if e.AI_ans else None,
                "create_time": e.create_time.isoformat() if e.create_time else None,
            }
            for e in entries
        ],
    }


@router.get("/diaries/{nid}", summary="获取日记详情")
def get_diary_detail(
    nid: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    entry = db.query(DiaryEntry).filter(DiaryEntry.NID == nid, DiaryEntry.is_open == True).first()
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在或非公开")
    return {
        "NID": entry.NID,
        "UID": entry.UID,
        "user_name": entry.user.user_name if entry.user else None,
        "content": entry.content,
        "is_open": entry.is_open,
        "weather": entry.weather,
        "AI_ans": entry.AI_ans,
        "create_time": entry.create_time.isoformat() if entry.create_time else None,
    }


@router.delete("/diaries/{nid}", summary="删除日记", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary(
    nid: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    entry = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")
    db.delete(entry)
    db.commit()


# ═══════════════════════════════════════════════════
# 分析数据管理
# ═══════════════════════════════════════════════════

@router.get("/analyses", summary="获取分析记录列表")
def list_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None, description="按用户 ID 过滤"),
    sort_by: Optional[str] = Query(None, description="排序字段: Token_cost, cache_hit_tokens, output_tokens, Thk_time"),
    sort_order: str = Query("desc", description="排序方向: asc 或 desc"),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(Analysis).join(DiaryEntry, Analysis.NID == DiaryEntry.NID)
    if user_id:
        query = query.filter(DiaryEntry.UID == user_id)
    total = query.count()

    # 排序
    sort_map = {
        "Token_cost": Analysis.Token_cost,
        "cache_hit_tokens": Analysis.cache_hit_tokens,
        "output_tokens": Analysis.output_tokens,
        "cache_miss_tokens": Analysis.cache_miss_tokens,
        "Thk_time": Analysis.Thk_time,
        "diary_length": Analysis.diary_length,
    }
    if sort_by and sort_by in sort_map:
        col = sort_map[sort_by]
        query = query.order_by(col.desc() if sort_order == "desc" else col.asc())
    else:
        query = query.order_by(Analysis.Thk_time.desc())

    analyses = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "Thk_ID": a.Thk_ID,
                "NID": a.NID,
                "Token_cost": a.Token_cost,
                "cache_hit_tokens": a.cache_hit_tokens,
                "cache_miss_tokens": a.cache_miss_tokens,
                "output_tokens": a.output_tokens,
                "agent_mode": a.agent_mode,
                "Thk_time": a.Thk_time.isoformat() if a.Thk_time else None,
                "diary_length": a.diary_length,
            }
            for a in analyses
        ],
    }


@router.delete("/analyses/{thk_id}", summary="删除分析记录", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    thk_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    analysis = db.query(Analysis).filter(Analysis.Thk_ID == thk_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    db.delete(analysis)
    db.commit()


# ═══════════════════════════════════════════════════
# 标签审核
# ═══════════════════════════════════════════════════

@router.get("/tags/pending", summary="获取待审核标签列表")
def list_pending_tags(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.models.tag import Tag
    tags = db.query(Tag).filter(Tag.status == "pending").order_by(Tag.create_time.desc()).all()
    return [
        {
            "id": t.id,
            "tag_name": t.tag_name,
            "color": t.color,
            "creator": t.creator,
            "create_time": t.create_time.isoformat() if t.create_time else None,
        }
        for t in tags
    ]


@router.put("/tags/{tag_id}/approve", summary="审核通过标签")
def approve_tag(
    tag_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.services.tag_service import approve_tag as do_approve
    tag = do_approve(db, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    return {"id": tag.id, "tag_name": tag.tag_name, "status": tag.status}


@router.delete("/tags/{tag_id}/reject", summary="拒绝标签", status_code=status.HTTP_204_NO_CONTENT)
def reject_tag(
    tag_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.services.tag_service import reject_tag as do_reject
    if not do_reject(db, tag_id):
        raise HTTPException(status_code=404, detail="标签不存在")
