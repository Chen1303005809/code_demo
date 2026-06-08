import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
}

// ── 思考标签解析 ──────────────────────────────────────────
// DeepSeek / 各类模型的输出格式：
//   思考这是思考过程...\n\n最终答案。
// 或:
//   thinking\nThis is thinking...\n\nActual answer.

interface ContentBlock {
  type: "markdown" | "thinking";
  content: string;
}

/** 将原始内容按 思考... / thinking... 标签拆分为块 */
function parseContentBlocks(raw: string): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  // 同时匹配英文 "thinking" 和中文 "思考"
  const thinkRegex = /(?:thinking|思考)\s*([\s\S]*?)\s*/gi;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = thinkRegex.exec(raw)) !== null) {
    // 思考标签之前的文本 → Markdown
    const before = raw.slice(lastIndex, match.index);
    if (before.trim()) {
      blocks.push({ type: "markdown", content: before });
    }

    // 思考内容
    const thinkContent = match[1].trim();
    if (thinkContent) {
      blocks.push({ type: "thinking", content: thinkContent });
    }

    lastIndex = match.index + match[0].length;
  }

  // 剩余尾部文本
  const tail = raw.slice(lastIndex);
  if (tail.trim()) {
    blocks.push({ type: "markdown", content: tail });
  }

  // 如果没有匹配到任何思考标签，整个内容作为 Markdown
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
        margin: "12px 0",
        border: "1px solid #d4a574",
        borderRadius: 8,
        background: "#fdf6ec",
        overflow: "hidden",
      }}
    >
      <summary
        style={{
          padding: "8px 14px",
          cursor: "pointer",
          fontWeight: 600,
          fontSize: 13,
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
          padding: "10px 16px",
          fontSize: 13,
          color: "#5c4a2e",
          lineHeight: 1.7,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {content}
      </div>
    </details>
  );
};

// ── 主组件 ────────────────────────────────────────────────

export default function ResultView({ content }: Props) {
  if (!content) {
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
        <p>输入问题，开始查询。</p>
      </div>
    );
  }

  const blocks = parseContentBlocks(content);

  return (
    <div
      style={{
        flex: 1,
        overflow: "auto",
        padding: "20px 24px",
        lineHeight: 1.8,
        fontSize: 15,
      }}
    >
      {blocks.map((block, i) =>
        block.type === "thinking" ? (
          <ThinkingBlock key={i} content={block.content} />
        ) : (
          <ReactMarkdown
            key={i}
            remarkPlugins={[remarkGfm]}
            components={{
              pre: ({ children }) => (
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
                  {children}
                </pre>
              ),
              code: ({ children, ...props }) =>
                (props as { className?: string }).className ? (
                  <code {...props}>{children}</code>
                ) : (
                  <code
                    style={{
                      background: "#f0f0f0",
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontSize: 13,
                    }}
                  >
                    {children}
                  </code>
                ),
              table: ({ children }) => (
                <table
                  style={{
                    borderCollapse: "collapse",
                    width: "100%",
                    margin: "8px 0",
                  }}
                >
                  {children}
                </table>
              ),
              th: ({ children }) => (
                <th
                  style={{
                    border: "1px solid #ddd",
                    padding: "6px 12px",
                    background: "#f5f5f5",
                    textAlign: "left",
                  }}
                >
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td
                  style={{ border: "1px solid #ddd", padding: "6px 12px" }}
                >
                  {children}
                </td>
              ),
            }}
          >
            {block.content}
          </ReactMarkdown>
        )
      )}
    </div>
  );
}
