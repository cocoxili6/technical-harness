# 研途 · Research Harness

面向科研入门者的文献调研工作台：输入一个研究方向或问题，智能体检索 arXiv、OpenAlex 与 Google Scholar、梳理方法脉络，输出按入门、基础、进阶、前沿四阶段排序的文献阅读路线和下一步动作。

- 前端：Vue 3 + Vite + TypeScript
- 后端：FastAPI + LangGraph
- 模型：DeepSeek（OpenAI 兼容接口）
- 交互：SSE 流式输出、检索轨迹、来源卡片、多轮短期记忆、按 token 预算滚动压缩的上下文、按遗忘曲线衰减的长期记忆、刷新恢复会话

当前仓库是**本地可运行脚手架**，尚未发布到 Qoder Sites。未配置模型 Key 时自动进入演示模式，界面上的示例内容会明确标注。

身份验证使用 Supabase Auth 邮箱一次性验证码。会话、消息、长期记忆、LangGraph 检查点、论文清单和滚动摘要保存在 Supabase PostgreSQL，并按已验证的用户 ID 隔离。

## 目录

```text
backend/
  app/
    main.py              FastAPI 入口、SSE 协议、会话接口
    config.py            环境配置
    auth.py              Supabase JWT 验证与网关凭据校验
    db.py                PostgreSQL 用户事务、RLS claims、LangGraph saver 生命周期
    repositories/        用户隔离的会话、记忆和上下文仓储
    migrations/          用户数据表、外键和 RLS 策略
    memory.py            长期记忆遗忘曲线、检索与自动抽取逻辑
    demo.py              未配置 Key 时的演示流
    agent/
      graph.py           LangGraph: prepare_context -> assistant <-> ToolNode
      compact.py         上下文管理：论文清单、工具结果归档、滚动摘要
      tools.py           arXiv / Google Scholar 检索工具
      prompts.py         研究向导系统提示词
  requirements.txt
  Dockerfile
  .env.example
frontend/
  .env.example
  src/
    App.vue              工作台、会话状态、流式消费
    components/
      AuthGate.vue       邮箱 OTP 登录界面
      ...               侧栏、会话、Markdown、轨迹、来源、输入框
    lib/api.ts           HTTP + SSE 客户端
functions/
  app/index.ts           Qoder Sites Edge Function 部署入口
  app/proxy.ts           白名单校验、Supabase bearer 与网关凭据转发
```

## 快速开始

前置：Python 3.11+、Node.js 20+。

启动后端（Windows）：

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

macOS / Linux：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173 。后端健康检查在 http://127.0.0.1:8000/api/health ，接口文档在 http://127.0.0.1:8000/docs 。

> 依赖说明：Python 3.9 可用的 LangGraph 最高为 0.4.x，因此 `requirements.txt` 固定了 `langgraph-prebuilt==0.2.3`。更新的 prebuilt 版本要求 LangGraph 1.x，与 3.9 不兼容。

## 接入 DeepSeek

```bat
cd backend
copy .env.example .env
```

编辑 `backend/.env`：

