"""
分析路由模块（Analysis Router）
================================

提供 AI 日记分析的 RESTful API 接口。
所有接口均需 JWT 认证，通过 get_current_user 依赖注入获取当前用户。

接口列表：
- POST   /analysis          — 为指定日记创建 AI 分析
- GET    /analysis/{nid}    — 获取指定日记的分析结果
- PUT    /analysis/{nid}    — 重新生成分析（智能防重）
- DELETE /analysis/{thk_id} — 删除分析记录

错误码约定：
- 400: 业务逻辑错误（已有分析、内容未变化等）
- 401: 未认证
- 403: 无权访问（跨用户操作）
- 404: 资源不存在
- 503: AI 服务不可用（LLM 连接失败等）
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisResponse, AnalysisUpdate
from app.services import analysis_service
from app.services.ai_service import AIServiceUnavailableError

router = APIRouter()


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建 AI 分析",
    description="为指定日记创建 AI 分析。系统会读取日记内容和标签，调用 LLM 生成分析回应。",
)
def create_analysis(
    body: AnalysisCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    创建分析的完整流程：
    1. 前端传入日记 NID
    2. 后端验证日记归属（用户隔离）
    3. 检查是否已有分析（避免重复）
    4. 调用 AIService 生成分析
    5. 存储结果并返回
    """
    try:
        analysis = analysis_service.create_analysis(
            db=db,
            user_id=current_user.UID,
            nid=body.nid,
        )
        return analysis
    except ValueError as exc:
        # 业务逻辑错误：日记不存在、已有分析等
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AIServiceUnavailableError as exc:
        # AI 服务不可用：LLM 连接失败、API Key 无效等
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI 服务暂时不可用，请稍后重试: {str(exc)}",
        ) from exc


@router.get(
    "/{nid}",
    response_model=AnalysisResponse,
    summary="获取分析结果",
    description="获取指定日记的 AI 分析结果。需要验证日记归属。",
)
def get_analysis(
    nid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取分析结果前，先验证日记是否属于当前用户。
    这确保了用户 A 无法查看用户 B 的日记分析（数据隔离）。
    """
    # 验证日记归属
    from app.models.diary import DiaryEntry
    diary_entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.NID == nid, DiaryEntry.UID == current_user.UID)
        .first()
    )
    if diary_entry is None:
        # 检查日记是否存在但不属于当前用户
        entry_any = db.query(DiaryEntry).filter(DiaryEntry.NID == nid).first()
        if entry_any is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该资源",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="日记不存在",
        )

    # 查询分析记录
    analysis = analysis_service.get_analysis(db=db, nid=nid)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该日记尚无分析记录",
        )
    return analysis


@router.put(
    "/{nid}",
    response_model=AnalysisResponse,
    summary="重新生成分析（智能防重）",
    description="重新生成指定日记的 AI 分析。如果日记内容未变化，将拒绝重新分析以节省 Token。",
)
def update_analysis(
    nid: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    智能防重机制：
    - 比较当前日记内容长度与上次分析时的长度
    - 长度相同 → 内容大概率没变 → 返回 400 拒绝
    - 长度不同 → 内容有变化 → 重新调用 AI 分析
    """
    try:
        analysis = analysis_service.update_analysis(
            db=db,
            user_id=current_user.UID,
            nid=nid,
        )
        return analysis
    except ValueError as exc:
        error_msg = str(exc)
        # 区分不同的错误类型
        if "未变化" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="日记内容未变化，无需重新分析",
            ) from exc
        elif "无权" in error_msg or "不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            ) from exc
    except AIServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI 服务暂时不可用，请稍后重试: {str(exc)}",
        ) from exc


@router.delete(
    "/{thk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除分析记录",
    description="通过分析 ID 删除分析记录。同时清空关联日记的 AI 回应字段。",
)
def delete_analysis(
    thk_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    删除分析记录。
    注意：这里需要验证分析记录关联的日记是否属于当前用户，
    防止用户 A 删除用户 B 的分析记录。
    """
    # 先获取分析记录
    analysis = analysis_service.get_analysis_by_id(db=db, thk_id=thk_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析记录不存在",
        )

    # 验证关联日记的归属
    from app.models.diary import DiaryEntry
    diary_entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.NID == analysis.NID, DiaryEntry.UID == current_user.UID)
        .first()
    )
    if diary_entry is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源",
        )

    deleted = analysis_service.delete_analysis(db=db, thk_id=thk_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析记录不存在",
        )
