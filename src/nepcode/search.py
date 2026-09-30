"""Web search, free and without API keys.

Backends: a self-hosted SearXNG instance (private, needs Docker) or the `ddgs` metasearch library
(no setup). With NEPCODE_SEARCH_BACKEND=auto, SearXNG is used when it answers, ddgs otherwise.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import httpx

from .config import Settings


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    published: str | None = None
    trusted: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _is_trusted(url: str, trusted_domains: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in trusted_domains)


def rank_results(raw: list[dict], trusted_domains: tuple[str, ...], limit: int) -> list[SearchResult]:
    """Dedupe by URL and put results from trusted documentation sites first, keeping engine order otherwise."""
    seen: set[str] = set()
    results: list[SearchResult] = []
    for item in raw:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        results.append(
            SearchResult(
                title=(item.get("title") or "").strip(),
                url=url,
                snippet=(item.get("content") or "").strip(),
                published=item.get("publishedDate"),
                trusted=_is_trusted(url, trusted_domains),
            )
        )
    results.sort(key=lambda r: not r.trusted)  # stable: keeps relevance order within each group
    return results[:limit]


def _searxng(settings: Settings, query: str, time_range: str | None) -> list[dict]:
    params = {"q": query, "format": "json", "safesearch": 0}
    if time_range:
        params["time_range"] = time_range
    resp = httpx.get(f"{settings.searxng_url.rstrip('/')}/search", params=params, timeout=settings.timeout_s)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _ddgs(query: str, time_range: str | None, limit: int) -> list[dict]:
    from ddgs import DDGS

    timelimit = {"day": "d", "month": "m", "year": "y"}.get(time_range or "")
    # over-fetch so trusted docs can be ranked first; map to SearXNG's field names
    raw = DDGS().text(query, max_results=limit * 2, timelimit=timelimit)
    return [{"title": r.get("title"), "url": r.get("href"), "content": r.get("body")} for r in raw]


def web_search(settings: Settings, query: str, limit: int = 8, time_range: str | None = None) -> list[SearchResult]:
    if time_range not in {"day", "month", "year"}:
        time_range = None
    backend = settings.search_backend
    if backend in {"auto", "searxng"}:
        try:
            raw = _searxng(settings, query, time_range)
        except httpx.HTTPError:
            if backend == "searxng":
                raise
            raw = _ddgs(query, time_range, limit)
    elif backend == "ddgs":
        raw = _ddgs(query, time_range, limit)
    else:
        raise ValueError(f"unknown NEPCODE_SEARCH_BACKEND: {backend}")
    return rank_results(raw, settings.trusted_domains, limit)
