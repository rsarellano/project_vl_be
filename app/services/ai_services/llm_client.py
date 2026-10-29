"""Shared chat client.

Defaults to OpenAI. Set ``OPENAI_BASE_URL`` (for example LM Studio at
``http://127.0.0.1:1234/v1``) to send the same calls to a compatible server.
Inside Docker, localhost is the container, so that address is rewritten to
``host.docker.internal``.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from langchain_openai import ChatOpenAI


def openai_api_key() -> str | None:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    return key or None


def openai_base_url() -> str | None:
    url = (os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/")
    if not url:
        return None
    if not Path("/.dockerenv").exists():
        return url
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return url
    host = "host.docker.internal"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=host))


def build_chat_model(
    *,
    temperature: float,
    model: str,
    api_key: str | None = None,
) -> ChatOpenAI:
    key = (api_key or openai_api_key() or "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    kwargs: dict[str, object] = {
        "temperature": temperature,
        "model": model,
        "api_key": key,
    }
    base_url = openai_base_url()
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
