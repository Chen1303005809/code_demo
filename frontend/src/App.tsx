import React, { useCallback, useRef, useState } from "react";
import QueryInput from "./components/QueryInput";
import ChatView from "./components/ChatView";
import ProjectSelector from "./components/ProjectSelector";
import SessionSidebar from "./components/SessionSidebar";
import type { MessageItem, ProjectItem, SSEEvent } from "./lib/types";
import { fetchSession, streamSessionQuery } from "./lib/api";

type QueryState =
  | { phase: "idle" }
  | { phase: "queued"; position: number }
  | { phase: "streaming" }
  | { phase: "done"; queryId: string; totalMs: number }
  | { phase: "error"; message: string };

// ── 每个会话独立的状态 ────────────────────────────

interface SessionData {
  messages: MessageItem[];
  streamingContent: string;
  queryState: QueryState;
  loaded: boolean; // 是否已从后端加载过消息
}

function emptySession(): SessionData {
  return {
    messages: [],
    streamingContent: "",
    queryState: { phase: "idle" },
    loaded: false,
  };
}

// ── 辅助：更新 sessionMap 中某个会话的部分字段 ─────

function updateSession(
  prev: Record<string, SessionData>,
  sid: string,
  patch: Partial<SessionData>
): Record<string, SessionData> {
  const cur = prev[sid] ?? emptySession();
  return { ...prev, [sid]: { ...cur, ...patch } };
}

