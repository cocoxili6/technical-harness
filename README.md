# 研途 · Research Harness

面向科研入门者的文献调研工作台：输入一个研究方向或问题，智能体检索 arXiv 与 Google Scholar、梳理方法脉络，输出分阶段研究路线和下一步动作。

- 前端：Vue 3 + Vite + TypeScript
- 后端：FastAPI + LangGraph
- 模型：DeepSeek（OpenAI 兼容接口）
- 交互：SSE 流式输出、检索轨迹、来源卡片、多轮短期记忆、刷新恢复会话

当前仓库是**本地可运行脚手架**，尚未发布到 Qoder Sites。未配置模型 Key 时自动进入演示模式，界面上的示例内容会明确标注。

## 目录

```text
backend/
  app/
    main.py              FastAPI 入口、SSE 协议、会话接口
    config.py            环境配置
    store.py             会话元数据 + 界面消息投影（进程内）
    demo.py              未配置 Key 时的演示流
    agent/
      graph.py           LangGraph: assistant <-> ToolNode
      tools.py           arXiv / Google Scholar 检索工具
      prompts.py         研究向导系统提示词
  requirements.txt
  Dockerfile
  .env.example
frontend/
  src/
    App.vue              工作台、会话状态、流式消费
    components/          侧栏、会话、Markdown、轨迹、来源、输入框
    lib/api.ts           HTTP + SSE 客户端
  .env.example
functions/
  app/index.ts           Qoder Sites Edge Function：FastAPI 同源代理
```

## 快速开始

前置：Python 3.9+（推荐 3.11）、Node.js 20+。

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

## 架构

```text
Vue 工作台
  │  POST /api/chat/stream  (fetch + SSE)
  ▼
FastAPI
  │
  ├─ LangGraph: assistant ──▶ ToolNode(search_arxiv / search_scholar) ──▶ assistant
  │     MemorySaver(thread_id)            arXiv API
  │
  └─ ConversationStore: 用户/助手消息、检索轨迹、来源卡片
```

- **LLM 短期记忆**：LangGraph `MemorySaver` 按 `thread_id` 保存完整消息序列，工具结果也会进入上下文。
- **界面恢复**：`ConversationStore` 额外保存一份界面投影（含检索轨迹和来源），刷新页面后可以通过 `/api/threads/{id}` 恢复。
- **生命周期**：两者都在后端进程内，服务重启即清空；前端只在 `localStorage` 记住当前会话 ID。

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
| `HARNESS_SHARED_TOKEN` | 空 | 后端侧共享令牌；为空表示不校验 |

`HARNESS_SHARED_TOKEN` 与 Edge Function 配合使用。本地经 Vite 代理直连后端时保持为空，否则请求会 401。

## 扩展

- **换检索源**：在 `backend/app/agent/tools.py` 新增 `@tool`，按 arXiv 工具的结构返回 JSON 字符串；然后在 `graph.py` 的 `tools` 列表中加入它。
- **改研究路线结构**：编辑 `backend/app/agent/prompts.py`。
- **换持久化**：把 `MemorySaver` 换成 SQLite/Postgres checkpointer，并把 `ConversationStore` 换成数据库表。`thread_id` 契约不变，前端无需改动。

## 部署到 Qoder Sites（方案 A：保留 Python）

Qoder Sites 只能托管静态文件和一个 TypeScript/Deno Edge Function，不能运行 Python。当前方案：

```text
浏览器 → Qoder Sites 静态站 + Edge Function 同源代理 → 外部 FastAPI/LangGraph → DeepSeek / arXiv
```

### 1. 部署 Python 后端

用 `backend/Dockerfile` 部署到 Railway、Fly.io、Render 或自有服务器，配置：

```ini
DEEPSEEK_API_KEY=...
HARNESS_SHARED_TOKEN=一个随机长字符串
CORS_ORIGINS=https://你的站点域名
```

要求：

- 公网 HTTPS 可达；
- 反向代理关闭响应缓冲（FastAPI 已发送 `X-Accel-Buffering: no`，Nginx 可配 `proxy_buffering off;`）；
- 实例至少能保持 5 分钟以上的流式连接。

### 2. 配置 Edge Function

`functions/app/index.ts` 已实现白名单代理：`/api/health`、`/api/threads`、`/api/threads/{id}`、`/api/chat/stream`。它不暴露任意上游，也不把令牌返回给浏览器。

在 Qoder Sites 中为该 Function 声明并配置两个 Secret：

- `HARNESS_BACKEND_URL`：FastAPI 的 origin，例如 `https://harness-api.example.com`（不要带 `/api`）
- `HARNESS_SHARED_TOKEN`：与后端同名变量一致

### 3. 构建前端

```bash
cd frontend
VITE_API_BASE=/functions/v1/app npm run build
```

这样浏览器请求 `/functions/v1/app/api/...`，由 Edge Function 转发到 FastAPI 的 `/api/...`。

### 4. 准备并发布

通过 Qoder Sites 以以下输入准备站点：

- 静态目录：`frontend/dist`
- Function 目录：`functions/app`
- 需要声明的 Secret：`HARNESS_BACKEND_URL`、`HARNESS_SHARED_TOKEN`

准备完成后在 Sites 设置中录入 Secret 值并等待同步，再发布。发布预览不执行 Function，健康检查、流式对话和会话恢复需要在已发布站点上验证。

### 部署注意

- Function 设置了 5 分钟上游超时；平台本身可能还有更短的执行时限，长调研需要拆分或改轮询方案。
- 公开站点意味着任何人都能调用这个代理并消耗你的模型额度。建议把站点设为受控访问，或再加应用级限流/登录。
- 不使用代理、让前端直连 FastAPI 也可行：`VITE_API_BASE=https://api.example.com`，并把站点域名加入 `CORS_ORIGINS`。这样更简单，但后端 API 对公网开放。

## 验证记录（2026-11-20）

| 项目 | 结果 |
| --- | --- |
| 演示模式 UI（桌面 1440×1000 / 移动 390×844） | 通过：流式渲染、轨迹、表格、来源卡片、侧栏抽屉、无横向溢出 |
| 会话切换与刷新恢复 | 通过：两轮消息、来源、检索轨迹均可恢复 |
| 真实分支（OpenAI 兼容 mock，非 DeepSeek） | 通过：22 个 token 事件、工具调用、2 个来源、两轮上下文（模型侧消息数 6 → 8）、刷新后轨迹恢复 |
| Google Scholar 工具（mock Serper + mock DeepSeek 全链路） | 通过：24 项单元检查；`search_scholar` 工具调用、2 张来源卡片（出处/年份回填）、会话持久化；浏览器 UI 验证通过（顶栏检索源、轨迹标签、来源卡片）；真实 Serper 接口待 Key |
| DeepSeek 官方接口 | 未验证：等待你提供 API Key |
| Qoder Sites Edge 代理 | 未验证：未部署；本机未安装 Deno，未执行 `deno check` |
| 前端类型检查 / 生产构建 | 通过 |

真实分支的 mock 只验证了“LangGraph + ChatOpenAI 兼容协议 + 工具 + SSE + 前端”的链路，不证明 DeepSeek 账号、额度和网络可用性。
