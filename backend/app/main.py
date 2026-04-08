"""
FastAPI 应用入口
配置 CORS、注册路由、启动应用
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 定位 .env：无论从哪个目录启动，都能找到 backend/.env
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# 创建 FastAPI 应用实例
app = FastAPI(
    title="个人网站 AI 日记系统",
    description="支持多用户的个人网站平台，核心功能为 AI 日记系统",
    version="1.0.0",
)

# 配置 CORS（跨域资源共享）
# 允许前端开发服务器（默认 localhost:5173）访问后端接口
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,   # 允许携带 Cookie 和认证头
    allow_methods=["*"],      # 允许所有 HTTP 方法
    allow_headers=["*"],      # 允许所有请求头
)


from app.models import user, diary, analysis, model_provider, tag  # noqa: F401
from app.core.database import Base, engine
from app.routers import auth, diary as diary_router
from app.routers.weather import router as weather_router
from app.routers.tags import router as tags_router
from app.routers.models import router as models_router

# 启动时自动创建数据库表
Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
    """根路径健康检查接口"""
    return {"message": "个人网站 AI 日记系统 API 运行正常", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """健康检查接口，用于监控服务状态"""
    return {"status": "healthy"}


# 注册认证路由
app.include_router(auth.router, prefix="/auth", tags=["认证"])
# 注册日记路由
app.include_router(diary_router.router, prefix="/diary", tags=["日记"])
# 注册天气路由
app.include_router(weather_router, prefix="/weather", tags=["天气"])
# 注册标签路由
app.include_router(tags_router, prefix="/tags", tags=["标签"])
# 注册模型路由
app.include_router(models_router, prefix="/models", tags=["模型管理"])
