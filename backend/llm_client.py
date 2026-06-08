"""上游 LightRag 流式消费 —— 调用 /query/stream，逐 chunk 产出文本。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from config import Config

logger = logging.getLogger("llm_client")


class LLMError(Exception):
    pass


def build_query_with_history(
    query: str, history_messages: list[dict],
) -> str:
    """将会话历史拼入查询文本，形成带上下文的完整提示。

    history_messages 按时间排序，每项包含 role/content 字段。
    格式：
      [对话历史]
      User: ...
      Assistant: ...
      ---
      [当前问题]
      ...
    """
    if not history_messages:
        return query

    parts: list[str] = ["[对话历史]"]
    for msg in history_messages:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        parts.append(f"{role_label}: {msg['content']}")
    parts.append("---")
    parts.append("[当前问题]")
    parts.append(query)

    return "\n".join(parts)


async def stream_chunks(config: Config, query: str) -> AsyncIterator[str]:
    """向 LightRag /query/stream 发起流式请求。

    请求体：{"query":..., "mode":"mix", "stream":true, "include_references":true}

    响应格式自动检测：
      * SSE：  data: {...}  → 去掉 "data: " 前缀后解析
      * NDJSON：每行直接是 JSON 对象

    超时策略：
    * 连接超时 10s
    * 读取超时（无数据间隔）使用 config.llm_timeout_ms
    """

    url = f"{config.llm_api_url.rstrip('/')}/query/stream"

    payload: dict[str, Any] = {
        "query": query,
        "mode": config.llm_query_mode,
        "stream": True,
        "include_references": True,
        "user_prompt": '''In your responses, you must strictly adhere to the following rules:
                            Whenever you mention a function name, you must specify the file in which it is defined.
                            Whenever you reference a function, you must explicitly state its return type.'''
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.llm_api_key:
        headers["Authorization"] = f"Bearer {config.llm_api_key}"

    connect_timeout = 10.0
    read_timeout = config.llm_timeout_ms / 1000.0

    logger.info(f"请求 LightRag: url={url}, mode={config.llm_query_mode}")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect_timeout, read=read_timeout),
    ) as client:
        async with client.stream(
            "POST",
            url,
            json=payload,
            headers=headers,
        ) as resp:
            content_type = resp.headers.get("content-type", "")
            logger.info(f"LightRag 响应: status={resp.status_code}, content-type={content_type}")

            if resp.status_code == 401:
                raise LLMError("上游认证失败，请检查 API Key。")
            if resp.status_code == 429:
                raise LLMError("上游速率限制，请稍后重试。")
            if 400 <= resp.status_code < 500:
                raise LLMError(f"请求参数异常 (HTTP {resp.status_code})")
            if resp.status_code >= 500:
                raise LLMError(f"上游服务故障 (HTTP {resp.status_code})")

            line_count = 0
            async for line in resp.aiter_lines():
                line_count += 1
                line = line.strip()
                if not line:
                    continue

                raw = line

                # SSE 格式：data: {...}
                if raw.startswith("data:"):
                    raw = raw[len("data:"):].strip()
                    if raw == "[DONE]":
                        logger.info(f"LightRag 流结束 (SSE DONE), 共 {line_count} 行")
                        return

                if not raw:
                    continue

                try:
                    data: dict[str, Any] = json.loads(raw)
                except json.JSONDecodeError:
                    logger.debug(f"跳过非 JSON 行: {raw[:200]}")
                    continue

                if "error" in data:
                    raise LLMError(data["error"])

                if "references" in data:
                    logger.debug(f"收到 references, {len(data['references'])} 条")
                    continue

                content = data.get("response", "")
                if content:
                    yield content

            logger.info(f"LightRag 流自然结束，共 {line_count} 行")
