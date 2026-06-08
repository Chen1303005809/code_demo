"""并发调度器 —— Semaphore 槽位 + Queue 等待队列，支持会话上下文。

每个请求以异步迭代器形式产出 SSE 事件，前端通过 fetch+ReadableStream 消费。
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("scheduler")

from config import get_config
from db import (
    create_session,
    get_session_messages,
    make_title,
    save_message,
    touch_session,
    update_session_title,
)
from history import save as save_history
from llm_client import LLMError, stream_chunks
from models import (
    SSEChunkData,
    SSEDoneData,
    SSEErrorData,
    SSEQueuedData,
)


@dataclass
class _WaitingTask:
    query_id: str
    query: str
    event_queue: asyncio.Queue[str | None]
    session_id: str = ""
    message_id: str = ""
    conversation_history: list[dict] | None = None


@dataclass
class _SSEEvent:
    @staticmethod
    def queued(position: int, estimated_wait_ms: int) -> str:
        data = SSEQueuedData(position=position, estimated_wait_ms=estimated_wait_ms)
        return f"event: queued\ndata: {data.model_dump_json()}\n\n"

    @staticmethod
    def started() -> str:
        return "event: started\ndata: {}\n\n"

    @staticmethod
    def chunk(content: str) -> str:
        data = SSEChunkData(content=content)
        return f"event: chunk\ndata: {data.model_dump_json()}\n\n"

    @staticmethod
    def done(query_id: str, total_ms: int, session_id: str = "", message_id: str = "") -> str:
        data = SSEDoneData(
            query_id=query_id, total_ms=total_ms,
            session_id=session_id, message_id=message_id,
        )
        return f"event: done\ndata: {data.model_dump_json()}\n\n"

    @staticmethod
    def error(message: str) -> str:
        data = SSEErrorData(message=message)
        return f"event: error\ndata: {data.model_dump_json()}\n\n"


class Scheduler:
    def __init__(self) -> None:
        config = get_config()
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._queue: asyncio.Queue[_WaitingTask] = asyncio.Queue()
        self._recent_durations: list[float] = []

    # ── 无会话查询（向后兼容）───────────────────────

    async def submit(self, query: str) -> AsyncIterator[str]:
        query_id = f"q_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        if not self._semaphore.locked():
            await self._semaphore.acquire()
            async for line in self._run(query_id, query):
                yield line
        else:
            async for line in self._enqueue_and_wait(query_id, query):
                yield line

    # ── 会话内查询 ──────────────────────────────────

    async def submit_session(
        self, session_id: str, query: str,
    ) -> AsyncIterator[str]:
        """在会话内提交查询，自动保存用户消息和助手回复。"""
        user_msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        assistant_msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        query_id = f"q_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        # 保存用户消息
        created_at = datetime.now(timezone.utc).isoformat()
        await save_message(user_msg_id, session_id, "user", query, created_at)

        # 获取会话历史作为上下文
        history_messages = await get_session_messages(session_id)
        # 去掉刚保存的这条（当前查询），剩余的是历史
        context_messages = [m for m in history_messages if m["id"] != user_msg_id]

        # 如果是第一条消息，用问题内容作为会话标题
        if len(context_messages) == 0:
            await update_session_title(session_id, make_title(query))

        # 构建 LightRag 格式的 conversation_history
        conv_history = [
            {"role": m["role"], "content": m["content"]}
            for m in context_messages
        ] if context_messages else None

        if not self._semaphore.locked():
            await self._semaphore.acquire()
            async for line in self._run(
                query_id, query,
                session_id=session_id, message_id=assistant_msg_id,
                conversation_history=conv_history,
            ):
                yield line
        else:
            async for line in self._enqueue_and_wait(
                query_id, query,
                session_id=session_id, message_id=assistant_msg_id,
                conversation_history=conv_history,
            ):
                yield line

    async def _enqueue_and_wait(
        self, query_id: str, query: str,
        session_id: str = "", message_id: str = "",
        conversation_history: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        event_queue: asyncio.Queue[str | None] = asyncio.Queue()
        task = _WaitingTask(
            query_id=query_id, query=query, event_queue=event_queue,
            session_id=session_id, message_id=message_id,
            conversation_history=conversation_history,
        )
        await self._queue.put(task)

        estimated_ms = self._estimate_wait_ms()
        yield _SSEEvent.queued(
            position=self._queue.qsize(), estimated_wait_ms=estimated_ms,
        )

        while True:
            line = await event_queue.get()
            if line is None:
                break
            yield line

    # ── 核心执行 ────────────────────────────────────

    async def _run(
        self, query_id: str, query: str,
        session_id: str = "", message_id: str = "",
        conversation_history: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        config = get_config()
        started_at = time.monotonic()
        full_answer_parts: list[str] = []
        had_error = False

        try:
            yield _SSEEvent.started()
            async for chunk_text in stream_chunks(
                config, query,
                conversation_history=conversation_history,
            ):
                full_answer_parts.append(chunk_text)
                yield _SSEEvent.chunk(chunk_text)
        except LLMError as exc:
            had_error = True
            logger.warning(f"LLM 错误: {exc}, query_id={query_id}")
            yield _SSEEvent.error(str(exc))
        except asyncio.CancelledError:
            had_error = True
            raise
        except Exception as exc:
            had_error = True
            logger.exception(f"流式查询异常: query_id={query_id}, session_id={session_id}")
            yield _SSEEvent.error(f"查询失败: {exc}")
        else:
            # 流式部分正常完成，执行持久化（在 else 中以便 CancelledError 时跳过）
            try:
                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                full_answer = "".join(full_answer_parts)
                created_at = datetime.now(timezone.utc).isoformat()

                if session_id:
                    await save_message(
                        message_id, session_id, "assistant",
                        full_answer, created_at, total_ms=elapsed_ms,
                    )
                    await touch_session(session_id)
                else:
                    await save_history(
                        query_id=query_id, query=query,
                        full_answer=full_answer, total_ms=elapsed_ms,
                        created_at=created_at,
                    )

                self._record_duration(elapsed_ms / 1000.0)
                yield _SSEEvent.done(
                    query_id=query_id, total_ms=elapsed_ms,
                    session_id=session_id, message_id=message_id,
                )
            except Exception as exc:
                had_error = True
                logger.exception(f"持久化异常: query_id={query_id}, session_id={session_id}")
                yield _SSEEvent.error(f"保存失败: {exc}")
        finally:
            self._semaphore.release()
            if not self._queue.empty():
                next_task = self._queue.get_nowait()
                asyncio.create_task(self._drain_queue(next_task))

    async def _drain_queue(self, task: _WaitingTask) -> None:
        try:
            await self._semaphore.acquire()
        except Exception:
            await task.event_queue.put(_SSEEvent.error("系统繁忙，获取槽位失败。"))
            await task.event_queue.put(None)
            return

        async for line in self._run(
            task.query_id, task.query,
            session_id=task.session_id, message_id=task.message_id,
            conversation_history=task.conversation_history,
        ):
            await task.event_queue.put(line)
        await task.event_queue.put(None)

    def _estimate_wait_ms(self) -> int:
        if not self._recent_durations:
            return 10000
        avg = sum(self._recent_durations) / len(self._recent_durations)
        return int(self._queue.qsize() * avg * 1000)

    def _record_duration(self, seconds: float) -> None:
        self._recent_durations.append(seconds)
        if len(self._recent_durations) > 10:
            self._recent_durations = self._recent_durations[-10:]


_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
