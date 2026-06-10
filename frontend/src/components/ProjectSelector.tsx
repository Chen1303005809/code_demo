import React, { useEffect, useState } from "react";
import {
  fetchProjects,
  createProject,
  deleteProject,
} from "../lib/api";
import type { ProjectItem, ProjectCreate } from "../lib/types";

interface Props {
  activeProjectId: string | null;
  onSelect: (project: ProjectItem) => void;
  onRefresh: () => void;
}

export default function ProjectSelector({ activeProjectId, onSelect, onRefresh }: Props) {
  const [items, setItems] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // 新建表单
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formMode, setFormMode] = useState("mix");
  const [formDesc, setFormDesc] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchProjects();
      setItems(data.items);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    const name = formName.trim();
    if (!name) return;
    const data: ProjectCreate = {
      name,
      description: formDesc.trim(),
      llm_api_url: formUrl.trim(),
      llm_query_mode: formMode.trim() || "mix",
    };
    try {
      await createProject(data);
      setShowCreate(false);
      setFormName("");
      setFormUrl("");
      setFormMode("mix");
      setFormDesc("");
      load();
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("删除项目？其下的会话不会删除，但会变为无归属状态。")) return;
    try {
      await deleteProject(projectId);
      if (activeProjectId === projectId) {
        onRefresh();
      }
      load();
    } catch {
      /* ignore */
    }
  };

  const activeName = items.find((p) => p.id === activeProjectId)?.name ?? "选择项目";

  return (
    <div style={{ position: "relative" }}>
      {/* 选择器按钮 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            background: "#2a2a4a",
            color: "#e0e0e0",
            border: "1px solid #444",
            borderRadius: 6,
            padding: "4px 12px",
            cursor: "pointer",
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 4,
            minWidth: 120,
          }}
        >
          <span style={{ opacity: 0.6 }}>📁</span>
          <span style={{ flex: 1, textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {activeProjectId ? activeName : "选择项目"}
          </span>
          <span style={{ fontSize: 10 }}>{expanded ? "▲" : "▼"}</span>
        </button>
        <button
          onClick={() => setShowCreate(true)}
          style={{
            background: "none",
            border: "1px solid #555",
            color: "#aaa",
            borderRadius: 6,
            padding: "4px 8px",
            cursor: "pointer",
            fontSize: 12,
          }}
          title="新建项目"
        >
          ＋
        </button>
      </div>

      {/* 下拉列表 */}
      {expanded && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            marginTop: 4,
            background: "#1e1e2e",
            border: "1px solid #444",
            borderRadius: 8,
            minWidth: 240,
            maxHeight: 300,
            overflow: "auto",
            zIndex: 100,
            boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          }}
        >
          {loading && (
            <p style={{ padding: 12, color: "#888", fontSize: 12 }}>加载中...</p>
          )}
          {!loading && items.length === 0 && (
            <p style={{ padding: 12, color: "#888", fontSize: 12 }}>
              暂无项目，点击 ＋ 新建
            </p>
          )}
          {!loading &&
            items.map((p) => (
              <div
                key={p.id}
                onClick={() => {
                  onSelect(p);
                  setExpanded(false);
                }}
                style={{
                  padding: "8px 12px",
                  cursor: "pointer",
                  fontSize: 13,
                  color: "#d0d0d0",
                  background: p.id === activeProjectId ? "#2a2a4a" : "transparent",
                  borderLeft:
                    p.id === activeProjectId ? "3px solid #3498db" : "3px solid transparent",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ flex: 1, overflow: "hidden" }}>
                  <div
                    style={{
                      fontWeight: p.id === activeProjectId ? 600 : 400,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {p.name}
                  </div>
                  <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>
                    {p.llm_query_mode} · {p.session_count} 会话
                    {p.llm_api_url && ` · ${p.llm_api_url}`}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(p.id, e)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#666",
                    cursor: "pointer",
                    fontSize: 12,
                    padding: "2px 4px",
                  }}
                  title="删除项目"
                >
                  ✕
                </button>
              </div>
            ))}
        </div>
      )}

      {/* 新建项目弹窗 */}
      {showCreate && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 200,
          }}
          onClick={() => setShowCreate(false)}
        >
          <div
            style={{
              background: "#1e1e2e",
              border: "1px solid #444",
              borderRadius: 12,
              padding: 24,
              minWidth: 360,
              maxWidth: 460,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 16px", color: "#e0e0e0", fontSize: 16 }}>
              📁 新建项目
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <label style={{ color: "#aaa", fontSize: 12 }}>
                项目名称 *
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="例如：项目 A"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "6px 10px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #555",
                    background: "#2a2a3a",
                    color: "#e0e0e0",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </label>
              <label style={{ color: "#aaa", fontSize: 12 }}>
                LightRag 地址
                <input
                  type="text"
                  value={formUrl}
                  onChange={(e) => setFormUrl(e.target.value)}
                  placeholder="例如：http://127.0.0.1:9621"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "6px 10px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #555",
                    background: "#2a2a3a",
                    color: "#e0e0e0",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </label>
              <label style={{ color: "#aaa", fontSize: 12 }}>
                查询模式
                <select
                  value={formMode}
                  onChange={(e) => setFormMode(e.target.value)}
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "6px 10px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #555",
                    background: "#2a2a3a",
                    color: "#e0e0e0",
                    fontSize: 13,
                    outline: "none",
                  }}
                >
                  <option value="mix">mix</option>
                  <option value="hybrid">hybrid</option>
                  <option value="local">local</option>
                  <option value="global">global</option>
                  <option value="naive">naive</option>
                </select>
              </label>
              <label style={{ color: "#aaa", fontSize: 12 }}>
                描述
                <input
                  type="text"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="可选"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "6px 10px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #555",
                    background: "#2a2a3a",
                    color: "#e0e0e0",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </label>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button
                onClick={() => setShowCreate(false)}
                style={{
                  padding: "6px 16px",
                  borderRadius: 6,
                  border: "1px solid #555",
                  background: "transparent",
                  color: "#aaa",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                style={{
                  padding: "6px 20px",
                  borderRadius: 6,
                  border: "none",
                  background: "#3498db",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
