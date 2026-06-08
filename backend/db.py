"""SQLite 数据库操作 —— 会话、消息、历史（向后兼容）。"""

from __future__ import annotations

import os
import re

import aiosqlite

from config import get_config


# ── 工具函数 ──────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[.*?]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def make_title(text: str, max_chars: int = 50) -> str:
    """从第一条用户消息生成会话标题。"""
    plain = _strip_markdown(text)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= max_chars:
        return plain
    return plain[: max_chars - 3] + "..."


def _make_summary(full_answer: str, max_chars: int = 200) -> str:
    plain = _strip_markdown(full_answer)
    if len(plain) <= max_chars:
        return plain
    return plain[: max_chars - 3] + "..."


# ── 数据库初始化 ──────────────────────────────────────

async def _connect() -> aiosqlite.Connection:
    config = get_config()
    db_dir = os.path.dirname(config.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    db = await aiosqlite.connect(config.db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await _init_tables(db)
    return db


async def _init_tables(db: aiosqlite.Connection) -> None:
    # 会话表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL DEFAULT '新对话',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    # 消息表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content     TEXT NOT NULL,
            total_ms    INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    # 旧 queries 表（向后兼容）
    await db.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id          TEXT PRIMARY KEY,
            query       TEXT NOT NULL,
            summary     TEXT NOT NULL,
            full_answer TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            total_ms    INTEGER NOT NULL
        )
    """)
    # 索引
    await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries(created_at DESC)")
    await db.commit()


# ── 会话 CRUD ─────────────────────────────────────────

async def create_session(session_id: str, title: str, created_at: str) -> None:
    db = await _connect()
    try:
        await db.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, title, created_at, created_at),
        )
        await db.commit()
    finally:
        await db.close()


async def list_sessions() -> list[dict]:
    db = await _connect()
    try:
        cursor = await db.execute(
            """SELECT s.id, s.title, s.created_at, s.updated_at,
                      (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
               FROM sessions s
               ORDER BY s.updated_at DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_session(session_id: str) -> dict | None:
    db = await _connect()
    try:
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_session_title(session_id: str, title: str) -> None:
    db = await _connect()
    try:
        await db.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now_iso(), session_id),
        )
        await db.commit()
    finally:
        await db.close()


async def touch_session(session_id: str) -> None:
    db = await _connect()
    try:
        await db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (_now_iso(), session_id),
        )
        await db.commit()
    finally:
        await db.close()


async def delete_session(session_id: str) -> None:
    db = await _connect()
    try:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
    finally:
        await db.close()


# ── 消息 CRUD ─────────────────────────────────────────

async def save_message(
    message_id: str,
    session_id: str,
    role: str,
    content: str,
    created_at: str,
    total_ms: int = 0,
) -> None:
    db = await _connect()
    try:
        await db.execute(
            "INSERT INTO messages (id, session_id, role, content, total_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, total_ms, created_at),
        )
        await db.commit()
    finally:
        await db.close()


async def get_session_messages(session_id: str) -> list[dict]:
    db = await _connect()
    try:
        cursor = await db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_message_count(session_id: str) -> int:
    db = await _connect()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM messages WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
    finally:
        await db.close()


# ── 旧 queries 表（向后兼容）──────────────────────────

async def save_legacy(
    query_id: str,
    query: str,
    full_answer: str,
    total_ms: int,
    created_at: str,
) -> None:
    db = await _connect()
    try:
        summary = _make_summary(full_answer)
        await db.execute(
            "INSERT INTO queries (id, query, summary, full_answer, created_at, total_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (query_id, query, summary, full_answer, created_at, total_ms),
        )
        await db.commit()
    finally:
        await db.close()


async def list_legacy(page: int = 1, size: int = 20) -> tuple[list[dict], int]:
    db = await _connect()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM queries")
        row = await cursor.fetchone()
        total = row["cnt"] if row else 0

        offset = (page - 1) * size
        cursor = await db.execute(
            "SELECT id, query, summary, created_at, total_ms FROM queries "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows], total
    finally:
        await db.close()


async def get_legacy_full(query_id: str) -> dict | None:
    """获取单条历史记录的完整内容（含 full_answer）。"""
    db = await _connect()
    try:
        cursor = await db.execute("SELECT * FROM queries WHERE id = ?", (query_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def delete_legacy_one(query_id: str) -> None:
    db = await _connect()
    try:
        await db.execute("DELETE FROM queries WHERE id = ?", (query_id,))
        await db.commit()
    finally:
        await db.close()


async def delete_legacy_all() -> None:
    db = await _connect()
    try:
        await db.execute("DELETE FROM queries")
        await db.commit()
    finally:
        await db.close()


# ── 内部 ──────────────────────────────────────────────

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
