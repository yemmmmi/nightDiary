# 个人网站 AI 日记系统

支持多用户的个人网站平台，核心功能为 AI 日记系统。用户可撰写日记，系统调用 LLM 分析最近一周记录并给出积极评价。

**技术栈**：React + Tailwind CSS / Python + FastAPI / LangChain / SQLite

---

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- （可选）LM Studio 或其他 OpenAI 兼容的本地/云端 LLM 服务

---

## 快速启动

### 1. 后端

**首次安装：**

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 按需编辑 .env，填写 JWT_SECRET_KEY 和 LLM 相关配置
```

**日常启动：**

```bash
cd backend

# 先激活虚拟环境
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 启动开发服务器（自动创建 diary.db）
uvicorn app.main:app --reload
```

后端默认运行在 `http://localhost:800

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认运行在 `http://localhost:5173`。

---

## 环境变量说明（backend/.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | MySQL 连接字符串 | `mysql+pymysql://root:password@localhost:3306/diary_db` |
| `JWT_SECRET_KEY` | JWT 签名密钥，生产环境务必修改 | — |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟） | `1440` |
| `LLM_PROVIDER` | LLM 提供商标识 | `lmstudio` |
| `LLM_API_KEY` | LLM API Key | `lm-studio` |
| `LLM_MODEL` | 模型名称 | `local-model` |
| `LLM_BASE_URL` | LLM 接口地址（OpenAI 兼容） | `http://localhost:1234/v1` |
| `ALLOWED_ORIGINS` | 前端跨域地址（逗号分隔） | `http://localhost:5173` |

---

## LLM 配置说明

系统使用 OpenAI 兼容接口，支持以下方式：

- **LM Studio（本地）**：启动 LM Studio 并加载模型，默认地址 `http://localhost:1234/v1`
- **DeepSeek**：`LLM_BASE_URL=https://api.deepseek.com/v1`，填入对应 API Key 和模型名
- **通义千问**：`LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`

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
