"""历史记录 CRUD —— 向后兼容，委托给 db.py。"""

from __future__ import annotations

from db import (
    delete_legacy_all as delete_all,
    delete_legacy_one as delete_one,
    get_legacy_full,
    list_legacy,
    save_legacy as save,
)
from models import HistoryDetail, HistoryItem, HistoryPage


async def list_history(page: int = 1, size: int = 20) -> HistoryPage:
    rows, total = await list_legacy(page, size)
    items = [
        HistoryItem(
            id=r["id"],
            query=r["query"],
            summary=r["summary"],
            created_at=r["created_at"],
            total_ms=r["total_ms"],
        )
        for r in rows
    ]
    return HistoryPage(items=items, total=total, page=page, size=size)


async def get_history_detail(query_id: str) -> HistoryDetail | None:
    row = await get_legacy_full(query_id)
    if row is None:
        return None
    return HistoryDetail(
        id=row["id"],
        query=row["query"],
        summary=row["summary"],
        full_answer=row["full_answer"],
        created_at=row["created_at"],
        total_ms=row["total_ms"],
    )
