"""上游 LightRag 流式消费 —— 调用 /query/stream，逐 chunk 产出文本。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx

logger = logging.getLogger("llm_client")


class LLMConfig(Protocol):
    """stream_chunks 所需的配置字段协议。"""
    llm_api_url: str
    llm_api_key: str
    llm_query_mode: str
    llm_timeout_ms: int
    llm_user_prompt_template: str


class LLMError(Exception):
    pass


async def stream_chunks(
    config: LLMConfig, query: str,
    conversation_history: list[dict] | None = None,
) -> AsyncIterator[str]:
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

    # 使用配置中的提示词模板拼接最终 query
    template = config.llm_user_prompt_template
    if "{query}" in template:
        final_query = template.replace("{query}", query)
    else:
        final_query = f"{template}\n{query}"

    payload: dict[str, Any] = {
        "query": final_query,
        "mode": config.llm_query_mode,
        "stream": True,
        "include_references": True,
    }

    # LightRag 原生 conversation_history 参数
    if conversation_history:
        payload["conversation_history"] = conversation_history

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
                    continue

                if "error" in data:
                    raise LLMError(data["error"])

                if "references" in data:
                    continue

                # 独立 thinking 字段（部分 LightRag 部署会分离输出）
                thinking = data.get("thinking", "")
                if thinking:
                    yield f"thinking\n{thinking}\n"

                # 正式回复内容（可能内嵌 思考... 标签）
                content = data.get("response", "")
                if content:
                    yield content

            logger.info(f"LightRag 流自然结束，共 {line_count} 行")
