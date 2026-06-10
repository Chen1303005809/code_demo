/** 前端类型定义，与后端 Pydantic 模型对应 */

export interface QueryRequest {
  query: string;
}

// ── 项目 ──────────────────────────────────────────

export interface ProjectCreate {
  name: string;
  description?: string;
  llm_api_url?: string;
  llm_api_key?: string;
  llm_query_mode?: string;
  prompt_template?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  llm_api_url?: string;
  llm_api_key?: string;
  llm_query_mode?: string;
  prompt_template?: string;
}

export interface ProjectItem {
  id: string;
  name: string;
  description: string;
  llm_api_url: string;
  llm_query_mode: string;
  session_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  items: ProjectItem[];
}

// ── 会话 ──────────────────────────────────────────

export interface SessionItem {
  id: string;
  title: string;
  project_id: string;
  created_at: string;
  updated_at: string;
  msg_count: number;
}

export interface SessionList {
  items: SessionItem[];
}

export interface MessageItem {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  total_ms: number;
  created_at: string;
}

export interface SessionDetail {
  id: string;
  title: string;
  project_id: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
}

// ── 历史（向后兼容）──────────────────────────────

export interface HistoryItem {
  id: string;
  query: string;
  summary: string;
  created_at: string;
  total_ms: number;
}

export interface HistoryDetail {
  id: string;
  query: string;
  summary: string;
  full_answer: string;
  created_at: string;
  total_ms: number;
}

export interface HistoryPage {
  items: HistoryItem[];
  total: number;
  page: number;
  size: number;
}

// ── SSE 事件 ──────────────────────────────────────

export type SSEEventType = "queued" | "started" | "chunk" | "done" | "error";

export interface SSEQueuedData {
  position: number;
  estimated_wait_ms: number;
}

export interface SSEChunkData {
  content: string;
}

export interface SSEDoneData {
  query_id: string;
  total_ms: number;
  session_id: string;
  message_id: string;
}

export interface SSEErrorData {
  message: string;
}

export type SSEEvent =
  | { type: "queued"; data: SSEQueuedData }
  | { type: "started" }
  | { type: "chunk"; data: SSEChunkData }
  | { type: "done"; data: SSEDoneData }
  | { type: "error"; data: SSEErrorData };
