"""
标签路由
GET/POST/PUT/DELETE /tags
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.tag import TagCreate, TagUpdate, TagResponse
from app.services import tag_service

router = APIRouter()


@router.get("/", response_model=list[TagResponse], summary="获取标签列表")
def list_tags(
    sort_by_usage: bool = True,
    db: Session = Depends(get_db),
):
    """返回所有标签，默认按引用次数倒序"""
    return tag_service.get_tags(db, sort_by_usage=sort_by_usage)


@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED, summary="创建标签")
def create_tag(
    body: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return tag_service.create_tag(
            db=db,
            tag_name=body.tag_name,
            color=body.color or "#6B7280",
            creator=current_user.user_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/{tag_id}", response_model=TagResponse, summary="修改标签")
def update_tag(
    tag_id: int,
    body: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tag = tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    if tag.creator != current_user.user_name and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该标签")

    try:
        updated = tag_service.update_tag(db, tag_id, tag_name=body.tag_name, color=body.color)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return updated


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除标签")
def delete_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tag = tag_service.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    if tag.creator != current_user.user_name and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该标签")

    tag_service.delete_tag(db, tag_id)