```ini
DEEPSEEK_API_KEY=sk-你的Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

重启后端。访问 `/api/health`，当 `demo_mode` 为 `false` 时表示已切换到真实模型。Key 只在后端使用，不会进入前端产物。

模型调用链：LangGraph `assistant` 节点 → DeepSeek → 需要时调用 `search_arxiv` / `search_scholar` → 继续生成。前端只消费后端转发的 SSE。

## 接入 Google Scholar（可选）

谷歌学术没有官方 API，直接爬取会触发验证码并封 IP，因此走 [Serper.dev](https://serper.dev) 的 Google Scholar 接口（注册送 2,500 次免费查询，无需信用卡）。

1. 在 serper.dev 注册并复制 API Key；
2. 编辑 `backend/.env`，填入：

```ini
SERPER_API_KEY=你的Key
```

3. 重启后端。`/api/health` 的 `search` 字段变为 `arXiv + Google Scholar` 时表示已启用。

启用后智能体多一个 `search_scholar` 工具：适合期刊/会议论文、综述和按引用量判断影响力；arXiv 工具继续负责最新预印本。每次调用消耗 1 次 Serper 查询额度，最多返回 8 条结果。未配置 Key 时该工具不会暴露给模型，其余功能不受影响。

## 长期记忆（遗忘曲线）

登录后，侧栏「长期记忆」卡片打开管理面板。记忆存放在 Supabase `public.memories` 表，并由 RLS 与显式 `user_id` 条件双重隔离。旧版本地 `backend/data/memories.json` 没有可信的账户归属，不会自动导入。

- **写入**：每轮真实对话结束后，后台让 DeepSeek 抽取 0-3 条关于用户的稳定信息；按科研辅导场景分类：知识基础、学习偏好、方向兴趣、方向目标、阅读/复现进展、工具事实。目标和进展必须绑定具体方向，泛化目标（了解全景/找问题）由界面画像承担，不重复记录；相似记忆自动合并，也可在面板里手动添加。
- **衰减**：每条记忆有稳定度 S（天），强度 `R = e^(−t/S)`，t 为距上次回想的天数。初始 S = `(3 + 3 × 重要度) × 类别系数`：背景/偏好 1.5，兴趣 1.2，目标/事实 1.0，进展 0.6；进展类无论 S 多高，90 天未更新即视为淡忘。
- **强化**：记忆被当前问题命中、或面板里点「复习」，`S ← S × (1 + 1.5 × (1 − R)) + 0.5`，即越接近遗忘时复习，间隔拉得越长（间隔重复）。
- **淡忘**：`R < 10%` 视为淡忘，不再注入回答；面板可恢复（强度回到 100%）或删除。最多保留 300 条，超出时优先淘汰最弱的淡忘记忆。
- **注入（两层）**：稳定画像层（知识基础/学习偏好）每轮常驻，按类别取最强条目拼成 ≤120 字摘要；情景层（兴趣/目标/进展/事实）只注入与当前方向相关的记忆，检索时拼接会话主题与当前问题，最多 5 条、合计 ≤600 字。画像层不会因为常驻展示而强化，只有问题命中才触发强化。
- 演示模式没有 LLM，自动抽取不运行；启用 Supabase 后，面板仍可手动添加、复习和删除记忆。

## 架构

```text
Vue 工作台 + Supabase Auth
  │  Supabase access token
  ▼
Qoder Edge Function
  │  Authorization: Supabase bearer
  │  x-harness-gateway-token: Edge shared secret
  ▼
FastAPI ──▶ Supabase PostgreSQL (RLS + user_id 条件)
  │              ├─ threads / messages / memories
  │              ├─ paper_catalog / context_summaries
  │              └─ LangGraph Postgres checkpointer
  └─ LangGraph: prepare_context -> assistant <-> ToolNode -> prepare_context
