"""FastAPI 应用入口 —— 路由注册、CORS 配置、SSE 端点、会话管理。"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from db import (
    create_session,
    delete_session,
    get_session,
    get_session_messages,
    list_sessions,
)
from history import (
    delete_all,
    delete_one,
    get_history_detail,
    list_history,
)
from models import (
    MessageItem,
    QueryRequest,
    SessionDetail,
    SessionItem,
    SessionList,
    SessionQueryRequest,
)
from scheduler import get_scheduler

app = FastAPI(title="LLM Query Dashboard")

# CORS —— 开发阶段允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 查询（无会话，向后兼容）─────────────────────────────

@app.post("/api/query")
async def handle_query(req: QueryRequest):
    """发起无会话查询，返回 SSE 流。"""

    async def event_stream() -> AsyncIterator[str]:
        scheduler = get_scheduler()
        async for sse_line in scheduler.submit(req.query):
            yield sse_line

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 会话 ──────────────────────────────────────────────

@app.get("/api/sessions", response_model=SessionList)
async def handle_list_sessions():
    """列出全部会话（按最新更新时间降序）。"""
    rows = await list_sessions()
    items = [
        SessionItem(
            id=r["id"],
            title=r["title"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            msg_count=r["msg_count"],
        )
        for r in rows
    ]
    return SessionList(items=items)


@app.post("/api/sessions", response_model=SessionItem)
async def handle_create_session():
    """创建新会话。"""
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    await create_session(session_id, "新对话", created_at)
    return SessionItem(
        id=session_id,
        title="新对话",
        created_at=created_at,
        updated_at=created_at,
        msg_count=0,
    )


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def handle_get_session(session_id: str):
    """获取会话详情（含全部消息）。"""
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_rows = await get_session_messages(session_id)
    messages = [
        MessageItem(
            id=m["id"],
            session_id=m["session_id"],
            role=m["role"],
            content=m["content"],
            total_ms=m["total_ms"],
            created_at=m["created_at"],
        )
        for m in msg_rows
    ]

    return SessionDetail(
        id=session["id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=messages,
    )


@app.delete("/api/sessions/{session_id}")
async def handle_delete_session(session_id: str):
    """删除会话及其全部消息。"""
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    await delete_session(session_id)
    return None


@app.post("/api/sessions/{session_id}/query")
async def handle_session_query(session_id: str, req: SessionQueryRequest):
    """在会话内发起查询，返回 SSE 流。"""

    # 验证会话存在
    session = await get_session(session_id)
    if session is None:
        # 自动创建
        created_at = datetime.now(timezone.utc).isoformat()
        await create_session(session_id, "新对话", created_at)

    async def event_stream() -> AsyncIterator[str]:
        scheduler = get_scheduler()
        async for sse_line in scheduler.submit_session(session_id, req.query):
            yield sse_line

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 历史（向后兼容）────────────────────────────────────

@app.get("/api/history")
async def handle_history(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """分页获取历史查询记录。"""
    return await list_history(page=page, size=size)


@app.get("/api/history/{query_id}")
async def handle_history_detail(query_id: str):
    """获取单条历史记录的完整内容。"""
    detail = await get_history_detail(query_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return detail


@app.delete("/api/history/{query_id}")
async def handle_delete_one(query_id: str):
    """删除单条历史记录。"""
    await delete_one(query_id)
    return None


@app.delete("/api/history")
async def handle_delete_all():
    """清空全部历史记录。"""
    await delete_all()
    return None


@app.get("/health")
async def health():
    return {"status": "ok"}
