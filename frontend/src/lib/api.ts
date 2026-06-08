/**
 * API 层 —— SSE 连接 + REST fetch 封装。
 */

import type {
  HistoryDetail,
  HistoryPage,
  SSEEvent,
  SSEEventType,
  SessionDetail,
  SessionItem,
  SessionList,
} from "./types";

// ── SSE 查询 ───────────────────────────────────────

/** 发起 SSE 查询（无会话），回调每个事件 */
export function streamQuery(
  query: string,
  onEvent: (ev: SSEEvent) => void,
  signal: AbortSignal
): void {
  void (async () => {
    try {
      const resp = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        signal,
      });
      if (!resp.ok) {
        onEvent({ type: "error", data: { message: `HTTP ${resp.status}` } });
        return;
      }
      await readSSEStream(resp, onEvent);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      onEvent({
        type: "error",
        data: { message: "网络连接失败，请检查后端服务是否启动。" },
      });
    }
  })();
}

/** 发起 SSE 查询（会话内），回调每个事件 */
export function streamSessionQuery(
  sessionId: string,
  query: string,
  onEvent: (ev: SSEEvent) => void,
  signal: AbortSignal
): void {
  void (async () => {
    try {
      const resp = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        signal,
      });
      if (!resp.ok) {
        onEvent({ type: "error", data: { message: `HTTP ${resp.status}` } });
        return;
      }
      await readSSEStream(resp, onEvent);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      onEvent({
        type: "error",
        data: { message: "网络连接失败，请检查后端服务是否启动。" },
      });
    }
  })();
}

// ── 会话 ───────────────────────────────────────────

export async function fetchSessions(): Promise<SessionList> {
  const resp = await fetch("/api/sessions");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function createSession(): Promise<SessionItem> {
  const resp = await fetch("/api/sessions", { method: "POST" });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function fetchSession(sessionId: string): Promise<SessionDetail> {
  const resp = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const resp = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
}

// ── 历史（向后兼容）────────────────────────────────

export async function fetchHistory(
  page: number = 1,
  size: number = 20
): Promise<HistoryPage> {
  const resp = await fetch(`/api/history?page=${page}&size=${size}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function fetchHistoryDetail(id: string): Promise<HistoryDetail> {
  const resp = await fetch(`/api/history/${encodeURIComponent(id)}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export async function deleteHistoryItem(id: string): Promise<void> {
  const resp = await fetch(`/api/history/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
}

export async function deleteAllHistory(): Promise<void> {
  const resp = await fetch("/api/history", { method: "DELETE" });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
}

// ── SSE 流解析 ─────────────────────────────────────

async function readSSEStream(
  resp: Response,
  onEvent: (ev: SSEEvent) => void
): Promise<void> {
  if (!resp.body) return;

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop()!;

    for (const frame of parts) {
      const parsed = parseSSEFrame(frame);
      if (parsed) onEvent(parsed);
    }
  }
}

function parseSSEFrame(frame: string): SSEEvent | null {
  const lines = frame.split("\n");
  let eventType: SSEEventType | null = null;
  let dataStr = "";

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim() as SSEEventType;
    } else if (line.startsWith("data:")) {
      dataStr = line.slice(5).trim();
    }
  }

  if (!eventType) return null;

  switch (eventType) {
    case "queued":
      return { type: "queued", data: JSON.parse(dataStr) };
    case "started":
      return { type: "started" };
    case "chunk":
      return { type: "chunk", data: JSON.parse(dataStr) };
    case "done":
      return { type: "done", data: JSON.parse(dataStr) };
    case "error":
      return { type: "error", data: JSON.parse(dataStr) };
    default:
      return null;
  }
}
