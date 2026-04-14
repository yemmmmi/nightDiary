# 夜记管理系统

支持多用户的 Web 日记平台，核心功能为 AI 日记分析系统。用户可以记录日记、管理标签、配置个人 LLM 模型，系统通过 ReAct Agent 对日记内容进行深度分析并给出温暖回应。

**技术栈**：Vue 3 + TypeScript + Tailwind CSS / Python + FastAPI / LangChain + Chroma / MySQL

---

## 功能概览

- 用户注册/登录/JWT 认证，数据严格隔离
- 日记 CRUD，支持标签分类、天气自动获取
- AI 分析（ReAct Agent + RAG 语义检索 + 工具调用）
- 用户可配置自己的 LLM 模型（DeepSeek、OpenAI、通义千问等）
- 标签管理（自定义标签、引用计数、颜色）
- 模型管理（API Key 加密存储，任何接口不返回原始 Key）
- 报表打印（日记列表 / 个人信息导出 HTML）
- 在线帮助（新手引导、FAQ、反馈留言）

---

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- （可选）LM Studio 或其他 OpenAI 兼容的 LLM 服务

---

## 快速启动

后端:
       cd backend; .\venv\Scripts\activate; uvicorn app.main:app --reload
前端:
       cd frontend; npm run dev
一步:  
       .\start.ps1
### 1. 后端

```bash
cd backend 

# 创建并激活虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 PyTorch CPU 版本（Windows 用户推荐指定版本，避免 DLL 问题）
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写数据库连接、JWT 密钥、LLM 配置等

# 启动开发服务器（自动创建数据库表）
uvicorn app.main:app --reload
```

后端默认运行在 `http://localhost:8000`，API 文档访问 `http://localhost:8000/docs`。

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 `http://localhost:5173`。

### 3. 数据迁移（可选）

如果 MySQL 中已有日记数据，需要将其导入 Chroma 向量库以启用语义检索：

```bash
cd backend
python -m scripts.migrate_to_chroma
```

首次运行会下载 Embedding 模型（约 400MB），之后会缓存到本地。

---

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── core/           # 数据库、安全、依赖注入
│   │   ├── models/         # SQLAlchemy 数据模型
│   │   ├── routers/        # FastAPI 路由（auth/diary/analysis/tags/models）
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   └── services/       # 业务逻辑层
│   │       ├── ai_service.py        # ReAct Agent（LangChain）
│   │       ├── vector_service.py    # Chroma 向量库（RAG）
│   │       ├── analysis_service.py  # 分析 CRUD + 防重机制
│   │       ├── diary_service.py     # 日记 CRUD + Chroma 同步
│   │       └── ...
│   ├── scripts/            # 迁移脚本
│   ├── chroma_data/        # Chroma 持久化目录（gitignore）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/            # Axios API 封装
│   │   ├── components/     # Vue 组件（DiaryEditor/DiaryList/AIAnalysisPanel）
│   │   ├── pages/          # 页面（Login/Register/Diary/Profile/Tags/Models/Report/Help）
│   │   ├── stores/         # Pinia 状态管理
│   │   ├── router/         # Vue Router + 路由守卫
│   │   └── types/          # TypeScript 类型定义
│   └── package.json
└── Readme.md
```

---

## 环境变量说明（backend/.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | MySQL 连接字符串 | `mysql+pymysql://root:password@localhost:3306/diary_db` |
| `JWT_SECRET_KEY` | JWT 签名密钥，生产环境务必修改 | — |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟） | `1440` |
| `LLM_PROVIDER` | LLM 提供商标识 | `deepseek` |
| `LLM_API_KEY` | LLM API Key | — |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `LLM_BASE_URL` | LLM 接口地址（OpenAI 兼容） | `https://api.deepseek.com` |
| `MODEL_KEY_SECRET` | 用户模型 API Key 的加密密钥（Fernet） | — |
| `WEATHER_API_KEY` | 高德地图 API Key（天气查询） | — |
| `CHROMA_PERSIST_DIR` | Chroma 向量库持久化目录 | `./chroma_data` |
| `EMBEDDING_MODEL` | Embedding 模型名称 | `shibing624/text2vec-base-chinese` |
| `ALLOWED_ORIGINS` | 前端跨域地址（逗号分隔） | `http://localhost:5173,http://localhost:3000` |

---

## AI 分析架构

```
用户触发分析 → 读取日记 + 标签 → 构建 Prompt（标签 Few-shot）
                                        ↓
                                   ReAct Agent
                                   ┌─────────┐
                                   │ 需要工具？│
                                   └────┬────┘
                              Yes ──────┴────── No
                               ↓                 ↓
                        ┌─────────────┐   ┌──────────┐
                        │ search_diary│   │ 直接生成  │
                        │ (Chroma RAG)│   └──────────┘
                        │ get_weather │
                        └──────┬──────┘
                               ↓
                        综合生成 AI 回应
                               ↓
                  存储 AI_ans + Thk_log + Token_cost
```

- Embedding 模型：`shibing624/text2vec-base-chinese`（本地运行，免费）
- 向量数据库：Chroma（持久化存储，按用户隔离 Collection）
- LLM：支持 DeepSeek、OpenAI、通义千问等 OpenAI 兼容接口

---

## API 接口

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/auth/register` | 用户注册 |
| 认证 | POST | `/auth/login` | 用户登录 |
| 认证 | GET | `/auth/me` | 获取当前用户 |
| 认证 | PUT | `/auth/me` | 修改个人信息 |
| 认证 | DELETE | `/auth/me` | 注销账号 |
| 认证 | POST | `/auth/logout` | 退出登录 |
| 日记 | POST | `/diary/entries` | 创建日记 |
| 日记 | GET | `/diary/entries` | 日记列表（分页） |
| 日记 | GET | `/diary/entries/{nid}` | 获取单篇日记 |
| 日记 | PUT | `/diary/entries/{nid}` | 修改日记 |
| 日记 | DELETE | `/diary/entries/{nid}` | 删除日记 |
| 分析 | POST | `/analysis` | 创建 AI 分析 |
| 分析 | GET | `/analysis/{nid}` | 获取分析结果 |
| 分析 | PUT | `/analysis/{nid}` | 重新分析（防重） |
| 分析 | DELETE | `/analysis/{thk_id}` | 删除分析 |
| 标签 | GET | `/tags/` | 标签列表 |
| 标签 | POST | `/tags/` | 创建标签 |
| 标签 | PUT | `/tags/{tid}` | 修改标签 |
| 标签 | DELETE | `/tags/{tid}` | 删除标签 |
| 模型 | GET | `/models/` | 模型列表 |
| 模型 | POST | `/models/` | 注册模型 |
| 模型 | PUT | `/models/{mod_id}` | 修改模型 |
| 模型 | DELETE | `/models/{mod_id}` | 删除模型 |

---

## 运行测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm test
```