export default function App() {
  // ── 核心状态：按会话隔离 ──────────────────────────
  const [sessionMap, setSessionMap] = useState<Record<string, SessionData>>({});
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);

  // 同步 refs：SSE 回调中需要实时读写，避免闭包陈旧值
  const streamingRefs = useRef<Record<string, string>>({});
  const abortCtrls = useRef<Record<string, AbortController>>({});

  // 侧边栏刷新 key
  const [sessionListKey, setSessionListKey] = useState(0);

  // ── 派生：当前活跃会话的展示数据 ──────────────────

  const current = activeSessionId
    ? (sessionMap[activeSessionId] ?? emptySession())
    : null;

  const displayMessages = current?.messages ?? [];
  const displayStreaming = current?.streamingContent ?? "";
  const displayState = current?.queryState ?? { phase: "idle" as const };

  // ── 项目切换 ────────────────────────────────────────

  const handleSelectProject = useCallback((project: ProjectItem) => {
    setActiveProjectId(project.id);
    // 切换项目时清空当前会话
    setActiveSessionId(null);
    setSessionMap({});
    setSessionListKey((k) => k + 1);
  }, []);

  const handleProjectRefresh = useCallback(() => {
    setActiveProjectId(null);
    setActiveSessionId(null);
    setSessionMap({});
    setSessionListKey((k) => k + 1);
  }, []);

  // ── 加载会话消息（仅首次、或后端有更新时）─────────

  const ensureSessionLoaded = useCallback(async (sessionId: string) => {
    const cached = sessionMap[sessionId];
    if (cached?.loaded) return;

    try {
      const detail = await fetchSession(sessionId);
      setSessionMap((prev) =>
        updateSession(prev, sessionId, {
          messages: detail.messages,
          streamingContent: "",
          queryState: { phase: "idle" },
          loaded: true,
        })
      );
      delete streamingRefs.current[sessionId];
    } catch {
      setSessionMap((prev) =>
        updateSession(prev, sessionId, {
          messages: [],
          loaded: true,
        })
      );
    }
  }, [sessionMap]);

  // ── 选择会话：只切换 activeId，不中止流 ──────────

  const handleSelectSession = useCallback(
    (id: string) => {
      setActiveSessionId(id);
      ensureSessionLoaded(id);
    },
    [ensureSessionLoaded]
  );

  // ── 新建会话 ───────────────────────────────────────

  const handleNewSession = useCallback((id: string) => {
    setSessionMap((prev) => updateSession(prev, id, { ...emptySession(), loaded: true }));
    setActiveSessionId(id);
  }, []);

  // ── 发送查询 ───────────────────────────────────────

  const handleQuery = useCallback(
    (query: string) => {
      if (!activeSessionId) return;
      const sid = activeSessionId;

      // 取消该会话上一次请求
      abortCtrls.current[sid]?.abort();
      const ctrl = new AbortController();
      abortCtrls.current[sid] = ctrl;

      // 重置该会话的流式状态
      streamingRefs.current[sid] = "";
      setSessionMap((prev) =>
        updateSession(prev, sid, {
          streamingContent: "",
          queryState: { phase: "idle" },
        })
      );

      // 乐观添加用户消息
      const tempUserMsg: MessageItem = {
        id: "temp-" + Date.now(),
        session_id: sid,
        role: "user",
        content: query,
        total_ms: 0,
        created_at: new Date().toISOString(),
      };
      setSessionMap((prev) =>
        updateSession(prev, sid, {
          messages: [...(prev[sid]?.messages ?? []), tempUserMsg],
        })
      );

      streamSessionQuery(
        sid,
        query,
        (ev: SSEEvent) => {
          switch (ev.type) {
            case "queued":
              setSessionMap((prev) =>
                updateSession(prev, sid, {
                  queryState: {
                    phase: "queued",
                    position: ev.data.position,
                  },
                })
              );
              break;
            case "started":
              setSessionMap((prev) =>
                updateSession(prev, sid, {
                  queryState: { phase: "streaming" },
                })
              );
              break;
            case "chunk": {
              const acc = (streamingRefs.current[sid] ?? "") + ev.data.content;
              streamingRefs.current[sid] = acc;
              setSessionMap((prev) =>
                updateSession(prev, sid, {
                  streamingContent: acc,
                })
              );
              break;
            }
            case "done": {
              setSessionMap((prev) =>
                updateSession(prev, sid, {
                  queryState: {
                    phase: "done",
                    queryId: ev.data.query_id,
                    totalMs: ev.data.total_ms,
                  },
                })
              );

              const finalContent = streamingRefs.current[sid] ?? "";
              if (finalContent) {
                const assistantMsg: MessageItem = {
                  id: ev.data.message_id || "msg-" + Date.now(),
                  session_id: sid,
                  role: "assistant",
                  content: finalContent,
                  total_ms: ev.data.total_ms,
                  created_at: new Date().toISOString(),
                };
                setSessionMap((prev) => {
                  const cur = prev[sid] ?? emptySession();
                  const filtered = cur.messages.filter(
                    (m) => m.role === "assistant" || !m.id.startsWith("temp-")
                  );
                  return updateSession(prev, sid, {
                    messages: [...filtered, assistantMsg],
                    streamingContent: "",
                    loaded: true,
                  });
                });
              }

              delete streamingRefs.current[sid];
              setSessionListKey((k) => k + 1);
              break;
            }
            case "error":
              setSessionMap((prev) =>
                updateSession(prev, sid, {
                  queryState: {
                    phase: "error",
                    message: ev.data.message,
                  },
                })
              );
              break;
          }
        },
        ctrl.signal
      );
    },
    [activeSessionId]
  );

  // ── 取消当前会话的请求 ────────────────────────────

  const handleCancel = useCallback(() => {
    if (!activeSessionId) return;
    const sid = activeSessionId;
    abortCtrls.current[sid]?.abort();
    delete abortCtrls.current[sid];
    delete streamingRefs.current[sid];
    setSessionMap((prev) =>
      updateSession(prev, sid, {
        streamingContent: "",
        queryState: { phase: "idle" },
      })
    );
  }, [activeSessionId]);

  // ── 会话列表刷新回调（删除当前会话等触发）─────────

  const handleRefreshSessions = useCallback(() => {
    // 中止所有进行中的流
    for (const ctrl of Object.values(abortCtrls.current)) {
      ctrl.abort();
    }
    abortCtrls.current = {};
    streamingRefs.current = {};
    setSessionMap({});
    setActiveSessionId(null);
  }, []);

  // ── 渲染 ───────────────────────────────────────────

  return (
    <div style={{ display: "flex", height: "100vh", flexDirection: "column" }}>
      {/* 标题栏 */}
      <header
        style={{
          background: "#1a1a2e",
          color: "#e0e0e0",
          padding: "10px 20px",
          fontSize: 18,
          fontWeight: 600,
          letterSpacing: 1,
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <span>🔍 LLM 查询面板</span>
        <ProjectSelector
          activeProjectId={activeProjectId}
          onSelect={handleSelectProject}
          onRefresh={handleProjectRefresh}
        />
      </header>

      {/* 主体 */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <SessionSidebar
          key={sessionListKey}
          activeId={activeSessionId}
          projectId={activeProjectId}
          onSelect={handleSelectSession}
          onNew={handleNewSession}
          onRefresh={handleRefreshSessions}
        />
        <main
          style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}
        >
          {activeSessionId ? (
            <>
              <QueryInput
                key={activeSessionId}
                onQuery={handleQuery}
                onCancel={handleCancel}
                disabled={
                  displayState.phase === "streaming" || displayState.phase === "queued"
                }
              />
              <ChatView
                messages={displayMessages}
                streamingContent={displayStreaming}
                state={displayState}
              />
            </>
          ) : (
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#999",
                fontSize: 15,
                flexDirection: "column",
                gap: 8,
              }}
            >
              {activeProjectId ? (
                <>
                  <p>👈 选择一个会话或创建新会话开始对话</p>
                  <p style={{ fontSize: 13 }}>
                    每个会话是独立的对话线程，会自动保存全部消息。
                  </p>
                </>
              ) : (
                <>
                  <p>📁 请先在顶部选择一个项目</p>
                  <p style={{ fontSize: 13 }}>
                    不同项目可以关联不同的资料库（LightRag 实例）。
                  </p>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
