import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MessageItem } from "../lib/types";

interface Props {
  messages: MessageItem[];
  streamingContent: string;
}

// ── 思考标签解析 ──────────────────────────────────────────

interface ContentBlock {
  type: "markdown" | "thinking";
  content: string;
}

function parseContentBlocks(raw: string): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const thinkRegex = /(?:thinking|思考)\s*([\s\S]*?)\s*/gi;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = thinkRegex.exec(raw)) !== null) {
    const before = raw.slice(lastIndex, match.index);
    if (before.trim()) {
      blocks.push({ type: "markdown", content: before });
    }
    const thinkContent = match[1].trim();
    if (thinkContent) {
      blocks.push({ type: "thinking", content: thinkContent });
    }
    lastIndex = match.index + match[0].length;
  }

  const tail = raw.slice(lastIndex);
  if (tail.trim()) {
    blocks.push({ type: "markdown", content: tail });
  }

  if (blocks.length === 0) {
    blocks.push({ type: "markdown", content: raw });
  }

  return blocks;
}

// ── 思考折叠组件 ──────────────────────────────────────────

const ThinkingBlock: React.FC<{ content: string }> = ({ content }) => {
  const preview =
    content.length > 80 ? content.slice(0, 80).replace(/\n/g, " ") + "…" : content;

  return (
    <details
      style={{
        margin: "8px 0",
        border: "1px solid #d4a574",
        borderRadius: 8,
        background: "#fdf6ec",
        overflow: "hidden",
      }}
    >
      <summary
        style={{
          padding: "6px 12px",
          cursor: "pointer",
          fontWeight: 600,
          fontSize: 12,
          color: "#b07d44",
          background: "#fef0db",
          borderBottom: "1px solid #f0dbb8",
          userSelect: "none",
        }}
      >
        💭 思考过程 · {preview}
      </summary>
      <div
        style={{
          padding: "8px 14px",
          fontSize: 12,
          color: "#5c4a2e",
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {content}
      </div>
    </details>
  );
};

// ── Markdown 渲染 ────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const markdownComponents: any = {
  pre: (props: any) => (
    <pre
      style={{
        background: "#1e1e2e",
        color: "#cdd6f4",
        padding: 12,
        borderRadius: 8,
        overflow: "auto",
        fontSize: 13,
      }}
    >
      {props.children}
    </pre>
  ),
  code: (props: any) =>
    props.className ? (
      <code className={props.className}>{props.children}</code>
    ) : (
      <code
        style={{
          background: "#f0f0f0",
          padding: "2px 6px",
          borderRadius: 4,
          fontSize: 13,
        }}
      >
        {props.children}
      </code>
    ),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  table: (props: any) => (
    <table style={{ borderCollapse: "collapse", width: "100%", margin: "8px 0" }}>
      {props.children}
    </table>
  ),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  th: (props: any) => (
    <th
      style={{
        border: "1px solid #ddd",
        padding: "6px 12px",
        background: "#f5f5f5",
        textAlign: "left",
      }}
    >
      {props.children}
    </th>
  ),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  td: (props: any) => (
    <td style={{ border: "1px solid #ddd", padding: "6px 12px" }}>{props.children}</td>
  ),
};

// ── 内容渲染（含思考折叠）────────────────────────────────

const RenderedContent: React.FC<{ content: string }> = ({ content }) => {
  const blocks = parseContentBlocks(content);

  return (
    <>
      {blocks.map((block, i) =>
        block.type === "thinking" ? (
          <ThinkingBlock key={i} content={block.content} />
        ) : (
          <ReactMarkdown key={i} remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {block.content}
          </ReactMarkdown>
        )
      )}
    </>
  );
};

// ── 主组件 ────────────────────────────────────────────────

export default function ChatView({ messages, streamingContent }: Props) {
  if (messages.length === 0 && !streamingContent) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#999",
          fontSize: 14,
        }}
      >
        <p>输入问题，开始对话。</p>
      </div>
    );
  }

  return (
    <div
      style={{
        flex: 1,
        overflow: "auto",
        padding: "16px 24px",
      }}
    >
      {messages.map((msg) => (
        <div
          key={msg.id}
          style={{
            marginBottom: 20,
            display: "flex",
            flexDirection: "column",
            alignItems: msg.role === "user" ? "flex-end" : "flex-start",
          }}
        >
          {/* 角色标签 */}
          <div
            style={{
              fontSize: 11,
              color: "#888",
              marginBottom: 4,
              fontWeight: 600,
            }}
          >
            {msg.role === "user" ? "👤 你" : "🤖 助手"}
            {msg.total_ms > 0 && ` · ${msg.total_ms}ms`}
          </div>

          {/* 消息气泡 */}
          <div
            style={{
              maxWidth: "85%",
              padding: "12px 18px",
              borderRadius: 12,
              background: msg.role === "user" ? "#e3f2fd" : "#fff",
              border:
                msg.role === "user"
                  ? "1px solid #bbdefb"
                  : "1px solid #e0e0e0",
              lineHeight: 1.8,
              fontSize: 15,
              wordBreak: "break-word",
            }}
          >
            {msg.role === "user" ? (
              msg.content
            ) : (
              <RenderedContent content={msg.content} />
            )}
          </div>
        </div>
      ))}

      {/* 流式输出中 */}
      {streamingContent && (
        <div
          style={{
            marginBottom: 20,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: "#3498db",
              marginBottom: 4,
              fontWeight: 600,
            }}
          >
            🤖 助手 · 接收中...
          </div>
          <div
            style={{
              maxWidth: "85%",
              padding: "12px 18px",
              borderRadius: 12,
              background: "#fff",
              border: "1px solid #3498db",
              lineHeight: 1.8,
              fontSize: 15,
              wordBreak: "break-word",
            }}
          >
            <RenderedContent content={streamingContent} />
          </div>
        </div>
      )}
    </div>
  );
}
