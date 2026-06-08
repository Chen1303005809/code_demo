import React, { useEffect, useState } from "react";
import { fetchHistory, deleteHistoryItem, deleteAllHistory } from "../lib/api";
import type { HistoryItem } from "../lib/types";

interface Props {
  onSelect: (content: string) => void;
}

export default function HistorySidebar({ onSelect }: Props) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const page = await fetchHistory(1, 50);
      setItems(page.items);
    } catch {
      setError("加载历史失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteHistoryItem(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
    } catch {
      /* ignore */
    }
  };

  const handleClearAll = async () => {
    if (!confirm("确认清空全部历史记录？")) return;
    try {
      await deleteAllHistory();
      setItems([]);
    } catch {
      /* ignore */
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
        <span>历史记录</span>
        {items.length > 0 && (
          <button
            onClick={handleClearAll}
            style={{
              background: "none",
              border: "none",
              color: "#c0392b",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            清空
          </button>
        )}
      </div>

      {/* 列表 */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {loading && (
          <p style={{ padding: 12, color: "#999", fontSize: 13 }}>
            加载中...
          </p>
        )}
        {error && (
          <p style={{ padding: 12, color: "#e74c3c", fontSize: 13 }}>
            {error}
          </p>
        )}
        {!loading &&
          !error &&
          items.map((item) => (
            <div
              key={item.id}
              onClick={() => onSelect(item.query)}
              style={{
                padding: "8px 12px",
                borderBottom: "1px solid #eee",
                cursor: "pointer",
                fontSize: 13,
              }}
              title={item.query}
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
                  }}
                >
                  {item.query}
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
                  title="删除"
                >
                  ✕
                </button>
              </div>
              <div
                style={{
                  color: "#888",
                  fontSize: 11,
                  marginTop: 2,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {item.summary}
              </div>
            </div>
          ))}
        {!loading && !error && items.length === 0 && (
          <p style={{ padding: 12, color: "#999", fontSize: 13 }}>
            暂无历史记录
          </p>
        )}
      </div>
    </aside>
  );
}
