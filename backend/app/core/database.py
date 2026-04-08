"""
数据库连接配置模块
使用 SQLAlchemy 连接 MySQL 数据库
连接字符串从环境变量 DATABASE_URL 读取
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量读取数据库连接字符串
# MySQL 格式：mysql+pymysql://user:password@host:port/dbname
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:password@localhost:3306/diary_db"
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    echo=False,  # 生产环境关闭 SQL 日志，调试时可设为 True
    pool_pre_ping=True,  # 自动检测断开的连接并重连
    pool_recycle=3600,   # 每小时回收连接，避免 MySQL 8 小时超时断开
)

# 创建会话工厂
# autocommit=False：手动提交事务
# autoflush=False：手动刷新，避免意外的自动写入
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类
    所有数据模型都应继承此类
    """
    pass


def get_db():
    """
    FastAPI 依赖注入函数，提供数据库会话
    使用 yield 确保请求结束后自动关闭会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
