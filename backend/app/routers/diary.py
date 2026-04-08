"""
日记路由模块
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.diary import DiaryEntryCreate, DiaryEntryResponse
from app.services import diary_service
from app.services.ai_service import AIService, AIServiceUnavailableError
from app.services.weather_service import get_weather

_ai_service: AIService | None = None

router = APIRouter()


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        try:
            _ai_service = AIService()
        except Exception as exc:
            raise AIServiceUnavailableError(f"AI 服务初始化失败: {str(exc)}")
    return _ai_service


@router.post(
    "/entries",
    response_model=DiaryEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建日记条目（自动写入天气）",
)
async def create_entry(
    body: DiaryEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 自动抓取用户当地天气
    weather = await get_weather(current_user.address or "")

    try:
        entry = diary_service.create_entry(
            db=db,
            user_id=current_user.id,
            content=body.content,
            mood=body.mood,
            is_public=body.is_public,
            weather=weather,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return entry


@router.get(
    "/entries",
    response_model=list[DiaryEntryResponse],
    summary="获取日记列表（分页）",
)
def list_entries(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return diary_service.get_entries(db=db, user_id=current_user.id, skip=skip, limit=limit)


@router.get(
    "/entries/{entry_id}",
    response_model=DiaryEntryResponse,
    summary="获取单篇日记",
)
def get_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = diary_service.get_entry(db=db, user_id=current_user.id, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日记条目不存在")
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除日记条目")
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = diary_service.delete_entry(db=db, user_id=current_user.id, entry_id=entry_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日记条目不存在")


@router.post("/analyze", status_code=status.HTTP_200_OK, summary="获取 AI 日记分析")
def analyze_diary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recent_entries = diary_service.get_recent_7days(db=db, user_id=current_user.id)

    if not recent_entries:
        return {"analysis": "你还没有写过日记，快去记录今天的故事吧！"}

    current_entry = recent_entries[0]

    try:
        ai_service = get_ai_service()
        analysis = ai_service.analyze(current_entry=current_entry, recent_entries=recent_entries)
    except AIServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {"analysis": analysis}
