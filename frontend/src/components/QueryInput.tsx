import React, { useRef } from "react";

interface Props {
  onQuery: (query: string) => void;
  onCancel: () => void;
  disabled: boolean;
}

export default function QueryInput({ onQuery, onCancel, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    const val = inputRef.current?.value.trim();
    if (!val) return;
    onQuery(val);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
  };

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        padding: "12px 16px",
        borderBottom: "1px solid #e0e0e0",
        background: "#fafafa",
      }}
    >
      <input
        ref={inputRef}
        type="text"
        placeholder="请输入问题，按 Enter 发送..."
        disabled={disabled}
        onKeyDown={handleKeyDown}
        style={{
          flex: 1,
          padding: "8px 12px",
          border: "1px solid #ccc",
          borderRadius: 6,
          fontSize: 15,
          outline: "none",
        }}
      />
      {disabled ? (
        <button
          onClick={onCancel}
          style={{
            padding: "8px 20px",
            background: "#e74c3c",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 15,
          }}
        >
          取消
        </button>
      ) : (
        <button
          onClick={handleSubmit}
          style={{
            padding: "8px 24px",
            background: "#3498db",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 15,
          }}
        >
          发送
        </button>
      )}
    </div>
  );
}