```

- **身份与隔离**：FastAPI 从签名验证通过的 JWT `sub` 获取用户 ID。数据库事务设置 Supabase JWT claims 和 `authenticated` role，所有仓储查询同时显式限定 `user_id`。
- **会话持久化**：threads、messages、memories、论文目录、工具运行记录、滚动摘要和 LangGraph checkpoint 均存入 PostgreSQL。checkpoint 使用 `checkpoint_ns=user:<user_id>`。
- **记忆与上下文**：LangGraph `prepare_context` 按 token 预算压缩历史；摘要与论文目录另存于用户隔离的上下文表。长期记忆仍按遗忘曲线检索和强化。
- **界面恢复**：刷新后从 `/api/threads` 和 `/api/threads/{id}` 恢复数据库会话。浏览器只在 `localStorage` 记住当前 thread ID。

### 上下文管理

窗口是不可能无限增长的工作台，所以上下文按用途分三层管理，超出预算时压缩而不是报错。

- **论文清单 `paper_catalog`**：每条工具结果中的论文按 URL 去重后由代码写入结构化清单（标题、链接、年份、出处、引用量）。清单跨轮持久，引用论文时标题和链接只能取自这里，避免压缩后编造链接，也避免重复推荐。每轮注入最近 `CONTEXT_CATALOG_LIMIT` 篇。
- **工具结果归档**：最后一条用户消息之前的历史工具结果，从下一轮开始替换为一行占位符（工具名、关键词、命中数），完整原文不再进入上下文；当轮和第 0 级裁剪时保持原样，便于模型综合本轮检索。归档按消息 id 原地替换，`tool_call_id` 配对不变。
- **滚动摘要**：进入新一轮用户消息时估算总 token（system + 纪要 + 清单 + 历史），超过 `CONTEXT_TOKEN_BUDGET` 就把倒数第 `CONTEXT_KEEP_TURNS` 轮之前的消息交给非流式模型压缩成纪要（进展 / 已确定 / 待办），再用 `RemoveMessage` 删除原文。摘要失败时降级为少删一轮，不影响回答。摘要调用带 `context-compaction` 标签，SSE 层按标签过滤，不会混入回答。
- **缓存与顺序**：工具循环内不归档、不压缩，保持前缀稳定以命中 DeepSeek 的自动 KV 缓存；静态 system、纪要、清单分为三条 `SystemMessage`，静态前缀在前，压缩时只改后面的动态部分。

### SSE 事件

| event | 载荷 | 说明 |
| --- | --- | --- |
| `meta` | `thread_id`, `title`, `demo` | 会话建立或复用 |
| `token` | `text` | 增量文本 |
| `tool_start` | `id`, `name`, `input.query` | 工具开始 |
| `tool_end` | `id`, `name`, `ok`, `summary`, `count` | 工具结束 |
| `sources` | `items[]` | 文献来源，字段见下 |
| `done` | `thread_id` | 本轮完成 |
| `error` | `message` | 本轮失败或中断 |

来源字段：`title`, `authors`, `year`, `url`, `category`, `summary`。工具返回其他结构时仍会显示检索轨迹，但不会生成来源卡片。

### 接口

- `GET /api/health`：运行模式、模型名、检索器
- `GET /api/threads`：会话列表
- `GET /api/threads/{thread_id}`：会话消息（含轨迹与来源）
- `POST /api/chat/stream`：`{ "message": "...", "thread_id": "可选" }`
- `GET /api/memories`：长期记忆列表（含强度、稳定度、是否淡忘）
- `POST /api/memories`：`{ "text": "..." }` 手动添加记忆
- `POST /api/memories/{id}/review`：复习一条记忆（强化稳定度）
- `DELETE /api/memories/{id}`：删除一条记忆

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 空 | 为空时进入演示模式 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `DEEPSEEK_TEMPERATURE` | `0.3` | 采样温度 |
| `ARXIV_ENDPOINT` | `https://export.arxiv.org/api/query` | 文献检索端点 |
| `SERPER_API_KEY` | 空 | 为空时智能体只有 arXiv 工具；填入后启用 Google Scholar 检索 |
| `CORS_ORIGINS` | 本地 5173 | 逗号分隔；使用 Edge Function 代理时浏览器不跨域 |
| `CONTEXT_TOKEN_BUDGET` | `28000` | 上下文预算（估算 token），超限触发滚动摘要 |
| `CONTEXT_KEEP_TURNS` | `2` | 压缩时保留最近几轮原文 |
| `CONTEXT_CATALOG_LIMIT` | `40` | 每轮注入论文清单的最大条数 |
| `SUPABASE_URL` | 空 | Supabase 项目 URL |
| `SUPABASE_JWT_ISSUER` | 空 | `https://<project-ref>.supabase.co/auth/v1` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | access token audience |
| `SUPABASE_JWKS_URL` | 空 | Supabase Auth JWKS endpoint |
| `SUPABASE_DB_URL` | 空 | 后端 PostgreSQL session pooler URL，使用 `postgresql+asyncpg://` scheme |
| `HARNESS_SHARED_TOKEN` | 空 | Edge 到 FastAPI 的共享凭据，放在 `x-harness-gateway-token` |

