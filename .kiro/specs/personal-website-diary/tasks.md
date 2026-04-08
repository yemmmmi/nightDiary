# 实施计划：夜记管理系统
# venv\Scripts\activate | uvicorn app.main:app --reload

## 概述

按照"先用户系统，再日记功能，再标签/模型，最后 AI 分析"的顺序实施。首先搭建项目骨架和数据库，然后实现用户注册/登录/JWT 认证，接着实现带用户隔离的日记 CRUD，再实现标签和模型管理，最后集成 ReAct Agent AI 分析功能。

---

## 任务列表

- [x] 1. 搭建项目骨架与数据库配置
  - 初始化后端目录结构：`backend/app/{routers,models,services,core}/`
  - 初始化前端：Vue 3 + TypeScript + Vite + Tailwind CSS
  - 配置 MySQL 连接（SQLAlchemy），读取环境变量 `DATABASE_URL`
  - 创建 `users`、`diary`、`analysis`、`tags`、`diary_tags`、`model_provider` 表
  - 创建 `.env.example` 文件，包含 `DATABASE_URL`、`JWT_SECRET_KEY`、`LLM_PROVIDER`、`LLM_API_KEY`
  - _需求：1.1, 1.2_

- [x] 2. 实现用户模型与认证核心
  - [x] 2.1 实现 User SQLAlchemy 模型和 Pydantic schema（UserCreate、UserUpdate、UserResponse、TokenResponse）
    - 字段：uid、user_name、email、password_hash、gender、age、phone、address、role、create_time、last_time
    - 密码使用 `passlib[bcrypt]` 哈希存储
    - _需求：2.1, 2.10_

  - [ ]* 2.2 为用户模型编写属性测试
    - **属性 1：用户注册唯一性**
    - **Validates: Requirements 2.1, 2.2**
    - `# Feature: personal-website-diary, Property 1: 用户注册唯一性`

  - [x] 2.3 实现 JWT 工具函数（生成 token、验证 token、`get_current_user` 依赖）
    - JWT Payload 包含 uid、user_name、role，token 过期时间可配置
    - _需求：2.3, 2.5, 2.6_

  - [ ]* 2.4 为 JWT 认证编写属性测试
    - **属性 2：JWT 认证保护**
    - **Validates: Requirements 2.5, 2.6**
    - `# Feature: personal-website-diary, Property 2: JWT认证保护`

- [x] 3. 实现认证路由（注册/登录/退出/修改/删除）
  - [x] 3.1 实现 `POST /auth/register` 路由
    - 检查用户名和邮箱唯一性，哈希密码，写入数据库，返回 UserResponse
    - _需求：2.1, 2.2_

  - [x] 3.2 实现 `POST /auth/login` 路由
    - 验证用户名/邮箱和密码，返回 JWT access_token
    - _需求：2.3, 2.4_

  - [x] 3.3 实现 `GET /auth/me` 路由（需认证）
    - 返回当前登录用户信息
    - _需求：2.5_

  - [ ] 3.4 实现 `PUT /auth/me` 路由（修改个人信息）
    - 支持修改 user_name、email、gender、age、phone、address
    - 修改 email 需验证码验证
    - _需求：2.7_

  - [ ] 3.5 实现 `POST /auth/logout` 路由
    - 后端更新当前用户的 last_time 字段
    - _需求：2.8_

  - [ ] 3.6 实现 `DELETE /auth/me` 路由（注销账号）
    - 普通用户只能删除自己的账号
    - _需求：2.9_

  - [ ]* 3.7 为认证路由编写单元测试
    - 测试注册成功、重复用户名/邮箱、登录成功、密码错误等场景
    - _需求：2.1, 2.2, 2.3, 2.4_

- [x] 4. 检查点 — 确保认证系统所有测试通过，如有问题请告知

- [x] 5. 实现日记数据模型与服务层
  - [x] 5.1 实现 Diary SQLAlchemy 模型和 Pydantic schema（DiaryCreate、DiaryUpdate、DiaryResponse）
    - 字段：nid、uid、content、is_open、date、weather、ai_ans、create_time、update_time
    - _需求：3.1, 3.5, 3.6_

  - [x] 5.2 实现 DiaryService 服务层
    - `create_entry(uid, content, is_open, tag_ids)` — 创建日记，校验内容非空，关联标签，更新 UsageCount
    - `get_entries(uid, skip, limit, tag_id)` — 按时间倒序查询，支持标签筛选
    - `get_entry(uid, nid)` — 查询单篇，验证归属
    - `update_entry(uid, nid, data)` — 修改日记，同步更新标签关联和 UsageCount
    - `delete_entry(uid, nid)` — 删除，验证归属，级联删除分析记录，更新 UsageCount
    - _需求：3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 5.3 为日记服务编写属性测试
    - **属性 3：用户数据隔离**
    - **属性 4：日记内容非空校验**
    - **属性 5：日记创建与存储一致性**
    - **属性 6：日记列表时间倒序**
    - **Validates: Requirements 3.1, 3.2, 4.1, 4.2, 4.3**
    - `# Feature: personal-website-diary, Property 3-6`

