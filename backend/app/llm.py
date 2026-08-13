"""OpenCode Go / OpenAI 兼容 LLM 客户端封装。

风控要点（验证过）：
- 必须带浏览器 UA 头，否则 Cloudflare 1010 返回 403
- 必须走 Clash 代理 127.0.0.1:7890（opencode.ai 被墙）
- max_tokens 留足，否则输出可能为空
"""
import json
import os
from typing import AsyncIterator, Optional

import httpx

BASE_URL = os.environ.get("LLM_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.environ.get("LLM_MODEL", "kimi-k3")
PROXY = os.environ.get("LLM_PROXY", "http://127.0.0.1:7890")
UA = os.environ.get(
    "LLM_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)


def get_api_key() -> str:
    key = os.environ.get("LLM_API_KEY")
    if key:
        return key
    # 回退：读 Reasonix 全局 .env（本机开发用，不入库）
    env_path = os.path.expandvars(r"%APPDATA%/reasonix/.env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("OPENCODE_GO_API_KEY="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("LLM_API_KEY 未设置（可在环境变量或 %APPDATA%/reasonix/.env 提供）")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_api_key()}",
        "User-Agent": UA,
        "Content-Type": "application/json",
    }


async def stream_chat(
    messages: list[dict],
    *,
    tools: Optional[list[dict]] = None,
    max_tokens: int = 800,
) -> AsyncIterator[dict]:
    """流式对话，逐个产出事件 dict：
    {"type": "delta", "text": ...}          叙事文本增量
    {"type": "tool_call", "call": {...}}    完整 tool_call（名称+参数 JSON 字符串）
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(proxy=PROXY, timeout=120) as client:
        async with client.stream(
            "POST", f"{BASE_URL}/chat/completions", headers=_headers(), json=payload
        ) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"LLM {resp.status_code}: {body[:300]}")
            # 流式 tool_calls 增量聚合
            tool_calls: dict[int, dict] = {}
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    yield {"type": "delta", "text": delta["content"]}
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    slot = tool_calls.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
            for idx in sorted(tool_calls):
                slot = tool_calls[idx]
                yield {"type": "tool_call", "call": {
                    "id": slot["id"] or f"call_{idx}",
                    "name": slot["name"],
                    "arguments": slot["arguments"],
                }}
