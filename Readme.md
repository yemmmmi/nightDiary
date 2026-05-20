# 夜记 — AI 心理陪伴日记系统

支持多用户的 Web 日记平台，核心功能为基于 LangGraph Multi-Agent 架构的 AI 日记分析系统。系统通过 Supervisor + Worker Agents 协调模式，对日记内容进行意图识别、情感共鸣、历史检索和洞察分析，并通过 Thompson Sampling 强化学习持续优化回应风格。

**技术栈**：Vue 3 + TypeScript + Tailwind CSS + Chart.js / Python + FastAPI + LangGraph + LangChain / ChromaDB + Redis + MySQL

---

## 功能概览

### 核心 AI 能力
- **Multi-Agent 协调**：Supervisor Agent 意图分类 → Worker Agents 并行执行 → 结果整合
- **四种意图识别**：纯记录、情感支持、回顾复盘、习惯追踪
- **三层记忆系统**：Episodic Memory (Redis) + Long-Term Memory (MySQL) + Working Memory (LangGraph State)
- **RAG 增强检索**：Chroma + BM25 + RRF + bge-reranker-base 混合检索管线
- **强化学习反馈**：Thompson Sampling 动态优化回应风格（共情/务实/哲思/幽默）
- **危机响应**：极端负面情绪自动检测，提供心理援助热线
- **领域知识库**：85 条精选心理学知识（CBT、正念、睡眠卫生、社会支持、情绪调节）

### 用户功能
- 用户注册/登录/JWT 认证，数据严格隔离
- 日记 CRUD，支持标签分类、天气自动获取、公开专栏
- AI 分析回应 + 点赞/点踩反馈 + 隐式行为信号采集
- Token 消费仪表盘（折线图 + 饼图 + 30 秒自动刷新）
- 用户可配置自己的 LLM 模型（DeepSeek、OpenAI、通义千问等）
- 标签管理、模型管理、报表打印、在线帮助

---

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 6.0+（Episodic Memory，可选，不可用时自动降级）
- （可选）LM Studio 或其他 OpenAI 兼容的 LLM 服务

---

## 快速启动

```powershell
./start.ps1
```

### 1. 后端

```bash
cd backend

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 PyTorch CPU 版本
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写数据库连接、JWT 密钥、LLM 配置等

# 初始化心理学领域知识库（首次运行）
python -m scripts.init_domain_knowledge

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

```bash
cd backend
# 将 MySQL 日记数据导入 Chroma 向量库
python -m scripts.migrate_to_chroma

# 初始化心理学领域知识库（85 条精选知识）
python -m scripts.init_domain_knowledge
```

---

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── agents/         # Multi-Agent 协调层
│   │   │   ├── state.py              # MultiAgentState TypedDict
│   │   │   ├── graph.py              # LangGraph StateGraph 构建器
│   │   │   ├── supervisor.py         # Supervisor Agent（意图分类 + 结果整合）
│   │   │   ├── empathy_agent.py      # Empathy Worker（情感共鸣 + 危机响应）
│   │   │   ├── retrieval_agent.py    # Retrieval Worker（RAG 多跳检索）
│   │   │   ├── insight_agent.py      # Insight Worker（模式分析 + 周报/月报）
│   │   │   ├── intent_classifier.py  # 两级意图分类器（规则层 + LLM 层）
│   │   │   ├── context_compressor.py # 智能上下文压缩
│   │   │   └── parent_child_chunker.py # 父子文档切分
│   │   ├── memory/         # 三层记忆系统
│   │   │   ├── episodic.py           # Episodic Memory（Redis Sorted Set）
│   │   │   ├── long_term.py          # Long-Term Memory（MySQL JSON）
│   │   │   └── working.py            # Working Memory（LangGraph State）
│   │   ├── skills/         # Skill 架构（10 个 Skills）
│   │   │   ├── base.py               # BaseSkill 抽象类
│   │   │   ├── registry.py           # SkillRegistry（贪心选择 + Token 预算）
│   │   │   ├── pattern_detector.py   # 情绪/行为模式检测
│   │   │   ├── habit_tracker.py      # 习惯追踪
│   │   │   ├── crisis_detector.py    # 危机情绪检测
│   │   │   ├── memory_reader.py      # Episodic Memory 读取
│   │   │   ├── memory_writer.py      # Episodic Memory 写入
│   │   │   ├── summary_generator.py  # 周报/月报生成
│   │   │   └── ...                   # search_diary, weather, sentiment, address
│   │   ├── feedback/       # 强化学习反馈闭环
│   │   │   ├── thompson_sampling.py  # Thompson Sampling（Beta 分布）
│   │   │   └── prompt_tuner.py       # 动态 Prompt 构建器
│   │   ├── knowledge/      # 知识抽取与领域知识库
│   │   │   ├── extractor.py          # 结构化知识抽取（人物/事件/地点/话题）
│   │   │   └── domain_store.py       # Domain Knowledge Store（Chroma 共享集合）
│   │   ├── core/           # 数据库、安全、Redis、分布式锁
│   │   ├── models/         # SQLAlchemy 数据模型
│   │   ├── routers/        # FastAPI 路由
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   └── services/       # 业务逻辑层
│   ├── scripts/            # 迁移脚本、领域知识初始化
│   ├── tests/              # 319 个后端测试
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/            # Axios API 封装（含 tokenStats, feedback）
│   │   ├── components/     # Vue 组件
│   │   │   ├── FeedbackButtons.vue      # 点赞/点踩 + 原因选择
│   │   │   ├── AIAnalysisPanel.vue      # AI 分析面板 + 隐式反馈集成
│   │   │   ├── DiaryEditor.vue          # 日记编辑器
│   │   │   └── ...
│   │   ├── composables/    # Vue Composables
│   │   │   └── useImplicitFeedback.ts   # 隐式反馈信号采集
│   │   ├── pages/          # 页面组件
│   │   │   ├── TokenDashboardPage.vue   # Token 仪表盘（Chart.js）
│   │   │   └── ...
│   │   ├── stores/         # Pinia 状态管理
│   │   ├── router/         # Vue Router + 路由守卫
│   │   ├── test/           # 32 个前端测试
│   │   └── types/          # TypeScript 类型定义
│   └── package.json
└── Readme.md
```

