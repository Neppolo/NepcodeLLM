"""Fetch a web page and reduce it to clean Markdown (main content + code blocks), with an on-disk cache."""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing

import httpx
import trafilatura

from .config import Settings

USER_AGENT = "Mozilla/5.0 (compatible; NepcodeLLM-research/0.1)"


def extract_markdown(html: str, url: str | None = None) -> str:
    text = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_precision=True,
    )
    return (text or "").strip()


def _cache(settings: Settings) -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS fetch_cache (url TEXT PRIMARY KEY, fetched_at REAL, content TEXT)")
    return conn


def fetch_url(settings: Settings, url: str, max_chars: int = 20_000, use_cache: bool = True) -> str:
    if not url.startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs are supported")
    with closing(_cache(settings)) as conn:
        if use_cache:
            row = conn.execute("SELECT fetched_at, content FROM fetch_cache WHERE url = ?", (url,)).fetchone()
            if row and time.time() - row[0] < settings.fetch_cache_ttl_s:
                return row[1][:max_chars]

        with httpx.stream(
            "GET", url, headers={"User-Agent": USER_AGENT}, timeout=settings.timeout_s, follow_redirects=True
        ) as resp:
            resp.raise_for_status()
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > settings.fetch_max_bytes:
                    break
                chunks.append(chunk)
            body = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
            content_type = resp.headers.get("content-type", "")

        content = body if "html" not in content_type else extract_markdown(body, url)
        with conn:
            conn.execute("INSERT OR REPLACE INTO fetch_cache VALUES (?, ?, ?)", (url, time.time(), content))
    return content[:max_chars]