Supabase URL 和 publishable anon key 是前端公开配置，不要把 `service_role` key 放入浏览器变量。数据库密码、DeepSeek key 和 `HARNESS_SHARED_TOKEN` 只放在后端或 Edge secret。开发环境的 `.env`、`env1.env` 和 `.env.local` 都已加入 Git 忽略。

本地使用 Vite 代理直连 FastAPI 时，后端 `HARNESS_SHARED_TOKEN` 留空；走 Edge Function 时，后端与 Edge 两侧设置相同的共享值。

## 扩展

- **换检索源**：在 `backend/app/agent/tools.py` 新增 `@tool`，按 arXiv 工具的结构返回 JSON 字符串；然后在 `graph.py` 的 `tools` 列表中加入它。
- **改阅读路线结构**：编辑 `backend/app/agent/prompts.py`。
- **持久化边界**：仓储接口位于 `backend/app/repositories/`；用户表结构和 RLS 位于 `backend/migrations/0001_user_data.sql`。LangGraph 使用 `AsyncPostgresSaver` 的官方 schema setup。

## 配置 Supabase

1. 在 Supabase 创建项目并启用 Authentication 的 Email provider。
2. 要让用户输入数字验证码，在 Authentication → Email Templates 的登录验证码模板中使用 `{{ .Token }}`，并确认 Email OTP 已启用。按项目计划配置 SMTP 与邮件发送额度。
3. 在 SQL Editor 执行 `backend/migrations/0001_user_data.sql`，创建用户数据表、复合外键与 `auth.uid()` RLS policies。
4. 从 Database → Connect 复制 session pooler 连接信息。后端连接串使用 `postgresql+asyncpg://` scheme，并对密码中的保留字符做 URL 编码。
5. 前端只使用 Project URL 和 publishable anon key。不要使用 `service_role` key。

FastAPI 启动时会调用 LangGraph `AsyncPostgresSaver.setup()` 初始化其官方 checkpoint schema。旧版本地 `backend/data/memories.json` 没有可信的账户归属，不会自动导入。

本地运行时，将 `backend/.env.example` 复制为 `backend/.env`，将 `frontend/.env.example` 复制为 `frontend/.env.local`，再填入各自的配置。

## 部署到 Qoder Sites

Qoder Sites 托管静态前端和 TypeScript/Deno Edge Function，FastAPI 运行在独立服务器。

```text
浏览器（Supabase Auth）→ Qoder Sites + Edge Function → FastAPI/LangGraph → Supabase PostgreSQL
```

### 1. 部署 FastAPI 后端

用 `backend/Dockerfile` 部署到 Railway、Fly.io、Render 或自有服务器。配置 `backend/.env.example` 中的后端变量，至少包括：

```ini
DEEPSEEK_API_KEY=...
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_JWT_ISSUER=https://<project-ref>.supabase.co/auth/v1
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_DB_URL=postgresql+asyncpg://postgres.<project-ref>:<URL-encoded-password>@<pooler-host>:5432/postgres
HARNESS_SHARED_TOKEN=<long-random-secret>
```

后端需要公网 HTTPS、至少 5 分钟的流式连接时长。反向代理须关闭响应缓冲，Nginx 可设置 `proxy_buffering off;`。

### 2. 配置 Edge Function

Function 白名单代理健康检查、会话、聊天和记忆接口。它将浏览器的 Supabase bearer token 放在 `Authorization`，并把 Edge 共享凭据单独放在 `x-harness-gateway-token`。

在 Qoder Sites 为 Function 配置两个 Secret：

- `HARNESS_BACKEND_URL`：FastAPI origin，例如 `https://harness-api.example.com`，不要带 `/api`。
- `HARNESS_SHARED_TOKEN`：与 FastAPI 环境变量完全一致。

### 3. 构建并发布前端

在 Qoder Sites 的构建环境配置公开变量：

```ini
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable-anon-key>
VITE_API_BASE=/functions/v1/app
```

这些值会写入浏览器构建产物。数据库密码、DeepSeek API key 和 `HARNESS_SHARED_TOKEN` 只能留在服务端或 Edge Secrets。

