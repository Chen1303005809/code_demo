import React, { useCallback, useRef, useState } from "react";
import QueryInput from "./components/QueryInput";
import ChatView from "./components/ChatView";
import SessionSidebar from "./components/SessionSidebar";
import StatusBar from "./components/StatusBar";
import type { MessageItem, SSEEvent } from "./lib/types";
import { fetchSession, streamSessionQuery } from "./lib/api";

type QueryState =
  | { phase: "idle" }
  | { phase: "queued"; position: number }
  | { phase: "streaming" }
  | { phase: "done"; queryId: string; totalMs: number }
  | { phase: "error"; message: string };

export default function App() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const streamingRef = useRef(""); // 实时累计，避免闭包陈旧值
  const [state, setState] = useState<QueryState>({ phase: "idle" });
  const [abortCtrl, setAbortCtrl] = useState<AbortController | null>(null);
  const [sessionListKey, setSessionListKey] = useState(0);

  // ── 加载会话消息 ───────────────────────────────────

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const detail = await fetchSession(sessionId);
      setMessages(detail.messages);
      setStreamingContent("");
      streamingRef.current = "";
      setState({ phase: "idle" });
    } catch {
      setMessages([]);
    }
  }, []);

  // ── 选择会话 ───────────────────────────────────────

  const handleSelectSession = useCallback(
    (id: string) => {
      setActiveSessionId(id);
      loadSession(id);
    },
    [loadSession]
  );

  // ── 新建会话 ───────────────────────────────────────

  const handleNewSession = useCallback((id: string) => {
    setActiveSessionId(id);
    setMessages([]);
    setStreamingContent("");
    streamingRef.current = "";
    setState({ phase: "idle" });
  }, []);

  // ── 发送查询 ───────────────────────────────────────

  const handleQuery = useCallback(
    (query: string) => {
      if (!activeSessionId) return;

      // 取消上一次请求
      abortCtrl?.abort();
      const ctrl = new AbortController();
      setAbortCtrl(ctrl);
      setStreamingContent("");
      streamingRef.current = "";
      setState({ phase: "idle" });

      // 乐观添加到消息列表
      const tempUserMsg: MessageItem = {
        id: "temp-" + Date.now(),
        session_id: activeSessionId,
        role: "user",
        content: query,
        total_ms: 0,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);

      streamSessionQuery(
        activeSessionId,
        query,
        (ev: SSEEvent) => {
          switch (ev.type) {
            case "queued":
              setState({
                phase: "queued",
                position: ev.data.position,
              });
              break;
            case "started":
              setState({ phase: "streaming" });
              break;
            case "chunk":
              streamingRef.current += ev.data.content;
              setStreamingContent(streamingRef.current);
              break;
            case "done": {
              setState({
                phase: "done",
                queryId: ev.data.query_id,
                totalMs: ev.data.total_ms,
              });

              const finalContent = streamingRef.current;
              if (finalContent) {
                const assistantMsg: MessageItem = {
                  id: ev.data.message_id || "msg-" + Date.now(),
                  session_id: activeSessionId,
                  role: "assistant",
                  content: finalContent,
                  total_ms: ev.data.total_ms,
                  created_at: new Date().toISOString(),
                };
                setMessages((prev) => {
                  const filtered = prev.filter(
                    (m) => m.role === "assistant" || !m.id.startsWith("temp-")
                  );
                  return [...filtered, assistantMsg];
                });
              }

              setStreamingContent("");
              streamingRef.current = "";
              // 刷新会话列表（消息数已更新）
              setSessionListKey((k) => k + 1);
              break;
            }
            case "error":
              setState({ phase: "error", message: ev.data.message });
              break;
          }
        },
        ctrl.signal
      );
    },
    [activeSessionId, abortCtrl]
  );

  const handleCancel = useCallback(() => {
    abortCtrl?.abort();
    setAbortCtrl(null);
    setState({ phase: "idle" });
    setStreamingContent("");
    streamingRef.current = "";
  }, [abortCtrl]);

  // ── 会话列表刷新回调 ──────────────────────────────

  const handleRefreshSessions = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setStreamingContent("");
    streamingRef.current = "";
    setState({ phase: "idle" });
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
        }}
      >
        🔍 LLM 查询面板
      </header>

      {/* 主体 */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <SessionSidebar
          key={sessionListKey}
          activeId={activeSessionId}
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
                onQuery={handleQuery}
                onCancel={handleCancel}
                disabled={
                  state.phase === "streaming" || state.phase === "queued"
                }
              />
              <ChatView messages={messages} streamingContent={streamingContent} />
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
              <p>👈 选择一个会话或创建新会话开始对话</p>
              <p style={{ fontSize: 13 }}>
                每个会话是独立的对话线程，会自动保存全部消息。
              </p>
            </div>
          )}
        </main>
      </div>

      <StatusBar state={state} activeSessionId={activeSessionId} />
    </div>
  );
}
