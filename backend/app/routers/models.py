"""
模型管理路由
GET/POST/PUT/DELETE /models
model_key 加密存储，任何响应均不返回原始 key
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.model_provider import ModelCreate, ModelUpdate, ModelResponse
from app.services import model_service

router = APIRouter()


@router.get("/", response_model=list[ModelResponse], summary="获取当前用户的模型列表")
def list_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return model_service.get_models(db, user_id=current_user.UID)


@router.post("/", response_model=ModelResponse, status_code=status.HTTP_201_CREATED, summary="注册新模型")
def create_model(
    body: ModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return model_service.create_model(
        db=db,
        user_id=current_user.UID,
        model_name=body.model_name,
        model_key=body.model_key,
        base_url=body.base_url,
    )


@router.put("/{model_id}", response_model=ModelResponse, summary="修改模型信息")
def update_model(
    model_id: int,
    body: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = model_service.update_model(
        db=db,
        user_id=current_user.UID,
        model_id=model_id,
        model_name=body.model_name,
        model_key=body.model_key,
        base_url=body.base_url,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型不存在")
    return updated


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除模型")
def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = model_service.delete_model(db=db, user_id=current_user.UID, model_id=model_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型不存在")
