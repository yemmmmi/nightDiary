"""
日记路由模块
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.diary import DiaryEntry
from app.schemas.diary import DiaryEntryCreate, DiaryEntryResponse, DiaryUpdate
from app.services import diary_service
from app.services.weather_service import get_weather

router = APIRouter()


@router.post("/entries", response_model=DiaryEntryResponse, status_code=status.HTTP_201_CREATED, summary="创建日记")
async def create_entry(
    body: DiaryEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    weather = await get_weather(current_user.address or "", user_id=current_user.UID)
    try:
        entry = diary_service.create_entry(
            db=db, uid=current_user.UID, content=body.content,
            is_open=body.is_public if hasattr(body, 'is_public') else False, weather=weather,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return entry


@router.get("/entries", response_model=list[DiaryEntryResponse], summary="日记列表")
def list_entries(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return diary_service.get_entries(db=db, uid=current_user.UID, skip=skip, limit=limit)


@router.get("/entries/{nid}", response_model=DiaryEntryResponse, summary="获取单篇日记")
def get_entry(
    nid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = diary_service.get_entry(db=db, uid=current_user.UID, nid=nid)
    if entry is None:
        # 检查是否存在但不属于当前用户
        entry_any = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()
        if entry_any:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资源")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日记条目不存在")
    return entry


@router.put("/entries/{nid}", response_model=DiaryEntryResponse, summary="修改日记")
def update_entry(
    nid: int, body: DiaryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = diary_service.get_entry(db=db, uid=current_user.UID, nid=nid)
    if existing is None:
        entry_any = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()
        if entry_any:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该资源")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日记条目不存在")

    try:
        updated = diary_service.update_entry(
            db=db, uid=current_user.UID, nid=nid,
            content=body.content, is_open=body.is_open, tag_ids=body.tag_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return updated


@router.delete("/entries/{nid}", status_code=status.HTTP_204_NO_CONTENT, summary="删除日记")
def delete_entry(
    nid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = diary_service.delete_entry(db=db, uid=current_user.UID, nid=nid)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日记条目不存在")
