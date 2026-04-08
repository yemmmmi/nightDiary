"""
Model Provider 路由
用户可注册/修改/删除自己的私有 LLM 模型接口
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.model_provider import ModelProvider

router = APIRouter()


# ── Schemas ──────────────────────────────────────

class ModelCreate(BaseModel):
    model_name: str = "未命名"
    model_key: str
    base_url: str


class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    model_key: Optional[str] = None
    base_url: Optional[str] = None


class ModelResponse(BaseModel):
    id: int
    model_name: str
    is_active: bool
    base_url: Optional[str]
    created_at: datetime
    # model_key 不返回，防止泄露

    model_config = {"from_attributes": True}


# ── 路由 ──────────────────────────────────────────

@router.get("/", response_model=list[ModelResponse], summary="获取当前用户的模型列表")
def list_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(ModelProvider).filter(ModelProvider.user_id == current_user.id).all()


@router.post("/", response_model=ModelResponse, status_code=status.HTTP_201_CREATED, summary="注册新模型")
def create_model(
    body: ModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # TODO: model_key 应在此处加密后存储
    model = ModelProvider(
        user_id=current_user.id,
        model_name=body.model_name,
        model_key=body.model_key,
        base_url=body.base_url,
        is_active=False,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.patch("/{model_id}", response_model=ModelResponse, summary="修改模型信息")
def update_model(
    model_id: int,
    body: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = db.query(ModelProvider).filter(
        ModelProvider.id == model_id, ModelProvider.user_id == current_user.id
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    if body.model_name is not None:
        model.model_name = body.model_name
    if body.model_key is not None:
        model.model_key = body.model_key  # TODO: 加密
    if body.base_url is not None:
        model.base_url = body.base_url

    db.commit()
    db.refresh(model)
    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除模型")
def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = db.query(ModelProvider).filter(
        ModelProvider.id == model_id, ModelProvider.user_id == current_user.id
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    db.delete(model)
    db.commit()