- [x] 6. 实现日记路由（带认证保护）
  - [x] 6.1 实现 `POST /diary/entries` 路由
    - 从 JWT 中提取 uid，调用 DiaryService 创建条目
    - _需求：3.1, 3.2_

  - [x] 6.2 实现 `GET /diary/entries` 路由（分页 + 标签筛选）
    - 只返回当前用户的日记，按时间倒序
    - _需求：4.1, 4.3, 4.4_

  - [x] 6.3 实现 `GET /diary/entries/{nid}` 路由
    - 验证日记归属，非本人返回 403
    - _需求：4.2_

  - [ ] 6.4 实现 `PUT /diary/entries/{nid}` 路由（修改日记）
    - 修改正文及标签，同步更新 UsageCount
    - _需求：3.3_

  - [x] 6.5 实现 `DELETE /diary/entries/{nid}` 路由
    - 验证归属，级联删除分析记录，更新标签 UsageCount
    - _需求：3.4_

  - [ ]* 6.6 为日记路由编写单元测试
    - 测试跨用户访问返回 403、无 token 返回 401 等场景
    - _需求：4.1, 4.2, 2.6_

- [x] 7. 检查点 — 确保日记功能所有测试通过，如有问题请告知

- [x] 8. 实现标签管理模块
  - [x] 8.1 实现 Tag SQLAlchemy 模型和 Pydantic schema（TagCreate、TagResponse）
    - 字段：tid、tag_name（max 15 chars）、color、creator、usage_cnt、create_time
    - _需求：5.1, 5.2, 5.3_

  - [x] 8.2 实现 TagService 服务层
    - `get_tags(sort_by_usage)` — 获取标签列表，支持按 UsageCount 排序
    - `create_tag(tag_name, color, creator)` — 创建标签，校验字数和唯一性
    - `update_tag(tid, data)` — 修改标签属性
    - `delete_tag(tid)` — 删除标签
    - _需求：5.3, 5.4, 5.5, 5.6_

  - [x] 8.3 实现标签路由（`GET/POST/PUT/DELETE /tags`）
    - _需求：5.4, 5.5_

  - [ ]* 8.4 为标签模块编写属性测试
    - **属性 8：标签字数限制**
    - **属性 9：标签引用计数一致性**
    - **Validates: Requirements 5.2, 5.6**
    - `# Feature: personal-website-diary, Property 8-9`

- [ ] 9. 实现模型管理模块
  - [ ] 9.1 实现 ModelProvider SQLAlchemy 模型和 Pydantic schema（ModelCreate、ModelResponse）
    - 字段：mod_id、uid、model_name、model_key（加密存储）、base_url、is_active、create_time
    - model_key 加密存储，ModelResponse 不返回 model_key
    - _需求：6.1, 6.2_

  - [ ] 9.2 实现 ModelService 服务层
    - `create_model(uid, data)` — 注册模型，加密 model_key
    - `get_models(uid)` — 获取当前用户模型列表
    - `update_model(uid, mod_id, data)` — 修改模型信息
    - `delete_model(uid, mod_id)` — 删除模型
    - `check_active_status()` — 定时检测模型活跃度
    - _需求：6.1, 6.3, 6.4, 6.5_

  - [ ] 9.3 实现模型路由（`GET/POST/PUT/DELETE /models`）
    - _需求：6.1, 6.3, 6.4_

- [ ] 10. 实现 AI 分析服务（ReAct Agent）
  - [ ] 10.1 实现 AIService，使用 LangChain 封装 ReAct Agent
    - 通过用户配置的 ModelProvider（base_url、model_key）调用 LLM
    - 支持 RAG（检索历史日记）、MCP（天气/日期工具）、Function Calling、上下文记忆
    - 标签作为 Few-shot 上下文输入，辅助 AI 理解日记内容
    - LLM 不可用时抛出自定义异常，由路由层返回 503
    - _需求：7.1, 7.2, 7.5_

  - [ ] 10.2 实现 AnalysisService 服务层
    - `create_analysis(uid, nid)` — 读取日记+标签，调用 AIService，存储结果
    - `get_analysis(nid)` — 获取分析结果
    - `update_analysis(uid, nid)` — 智能防重：内容无变化则拒绝
    - `delete_analysis(thk_id)` — 删除分析日志
    - _需求：7.1, 7.3, 7.4_

  - [ ] 10.3 实现分析路由（`POST/GET/PUT/DELETE /analysis`）
    - _需求：7.1, 7.3, 7.4_

  - [ ]* 10.4 为 AI 分析编写属性测试和单元测试
    - **属性 7：AI 分析用户隔离**
    - **属性 10：分析防重机制**
    - Mock LLM 服务失败场景，验证返回 503
    - **Validates: Requirements 7.2, 7.4**
    - `# Feature: personal-website-diary, Property 7, 10`