---

## 环境变量说明（backend/.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | MySQL 连接字符串 | `mysql+pymysql://root:password@localhost:3306/diary_db` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | — |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟） | `1440` |
| `LLM_API_KEY` | LLM API Key | — |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `LLM_BASE_URL` | LLM 接口地址（OpenAI 兼容） | `https://api.deepseek.com` |
| `MULTI_AGENT_ENABLED` | Multi-Agent 功能开关 | `true` |
| `REDIS_URL` | Redis 连接地址（Episodic Memory） | `redis://localhost:6379/0` |
| `CHROMA_PERSIST_DIR` | Chroma 向量库持久化目录 | `./chroma_data` |
| `EMBEDDING_MODEL` | Embedding 模型名称 | `shibing624/text2vec-base-chinese` |
| `MODEL_KEY_SECRET` | 用户模型 API Key 加密密钥（Fernet） | — |
| `WEATHER_API_KEY` | 高德地图 API Key | — |
| `ALLOWED_ORIGINS` | 前端跨域地址 | `http://localhost:5173,http://localhost:3000` |

---

## AI 分析架构

```
用户写日记 → 触发 AI 分析 → AIService.analyze()
                                    │
                          ┌─────────┴─────────┐
                          │   路由决策          │
                          │ Multi-Agent > Agent │
                          │ > Chain > Fallback  │
                          └─────────┬─────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │ Multi-Agent │ │ ReAct Agent │ │   Chain     │
            │ (LangGraph) │ │ (工具调用)   │ │ (直接生成)  │
            └──────┬──────┘ └─────────────┘ └─────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌────────┐
│Empathy │  │Retrieval │  │Insight │
│ Agent  │  │  Agent   │  │ Agent  │
└────┬───┘  └────┬─────┘  └───┬────┘
     │           │             │
     ▼           ▼             ▼
┌──────────────────────────────────┐
│   Supervisor synthesize()         │
│   整合 Worker 输出为统一回应       │
└──────────────────────────────────┘
```

---

## API 接口

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/auth/register` | 用户注册 |
| 认证 | POST | `/auth/login` | 用户登录 |
| 认证 | GET | `/auth/me` | 获取当前用户 |
| 认证 | PUT | `/auth/me` | 修改个人信息 |
| 日记 | POST | `/diary/entries` | 创建日记 |
| 日记 | GET | `/diary/entries` | 日记列表（分页） |
| 日记 | GET | `/diary/entries/{nid}` | 获取单篇日记 |
| 日记 | PUT | `/diary/entries/{nid}` | 修改日记 |
| 日记 | DELETE | `/diary/entries/{nid}` | 删除日记 |
| 分析 | POST | `/analysis` | 创建 AI 分析 |
| 分析 | GET | `/analysis/{nid}` | 获取分析结果 |
| 分析 | PUT | `/analysis/{nid}` | 重新分析 |
| Token 统计 | GET | `/api/analysis/stats` | 聚合 Token 统计 |
| Token 统计 | GET | `/api/analysis/history` | 分页分析历史 |
| 反馈 | POST | `/api/feedback` | 显式反馈（点赞/点踩） |
| 反馈 | POST | `/api/feedback/implicit` | 隐式反馈信号 |
| 标签 | GET/POST/PUT/DELETE | `/tags/` | 标签 CRUD |
| 模型 | GET/POST/PUT/DELETE | `/models/` | 模型管理 |
| 天气 | GET | `/weather/` | 天气查询 |
| 专栏 | GET | `/public/column/` | 公开日记专栏 |

---

## 运行测试

```bash
# 后端测试（319 个测试）
cd backend
venv\Scripts\python.exe -m pytest tests/ -v

# 前端测试（32 个测试）
cd frontend
npx vitest --run
```

---

## 降级策略

系统在任何组件故障时保持可用：

| 组件故障 | 降级行为 |
|----------|----------|
| LangGraph 未安装 | 回退到 ReAct Agent 模式 |
| Multi-Agent 执行失败 | 回退到 Agent/Chain 模式 |
| Redis 不可用 | 跳过 Episodic Memory，不影响核心分析 |
| LLM API 超时 | 返回 FALLBACK_FEEDBACK 兜底文本 |
| Domain Knowledge Store 不存在 | 跳过领域知识查询 |
| Thompson Sampling 参数加载失败 | 使用默认偏好（共情型） |
| 单个 Worker Agent 失败 | 使用其余成功 Agent 的输出生成回应 |
