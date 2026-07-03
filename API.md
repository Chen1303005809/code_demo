# 后端 API 文档

LLM 查询面板后端基于 **FastAPI**，提供项目管理、会话管理、流式查询（SSE）与历史记录四类接口。所有业务路径前缀为 `/api`，另有一个健康检查端点 `/health`。

- 默认监听端口：`8000`（容器内），部署时映射到宿主机 `8080`。
- 生产部署为单容器：同一 FastAPI 服务既提供 `/api`、`/health`，也托管前端构建产物（`/assets`、SPA 回退）。前端与后端同源，无需跨域。
- 时间字段均为 **UTC ISO 8601** 字符串（如 `2026-07-03T08:30:00+00:00`）。
- 所有 `DELETE` 接口成功时 HTTP 200，响应体为 `null`。
- 资源不存在时返回 `404`，响应体：`{"detail": "<中文原因>"}`。

---

## 目录

1. [项目 Projects](#1-项目-projects)
2. [会话 Sessions](#2-会话-sessions)
3. [查询（流式）Query / SSE](#3-查询流式query--sse)
4. [历史 History](#4-历史-history)
5. [健康检查](#5-健康检查)
6. [SSE 事件协议](#6-sse-事件协议)
7. [数据模型](#7-数据模型)

---

## 1. 项目 Projects

### 1.1 列出全部项目

`GET /api/projects`

按更新时间降序返回，每项含 `session_count`（该项目下会话数）。

**响应** `200` — [`ProjectList`](#projectlist)

```json
{
  "items": [
    {
      "id": "proj_a1b2c3d4",
      "name": "代码问答",
      "description": "基于代码库的问答",
      "llm_api_url": "",
      "llm_query_mode": "mix",
      "session_count": 3,
      "created_at": "2026-07-01T10:00:00+00:00",
      "updated_at": "2026-07-03T09:12:33+00:00"
    }
  ]
}
```

### 1.2 创建项目

`POST /api/projects`

**请求体** — [`ProjectCreate`](#projectcreate)

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `name` | string | 是 | — | 项目名 |
| `description` | string | 否 | `""` | 描述 |
| `llm_api_url` | string | 否 | `""` | 上游 LightRag 地址（留空则用全局 `LLM_API_URL`） |
| `llm_api_key` | string | 否 | `""` | Bearer Token（留空则用全局） |
| `llm_query_mode` | string | 否 | `"mix"` | 查询模式：`mix`/`hybrid`/`local`/`global`/`naive` |
| `prompt_template` | string | 否 | `"{query}"` | 用户提示词模板，`{query}` 占位 |

**响应** `201` — [`ProjectItem`](#projectitem)

### 1.3 获取项目详情

`GET /api/projects/{project_id}`

**路径参数**

| 字段 | 类型 | 说明 |
|---|---|---|
| `project_id` | string | 项目 ID，形如 `proj_xxxxxxxx` |

**响应** `200` — [`ProjectItem`](#projectitem)（`session_count` 固定为 `0`，详情接口不查会话数）

**错误** `404` 项目不存在

### 1.4 更新项目

`PUT /api/projects/{project_id}`

只更新请求体中**非 `null`** 的字段。

**请求体** — [`ProjectUpdate`](#projectupdate)（所有字段均可选）

```json
{ "name": "代码问答（改名）", "llm_query_mode": "hybrid" }
```

**响应** `200` — [`ProjectItem`](#projectitem)

**错误** `404` 项目不存在

### 1.5 删除项目

`DELETE /api/projects/{project_id}`

> 删除项目**不会级联删除**其下会话——这些会话的 `project_id` 会被置空，仍保留。

**响应** `200` — `null`

**错误** `404` 项目不存在

---

## 2. 会话 Sessions

### 2.1 列出会话

`GET /api/sessions`

**查询参数**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | string | 否 | 按项目过滤；不传则返回全部会话 |

**响应** `200` — [`SessionList`](#sessionlist)

> 也可用 `GET /api/projects/{project_id}/sessions` 获取指定项目下的会话，行为等价于带 `project_id` 过滤。

### 2.2 在项目下创建会话

`POST /api/projects/{project_id}/sessions`

> **去重逻辑**：若该项目下已存在空会话（无任何消息），直接复用并返回该会话，避免重复创建。

**响应** `200` — [`SessionItem`](#sessionitem)

**错误** `404` 项目不存在

### 2.3 获取会话详情（含全部消息）

`GET /api/sessions/{session_id}`

**响应** `200` — [`SessionDetail`](#sessiondetail)

```json
{
  "id": "sess_1a2b3c4d",
  "title": "如何解析 SSE 流",
  "project_id": "proj_a1b2c3d4",
  "created_at": "2026-07-03T08:00:00+00:00",
  "updated_at": "2026-07-03T08:30:00+00:00",
  "messages": [
    {
      "id": "msg_...",
      "session_id": "sess_1a2b3c4d",
      "role": "user",
      "content": "如何解析 SSE 流？",
      "total_ms": 0,
      "created_at": "2026-07-03T08:00:00+00:00"
    },
    {
      "id": "msg_...",
      "session_id": "sess_1a2b3c4d",
      "role": "assistant",
      "content": "可以用 ReadableStream ...",
      "total_ms": 1234,
      "created_at": "2026-07-03T08:00:02+00:00"
    }
  ]
}
```

**错误** `404` 会话不存在

### 2.4 删除会话

`DELETE /api/sessions/{session_id}`

级联删除该会话下的全部消息。

**响应** `200` — `null`

**错误** `404` 会话不存在

---

## 3. 查询（流式）Query / SSE

查询接口返回 `text/event-stream`，逐事件推送。事件定义见 [§6 SSE 事件协议](#6-sse-事件协议)。前端用 `fetch` + `ReadableStream` 消费。

### 3.1 无会话查询（向后兼容）

`POST /api/query`

**请求体** — [`QueryRequest`](#queryrequest)

```json
{ "query": "explain async iterators in Python" }
```

**响应** `200` — SSE 流

- 结果保存到旧版 `queries` 表（历史记录），见 [§4 历史](#4-历史-history)。
- 不携带会话上下文。

### 3.2 会话内查询

`POST /api/sessions/{session_id}/query`

**请求体** — [`SessionQueryRequest`](#sessionqueryrequest)

```json
{ "query": "再举一个例子" }
```

**响应** `200` — SSE 流

行为：

1. 先把用户消息落库（`role=user`）。
2. 若是会话首条消息，用其内容生成会话标题。
3. 取该会话历史消息作为 `conversation_history` 传给上游 LightRag。
4. 流结束后把完整助手回复落库（`role=assistant`，含 `total_ms`）。
5. `done` 事件回传 `session_id` 与 `message_id`。

**错误** `404` 会话不存在

---

## 4. 历史 History

> 历史记录来自无会话查询（§3.1）写入的旧版 `queries` 表。

### 4.1 分页获取历史

`GET /api/history`

**查询参数**

| 字段 | 类型 | 必填 | 默认 | 约束 |
|---|---|---|---|---|
| `page` | int | 否 | `1` | ≥ 1 |
| `size` | int | 否 | `20` | 1 ~ 100 |

**响应** `200` — [`HistoryPage`](#historypage)

```json
{
  "items": [
    {
      "id": "q_20260703_a1b2c3",
      "query": "explain async iterators in Python",
      "summary": "Python 的异步迭代器是 ...",
      "created_at": "2026-07-03T08:00:02+00:00",
      "total_ms": 1234
    }
  ],
  "total": 42,
  "page": 1,
  "size": 20
}
```

### 4.2 获取单条历史详情

`GET /api/history/{query_id}`

**响应** `200` — [`HistoryDetail`](#historydetail)（含完整 `full_answer`）

**错误** `404` 记录不存在

### 4.3 删除单条历史

`DELETE /api/history/{query_id}`

**响应** `200` — `null`

### 4.4 清空全部历史

`DELETE /api/history`

**响应** `200` — `null`

---

## 5. 健康检查

`GET /health`

**响应** `200`

```json
{ "status": "ok" }
```

---

## 6. SSE 事件协议

响应 `Content-Type: text/event-stream`，每个事件由 `event:` 和 `data:` 两行组成，事件之间以空行分隔：

```
event: started
data: {}

event: chunk
data: {"content":"Python"}

event: done
data: {"query_id":"q_20260703_a1b2c3","total_ms":1234,"session_id":"sess_1a2b3c4d","message_id":"msg_..."}
```

按时间顺序，一次查询可能下发的事件类型：

| event | data 结构 | 时机 | 说明 |
|---|---|---|---|
| `queued` | [`SSEQueuedData`](#ssequeueddata) | 仅当并发槽位已满、请求排队时 | 估算等待信息 |
| `started` | `{}` | 获得槽位、开始请求上游时 | 流开始 |
| `chunk` | [`SSEChunkData`](#ssechunkdata) | 上游每产出一小段文本 | 增量内容，需累加 |
| `done` | [`SSEDoneData`](#ssedonedata) | 流正常结束且已持久化 | 携带 `query_id` / `total_ms`，会话查询额外带 `session_id` / `message_id` |
| `error` | [`SSEErrorData`](#sseerrordata) | 上游故障或持久化异常 | 流终止 |

**消费示例（浏览器）**

```ts
const resp = await fetch("/api/sessions/sess_xxx/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: "你好" }),
});
const reader = resp.body!.getReader();
const decoder = new TextDecoder();
let buffer = "";
let answer = "";
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const frames = buffer.split("\n\n");
  buffer = frames.pop()!;
  for (const frame of frames) {
    // 解析 event: / data: 两行后分发处理
  }
}
```

**错误场景**：上游 401 → `上游认证失败，请检查 API Key`；429 → `上游速率限制，请稍后重试`；其它 4xx / 5xx 同样以 `error` 事件下发并终止流。

---

## 7. 数据模型

### 项目

<a id="projectcreate"></a>

**ProjectCreate**

| 字段 | 类型 | 默认 |
|---|---|---|
| `name` | string | — |
| `description` | string | `""` |
| `llm_api_url` | string | `""` |
| `llm_api_key` | string | `""` |
| `llm_query_mode` | string | `"mix"` |
| `prompt_template` | string | `"{query}"` |

<a id="projectupdate"></a>

**ProjectUpdate** — 所有字段可选（`Optional`），传 `null` 或缺省表示不更新。

<a id="projectitem"></a>

**ProjectItem**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | `proj_xxxxxxxx` |
| `name` | string | |
| `description` | string | |
| `llm_api_url` | string | |
| `llm_query_mode` | string | |
| `session_count` | int | 会话数 |
| `created_at` | string | ISO 时间 |
| `updated_at` | string | ISO 时间 |

<a id="projectlist"></a>

**ProjectList** — `{ "items": ProjectItem[] }`

### 会话

<a id="sessionitem"></a>

**SessionItem**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | `sess_xxxxxxxx` |
| `title` | string | 由首条消息生成 |
| `project_id` | string | 所属项目，无则为 `""` |
| `created_at` | string | |
| `updated_at` | string | |
| `msg_count` | int | 消息数 |

<a id="sessionlist"></a>

**SessionList** — `{ "items": SessionItem[] }`

<a id="messageitem"></a>

**MessageItem**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | `msg_xxxxxxxxxx` |
| `session_id` | string | |
| `role` | string | `"user"` \| `"assistant"` |
| `content` | string | |
| `total_ms` | int | 仅 assistant 有耗时 |
| `created_at` | string | |

<a id="sessiondetail"></a>

**SessionDetail**

| 字段 | 类型 |
|---|---|
| `id` | string |
| `title` | string |
| `project_id` | string |
| `created_at` | string |
| `updated_at` | string |
| `messages` | MessageItem[] |

### 查询请求

<a id="queryrequest"></a>

**QueryRequest** / <a id="sessionqueryrequest"></a>**SessionQueryRequest**

| 字段 | 类型 | 说明 |
|---|---|---|
| `query` | string | 用户输入 |

### 历史

<a id="historyitem"></a>

**HistoryItem** — `id`、`query`、`summary`、`created_at`、`total_ms`

<a id="historydetail"></a>

**HistoryDetail** — 在 `HistoryItem` 基础上增加 `full_answer`

<a id="historypage"></a>

**HistoryPage** — `{ items: HistoryItem[], total: int, page: int, size: int }`

### SSE 事件 data

<a id="ssequeueddata"></a>

**SSEQueuedData** — `{ position: int, estimated_wait_ms: int }`

<a id="ssechunkdata"></a>

**SSEChunkData** — `{ content: string }`

<a id="ssedonedata"></a>

**SSEDoneData** — `{ query_id: string, total_ms: int, session_id: string, message_id: string }`

<a id="sseerrordata"></a>

**SSEErrorData** — `{ message: string }`