- [ ] 11. 实现前端认证系统（Vue 3）
  - [ ] 11.1 实现 `AuthStore`（Pinia）
    - 状态：`user`、`token`、`isAuthenticated`
    - 方法：`login()`、`register()`、`logout()`（调用后端 /auth/logout 更新 last_time）
    - token 持久化到 `localStorage`，页面刷新后自动恢复登录状态
    - _需求：2.3, 2.5, 2.8_

  - [ ] 11.2 实现路由守卫（Vue Router Navigation Guard）
    - 未登录时重定向到 `/login`
    - _需求：2.5, 2.6_

  - [ ] 11.3 实现登录页面 `LoginPage`
    - 表单：用户名/邮箱、密码输入框，登录按钮
    - 登录失败时展示错误信息
    - _需求：2.3, 2.4_

  - [ ] 11.4 实现注册页面 `RegisterPage`
    - 表单：用户名、邮箱、密码、确认密码输入框，注册按钮
    - 用户名/邮箱已存在时展示错误信息
    - _需求：2.1, 2.2_

  - [ ] 11.5 实现个人中心页面 `ProfilePage`
    - 修改个人信息表单，注销账号按钮
    - _需求：2.7, 2.9_

  - [ ]* 11.6 为 AuthStore 编写单元测试
    - 测试登录/登出状态变化、token 持久化、路由守卫重定向
    - _需求：2.3, 2.5, 2.6_

- [ ] 12. 实现前端日记功能页面
  - [ ] 12.1 实现 `DiaryEditor` 组件
    - 正文 textarea（必填）+ 标签多选组件
    - 提交时调用 `POST /diary/entries`，携带 JWT token
    - 内容为空时禁用提交按钮并展示提示
    - _需求：3.1, 3.2, 3.5_

  - [ ] 12.2 实现 `DiaryList` 组件
    - 调用 `GET /diary/entries` 获取当前用户日记列表
    - 按时间倒序展示，支持分页和标签筛选
    - _需求：4.1, 4.3, 4.4_

  - [ ] 12.3 实现 `AIAnalysisPanel` 组件
    - 点击"获取 AI 分析"按钮，调用 `POST /analysis`
    - 展示分析结果（ai_ans、thk_log、token_cost）
    - LLM 不可用时展示友好错误提示
    - _需求：7.1, 7.5_

  - [ ] 12.4 组装 `DiaryPage`，整合 DiaryEditor、DiaryList、AIAnalysisPanel
    - _需求：3.1, 4.1, 7.1_

- [ ] 13. 实现前端标签与模型管理页面
  - [ ] 13.1 实现 `TagManager` 组件
    - 展示标签列表（按 UsageCount 排序），支持新增/修改/删除自定义标签
    - _需求：5.4, 5.5_

  - [ ] 13.2 实现 `ModelManager` 组件
    - 展示用户模型列表，支持注册/修改/删除模型
    - model_key 输入框使用 password 类型，不回显
    - _需求：6.1, 6.2, 6.3, 6.4_

- [ ] 14. 实现报表打印功能
  - [ ] 14.1 实现日记列表导出（HTML/PDF）
    - _需求：8.1_

  - [ ] 14.2 实现个人信息报表生成
    - _需求：8.2_

- [ ] 15. 实现在线帮助模块
  - [ ] 15.1 实现新手引导（高亮遮罩 + 气泡提示）
    - _需求：9.1_

  - [ ] 15.2 实现 FAQ 静态页面（支持关键词搜索）
    - _需求：9.2_

  - [ ] 15.3 实现用户反馈留言板
    - _需求：9.3_

- [ ] 16. 最终检查点 — 确保所有测试通过，前后端联调正常，如有问题请告知

---

## 备注

- 标有 `*` 的子任务为可选测试任务，可跳过以加快 MVP 进度
- 每个任务均引用具体需求编号以保证可追溯性
- 属性测试使用 `hypothesis` 库，每个属性最少运行 100 次
- 前端测试使用 `Vitest` + `Vue Test Utils`
- 所有日记/分析/标签/模型接口均需通过 JWT 认证，uid 从 token 中提取，不接受客户端传入
- model_key 加密存储，任何接口均不返回原始 model_key
- 管理员功能（封禁用户、系统备份/恢复、标签维护）在 MVP 后实现
