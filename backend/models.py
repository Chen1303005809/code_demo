"""Pydantic 模型 —— 请求 / 响应 / 事件类型 / 会话。"""

from __future__ import annotations

from typing import Optional
from enum import StrEnum

from pydantic import BaseModel


# ── 项目 ──────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    llm_api_url: str = ""
    llm_api_key: str = ""
    llm_query_mode: str = "mix"
    prompt_template: str = "{query}"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    llm_api_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_query_mode: Optional[str] = None
    prompt_template: Optional[str] = None


class ProjectItem(BaseModel):
    id: str
    name: str
    description: str
    llm_api_url: str
    llm_query_mode: str
    session_count: int
    created_at: str
    updated_at: str


class ProjectList(BaseModel):
    items: list[ProjectItem]


# ── 请求 ──────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str


class SessionQueryRequest(BaseModel):
    query: str


# ── 会话 ──────────────────────────────────────────

class SessionItem(BaseModel):
    id: str
    title: str
    project_id: str
    created_at: str
    updated_at: str
    msg_count: int


class SessionList(BaseModel):
    items: list[SessionItem]


class MessageItem(BaseModel):
    id: str
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    total_ms: int
    created_at: str


class SessionDetail(BaseModel):
    id: str
    title: str
    project_id: str
    created_at: str
    updated_at: str
    messages: list[MessageItem]


# ── 历史（向后兼容）──────────────────────────────

class HistoryItem(BaseModel):
    id: str
    query: str
    summary: str
    created_at: str
    total_ms: int


class HistoryDetail(BaseModel):
    id: str
    query: str
    summary: str
    full_answer: str
    created_at: str
    total_ms: int


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    size: int


# ── SSE 事件 ──────────────────────────────────────

class SSEEventKind(StrEnum):
    QUEUED = "queued"
    STARTED = "started"
    CHUNK = "chunk"
    DONE = "done"
    ERROR = "error"


class SSEQueuedData(BaseModel):
    position: int
    estimated_wait_ms: int


class SSEChunkData(BaseModel):
    content: str


class SSEDoneData(BaseModel):
    query_id: str
    total_ms: int
    session_id: str = ""
    message_id: str = ""


class SSEErrorData(BaseModel):
    message: str