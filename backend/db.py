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
    # 项目表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            llm_api_url     TEXT NOT NULL DEFAULT '',
            llm_api_key     TEXT NOT NULL DEFAULT '',
            llm_query_mode  TEXT NOT NULL DEFAULT 'mix',
            prompt_template TEXT NOT NULL DEFAULT '{query}',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)
    # sessions 表增加 project_id（向前兼容已有数据库）
    try:
        await db.execute("ALTER TABLE sessions ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE SET NULL")
    except Exception:
        pass  # 列已存在
    # 索引
    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC)")
    await db.commit()


# ── 会话 CRUD ─────────────────────────────────────────

async def create_session(session_id: str, title: str, created_at: str, project_id: str = "") -> None:
    db = await _connect()
    try:
        await db.execute(
            "INSERT INTO sessions (id, title, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, project_id, created_at, created_at),
        )
        await db.commit()
    finally:
        await db.close()


async def list_sessions(project_id: str | None = None) -> list[dict]:
    db = await _connect()
    try:
        if project_id is not None:
            cursor = await db.execute(
                """SELECT s.id, s.title, s.project_id, s.created_at, s.updated_at,
                          (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
                   FROM sessions s
                   WHERE s.project_id = ?
                   ORDER BY s.updated_at DESC""",
                (project_id,),
            )
        else:
            cursor = await db.execute(
                """SELECT s.id, s.title, s.project_id, s.created_at, s.updated_at,
                          (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS msg_count
                   FROM sessions s
                   ORDER BY s.updated_at DESC""",
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


# ── 项目 CRUD ─────────────────────────────────────────

async def create_project(
    project_id: str, name: str, description: str,
    llm_api_url: str, llm_api_key: str, llm_query_mode: str,
    prompt_template: str, created_at: str,
) -> None:
    db = await _connect()
    try:
        await db.execute(
            "INSERT INTO projects (id, name, description, llm_api_url, llm_api_key, "
            "llm_query_mode, prompt_template, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, name, description, llm_api_url, llm_api_key,
             llm_query_mode, prompt_template, created_at, created_at),
        )
        await db.commit()
    finally:
        await db.close()


async def list_projects() -> list[dict]:
    db = await _connect()
    try:
        cursor = await db.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM sessions s WHERE s.project_id = p.id) AS session_count
               FROM projects p
               ORDER BY p.updated_at DESC""",
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_project(project_id: str) -> dict | None:
    db = await _connect()
    try:
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_project(project_id: str, **fields: str) -> None:
    """更新项目字段。fields 只包含要更新的键值对。"""
    if not fields:
        return
    db = await _connect()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(_now_iso())
        values.append(project_id)
        await db.execute(
            f"UPDATE projects SET {set_clause}, updated_at = ? WHERE id = ?",
            values,
        )
        await db.commit()
    finally:
        await db.close()


async def delete_project(project_id: str) -> None:
    db = await _connect()
    try:
        # 将该项目下所有会话的 project_id 置空（而非级联删除）
        await db.execute(
            "UPDATE sessions SET project_id = NULL WHERE project_id = ?",
            (project_id,),
        )
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
    finally:
        await db.close()


async def find_empty_session(project_id: str) -> dict | None:
    """查找项目下第一条空会话（无消息），用于防止重复创建。"""
    db = await _connect()
    try:
        cursor = await db.execute(
            """SELECT s.id, s.title, s.project_id, s.created_at, s.updated_at
               FROM sessions s
               WHERE s.project_id = ?
                 AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.id)
               ORDER BY s.created_at DESC
               LIMIT 1""",
            (project_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_session_project(session_id: str) -> str | None:
    """获取会话所属的项目 id。"""
    db = await _connect()
    try:
        cursor = await db.execute(
            "SELECT project_id FROM sessions WHERE id = ?", (session_id,),
        )
        row = await cursor.fetchone()
        return row["project_id"] if row else None
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