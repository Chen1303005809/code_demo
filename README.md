# LLM 查询面板

基于 **FastAPI + React** 的 LLM（LightRag）流式查询面板。支持多项目隔离配置、会话上下文、SSE 流式输出与历史记录。

> 上游 LightRag 服务不在本仓库内，通过环境变量 `LLM_API_URL` 指向。

## 技术栈

- **后端**：FastAPI · Uvicorn · aiosqlite · httpx（SSE 流式消费上游）
- **前端**：React 18 · TypeScript · Vite · react-markdown
- **存储**：SQLite（会话 / 消息 / 项目 / 历史记录）
- **部署**：Docker Compose（多阶段构建，单容器同时托管 API 与前端静态资源）

## 目录结构

```
.
├── backend/          FastAPI 应用（路由、DB、调度器、LLM 客户端）
├── frontend/         React 前端（Vite 构建）
├── scripts/          数据库初始化脚本（可选）
├── Dockerfile        多阶段：node 构建前端 → python 运行后端
├── docker-compose.yml
├── .env.example      环境变量示例
└── API.md            后端 API 文档
```

## 快速开始（Docker Compose，推荐）

需要本机已安装 Docker 与 Docker Compose。

```bash
# 1. 拷贝并按需修改环境变量（重点是 LLM_API_URL）
cp .env.example .env

# 2. 构建并启动
docker compose up -d --build

# 3. 打开浏览器
open http://localhost:8080
```

启动后：

- 前端 + API 同源：`http://localhost:8080`
- 健康检查：`http://localhost:8080/health`
- API 文档：见 [`API.md`](./API.md)

### 连接上游 LightRag

面板需要上游 LightRag 服务提供 `/query/stream` 流式接口。在 `.env` 中设置 `LLM_API_URL`：

| LightRag 位置 | 配置值 |
|---|---|
| 跑在宿主机（本机） | `http://host.docker.internal:9621`（默认） |
| 同在 Docker 网络内 | `http://<服务名>:9621` |
| 远程服务器 | `http://<ip>:<port>` |

> 没有上游服务时，面板仍可正常打开、浏览历史，但发问会返回错误事件。

### 常用命令

```bash
docker compose up -d --build    # 构建并后台启动
docker compose logs -f app      # 查看实时日志
docker compose restart          # 重启（数据保留在卷中）
docker compose down             # 停止并删除容器（保留数据卷）
docker compose down -v          # 停止并删除容器 + 数据卷（清空数据）
```

### 数据持久化

SQLite 数据库落在命名卷 `app-data`（容器内路径 `/app/data/history.db`）。
`docker compose down`（不带 `-v`）不会删除数据；`restart` / 重新 `up` 后数据仍在。

---

## 本地开发（不使用 Docker）

分别启动前后端，前端 dev server 自带 `/api`、`/health` 代理到后端（见 `frontend/vite.config.ts`）。

### 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example ../.env          # 或在本目录建 .env，至少设置 LLM_API_URL
# 编辑 .env：LLM_API_URL=http://localhost:9621（开发时上游多在本机）

uvicorn main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173，自动代理 /api → 127.0.0.1:8000
```

### （可选）手动初始化数据库

后端首次运行会自动建表，一般无需手动执行。如需预建旧版 `queries` 表：

```bash
python scripts/init_db.py                 # 默认读取 .env 中的 DB_PATH
python scripts/init_db.py --db-path ./data/history.db
```

---

## 配置项

所有配置通过环境变量注入（`.env` 或 `docker-compose.yml` 的 `environment`）：

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `LLM_API_URL` | 是 | — | LightRag 基础地址（不含 `/query/stream`，代码自动拼接） |
| `LLM_API_KEY` | 否 | 空 | Bearer Token；留空则不发 `Authorization` 头 |
| `LLM_QUERY_MODE` | 否 | `mix` | 查询模式：`mix` / `hybrid` / `local` / `global` / `naive` |
| `LLM_TIMEOUT_MS` | 否 | `60000` | 单次请求读取超时（毫秒） |
| `MAX_CONCURRENCY` | 否 | `3` | 并发槽位数；超出的请求排队并收到 `queued` 事件 |
| `DB_PATH` | 否 | `./data/history.db` | SQLite 路径（容器内固定为 `/app/data/history.db`） |

> 项目级覆盖：在面板中创建项目时可单独设置该项目的 `llm_api_url` / `llm_api_key` / `llm_query_mode` / `prompt_template`，留空字段回退到全局配置。

---

## 架构与行为要点

- **流式查询**：`/api/query` 与 `/api/sessions/{id}/query` 返回 `text/event-stream`，事件类型 `queued` / `started` / `chunk` / `done` / `error`，详见 [`API.md` §6](./API.md#6-sse-事件协议)。
- **并发控制**：调度器用 Semaphore 限流；槽位满时请求排队，先下发 `queued` 事件，按完成顺序依次调度。
- **会话上下文**：会话内查询会自动带上历史消息作为 `conversation_history` 传给上游；首条消息用于自动生成会话标题。
- **删除项目**：不级联删除其下会话，而是把会话的 `project_id` 置空（会话保留）。
- **历史记录**：来自无会话查询（`/api/query`）写入的旧版 `queries` 表，供历史侧栏浏览。

## 许可

（待补充）
