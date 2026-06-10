"""FastAPI 应用入口 —— 路由注册、CORS 配置、SSE 端点、会话管理、项目管理。"""

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
    create_project,
    create_session,
    delete_project,
    delete_session,
    get_project,
    get_session,
    get_session_messages,
    list_projects,
    list_sessions,
    update_project,
)
from history import (
    delete_all,
    delete_one,
    get_history_detail,
    list_history,
)
from models import (
    MessageItem,
    ProjectCreate,
    ProjectItem,
    ProjectList,
    ProjectUpdate,
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


# ── 项目 ──────────────────────────────────────────────

@app.get("/api/projects", response_model=ProjectList)
async def handle_list_projects():
    """列出全部项目（按更新时间降序）。"""
    rows = await list_projects()
    items = [
        ProjectItem(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            llm_api_url=r["llm_api_url"],
            llm_query_mode=r["llm_query_mode"],
            session_count=r["session_count"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return ProjectList(items=items)


@app.post("/api/projects", response_model=ProjectItem)
async def handle_create_project(req: ProjectCreate):
    """创建新项目。"""
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    await create_project(
        project_id=project_id,
        name=req.name,
        description=req.description,
        llm_api_url=req.llm_api_url,
        llm_api_key=req.llm_api_key,
        llm_query_mode=req.llm_query_mode,
        prompt_template=req.prompt_template,
        created_at=created_at,
    )
    return ProjectItem(
        id=project_id,
        name=req.name,
        description=req.description,
        llm_api_url=req.llm_api_url,
        llm_query_mode=req.llm_query_mode,
        session_count=0,
        created_at=created_at,
        updated_at=created_at,
    )


@app.get("/api/projects/{project_id}", response_model=ProjectItem)
async def handle_get_project(project_id: str):
    """获取项目详情。"""
    row = await get_project(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    session_count = 0  # 由 list_projects 带回，get 不查
    return ProjectItem(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        llm_api_url=row["llm_api_url"],
        llm_query_mode=row["llm_query_mode"],
        session_count=session_count,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.put("/api/projects/{project_id}", response_model=ProjectItem)
async def handle_update_project(project_id: str, req: ProjectUpdate):
    """更新项目配置。"""
    existing = await get_project(project_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 只更新非 None 字段
    updates: dict[str, str] = {}
    for field in ("name", "description", "llm_api_url", "llm_api_key",
                  "llm_query_mode", "prompt_template"):
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val

    if updates:
        await update_project(project_id, **updates)

    # 重新读取返回
    row = await get_project(project_id)
    return ProjectItem(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        llm_api_url=row["llm_api_url"],
        llm_query_mode=row["llm_query_mode"],
        session_count=0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.delete("/api/projects/{project_id}")
async def handle_delete_project(project_id: str):
    """删除项目（其下会话 project_id 置空，不级联删除）。"""
    existing = await get_project(project_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    await delete_project(project_id)
    return None


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
async def handle_list_sessions(project_id: str | None = Query(default=None)):
    """列出会话（可按项目过滤）。"""
    rows = await list_sessions(project_id=project_id)
    items = [
        SessionItem(
            id=r["id"],
            title=r["title"],
            project_id=r.get("project_id") or "",
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            msg_count=r["msg_count"],
        )
        for r in rows
    ]
    return SessionList(items=items)


@app.get("/api/projects/{project_id}/sessions", response_model=SessionList)
async def handle_list_project_sessions(project_id: str):
    """列出指定项目下的会话。"""
    rows = await list_sessions(project_id=project_id)
    items = [
        SessionItem(
            id=r["id"],
            title=r["title"],
            project_id=r.get("project_id") or project_id,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            msg_count=r["msg_count"],
        )
        for r in rows
    ]
    return SessionList(items=items)


@app.post("/api/projects/{project_id}/sessions", response_model=SessionItem)
async def handle_create_project_session(project_id: str):
    """在指定项目下创建新会话（已有空会话时直接返回，防止无限创建）。"""
    from db import find_empty_session

    existing_project = await get_project(project_id)
    if existing_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 如果该项目下已有空会话，复用而非新建
    empty = await find_empty_session(project_id)
    if empty is not None:
        return SessionItem(
            id=empty["id"],
            title=empty["title"],
            project_id=empty.get("project_id") or project_id,
            created_at=empty["created_at"],
            updated_at=empty["updated_at"],
            msg_count=0,
        )

    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    await create_session(session_id, "新对话", created_at, project_id=project_id)
    return SessionItem(
        id=session_id,
        title="新对话",
        project_id=project_id,
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
        project_id=session.get("project_id") or "",
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
        raise HTTPException(status_code=404, detail="会话不存在")

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