构建命令为 `cd frontend && npm run build`。发布时设置静态目录 `frontend/dist` 和 Function 目录 `functions/app`。在已发布站点验证邮箱验证码登录、会话恢复与 SSE 流式聊天。

Function 上游超时设为 5 分钟，实际可用时长还受 Qoder 平台限制。

## 历史验证记录（2026-11-20）

| 项目 | 结果 |
| --- | --- |
| 演示模式 UI（桌面 1440×1000 / 移动 390×844） | 通过：流式渲染、轨迹、表格、来源卡片、侧栏抽屉、无横向溢出 |
| 会话切换与刷新恢复 | 通过：两轮消息、来源、检索轨迹均可恢复 |
| 真实分支（OpenAI 兼容 mock，非 DeepSeek） | 通过：22 个 token 事件、工具调用、2 个来源、两轮上下文（模型侧消息数 6 → 8）、刷新后轨迹恢复 |
| Google Scholar 工具（mock Serper + mock DeepSeek 全链路） | 通过：24 项单元检查；`search_scholar` 工具调用、2 张来源卡片（出处/年份回填）、会话持久化；浏览器 UI 验证通过（顶栏检索源、轨迹标签、来源卡片）；真实 Serper 接口待 Key |
| 长期记忆（遗忘曲线 + 持久化） | 通过：单元检查（相似合并、相关检索、30 天衰减 R=0.08 判定淡忘、复习复活、重载持久化）；API 增删查复习；浏览器面板添加/复习/删除、活跃与淡忘分组、侧栏计数同步；后端重启后记忆保留 |
| 长期记忆两层注入 | 通过：画像层仅含知识基础/学习偏好且常驻（≤120 字）、情景层含兴趣/目标/进展/事实并仅注入方向相关问题（≤5 条 / ≤600 字）、会话主题参与检索（追问不丢方向）、无关情景不注入、类别衰减系数与进展 90 天过期生效 |
| 长期记忆自动抽取（DeepSeek） | 未验证：抽取逻辑已接入，等待 API Key 实测 |
| 上下文管理（归档 + 滚动摘要，2026-11-23） | 通过：59 项离线检查（38 项模块单测：估算/去重/归档/切点/降级/纪要渲染；21 项图级集成：工具循环→清单→归档→压缩→纪要注入、裁剪后工具调用配对完整）；真实 DeepSeek 长对话待 Key |
| DeepSeek 官方接口 | 未验证：等待你提供 API Key |
| Qoder Sites Edge 代理 | 未验证：未部署；本机未安装 Deno，未执行 `deno check` |
| 前端类型检查 / 生产构建 | 通过 |

真实分支的 mock 只验证了“LangGraph + ChatOpenAI 兼容协议 + 工具 + SSE + 前端”的链路，不证明 DeepSeek 账号、额度和网络可用性。

## 身份与持久化验证记录（2026-11-27）

| 项目 | 结果 |
| --- | --- |
| Supabase 用户表迁移与 RLS | 通过：六张业务表启用 RLS；两名临时用户实测互相不可见，测试账号已清理 |
| 会话/消息/记忆 repositories | 通过：owner 可读写，另一用户读不到；临时测试用户已清理 |
| 摘要与论文目录恢复 | 通过：新 repository 实例能从 Supabase 读回保存状态，测试用户已清理 |
| LangGraph checkpoint schema | 通过：应用当前安装包提供的官方 migrations 到版本 9；本机 Windows 策略阻止 psycopg 二进制扩展加载，因此 saver 运行时启动仍需在 Linux 部署环境确认 |
| 后端测试 | 通过：21 项；有 1 条 LangChain pending-deprecation warning |
| 前端 OTP、API token、登出清理 | 通过：9 项 Vitest，TypeScript typecheck 和 Vite production build 通过 |
| Supabase 邮件 OTP 实际收件 | 待验证：需要在 Supabase 配置邮件模板/SMTP 后，用真实邮箱完成一次登录 |
| Edge Function 测试 | 待验证：已添加 Deno tests，但本机没有 Deno runtime |
