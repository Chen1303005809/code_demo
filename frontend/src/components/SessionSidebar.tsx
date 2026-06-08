import React, { useEffect, useState } from "react";
import {
  fetchSessions,
  createSession,
  deleteSession,
} from "../lib/api";
import type { SessionItem } from "../lib/types";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: (id: string) => void;
  onRefresh: () => void;
}

export default function SessionSidebar({ activeId, onSelect, onNew, onRefresh }: Props) {
  const [items, setItems] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchSessions();
      setItems(data.items);
    } catch {
      setError("加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // 暴露刷新方法给父组件
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__sessionSidebarReload = load;
    return () => {
      delete (window as unknown as Record<string, unknown>).__sessionSidebarReload;
    };
  }, []);

  const handleNew = async () => {
    try {
      const sess = await createSession();
      setItems((prev) => [sess, ...prev]);
      onNew(sess.id);
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteSession(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
      if (activeId === id) {
        onRefresh();
      }
    } catch {
      /* ignore */
    }
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      if (diffMin < 1) return "刚刚";
      if (diffMin < 60) return `${diffMin}分钟前`;
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}小时前`;
      return d.toLocaleDateString("zh-CN");
    } catch {
      return "";
    }
  };

  return (
    <aside
      style={{
        width: 260,
        borderRight: "1px solid #e0e0e0",
        display: "flex",
        flexDirection: "column",
        background: "#f8f9fa",
      }}
    >
      {/* 标题行 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 12px",
          borderBottom: "1px solid #e0e0e0",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        <span>💬 会话列表</span>
        <button
          onClick={handleNew}
          style={{
            background: "#3498db",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 12,
            padding: "3px 10px",
          }}
        >
          ＋ 新建
        </button>
      </div>

      {/* 列表 */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {loading && (
          <p style={{ padding: 12, color: "#999", fontSize: 13 }}>加载中...</p>
        )}
        {error && (
          <p style={{ padding: 12, color: "#e74c3c", fontSize: 13 }}>{error}</p>
        )}
        {!loading &&
          !error &&
          items.map((item) => (
            <div
              key={item.id}
              onClick={() => onSelect(item.id)}
              style={{
                padding: "10px 12px",
                borderBottom: "1px solid #eee",
                cursor: "pointer",
                fontSize: 13,
                background: activeId === item.id ? "#e8f4fd" : "transparent",
                borderLeft:
                  activeId === item.id ? "3px solid #3498db" : "3px solid transparent",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    flex: 1,
                    fontWeight: activeId === item.id ? 600 : 400,
                  }}
                  title={item.title}
                >
                  {item.title}
                </span>
                <button
                  onClick={(e) => handleDelete(item.id, e)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#bbb",
                    cursor: "pointer",
                    fontSize: 12,
                    padding: "0 0 0 8px",
                  }}
                  title="删除会话"
                >
                  ✕
                </button>
              </div>
              <div
                style={{
                  color: "#888",
                  fontSize: 11,
                  marginTop: 4,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span>
                  {item.msg_count > 0
                    ? `${item.msg_count} 条消息`
                    : "空会话"}
                </span>
                <span>{formatTime(item.updated_at)}</span>
              </div>
            </div>
          ))}
        {!loading && !error && items.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "#999", fontSize: 13 }}>
            <p style={{ marginBottom: 12 }}>暂无会话</p>
            <button
              onClick={handleNew}
              style={{
                background: "#3498db",
                color: "#fff",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
                fontSize: 13,
                padding: "6px 16px",
              }}
            >
              创建第一个会话
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
