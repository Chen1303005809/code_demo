import React from "react";

type QueryState =
  | { phase: "idle" }
  | { phase: "queued"; position: number }
  | { phase: "streaming" }
  | { phase: "done"; queryId: string; totalMs: number }
  | { phase: "error"; message: string };

interface Props {
  state: QueryState;
  activeSessionId: string | null;
}

export default function StatusBar({ state, activeSessionId }: Props) {
  const renderContent = () => {
    switch (state.phase) {
      case "idle":
        return <span style={{ color: "#666" }}>就绪</span>;
      case "queued":
        return (
          <span style={{ color: "#f39c12" }}>
            排队中（前面{state.position}人）...
          </span>
        );
      case "streaming":
        return <span style={{ color: "#3498db" }}>接收中...</span>;
      case "done":
        return (
          <span style={{ color: "#27ae60" }}>
            ✓ 完成 · 耗时 {state.totalMs}ms
          </span>
        );
      case "error":
        return <span style={{ color: "#e74c3c" }}>✕ {state.message}</span>;
    }
  };

  return (
    <footer
      style={{
        borderTop: "1px solid #e0e0e0",
        padding: "6px 16px",
        background: "#fafafa",
        fontSize: 13,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div>{renderContent()}</div>
      <div style={{ color: "#aaa", fontSize: 12 }}>
        {activeSessionId ? `会话: ${activeSessionId}` : "未选择会话"}
      </div>
    </footer>
  );
}
