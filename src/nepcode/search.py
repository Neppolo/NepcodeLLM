"""Web search through a self-hosted SearXNG instance (free, no API key, private)."""

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


def web_search(settings: Settings, query: str, limit: int = 8, time_range: str | None = None) -> list[SearchResult]:
    params = {"q": query, "format": "json", "safesearch": 0}
    if time_range in {"day", "month", "year"}:
        params["time_range"] = time_range
    resp = httpx.get(f"{settings.searxng_url.rstrip('/')}/search", params=params, timeout=settings.timeout_s)
    resp.raise_for_status()
    return rank_results(resp.json().get("results", []), settings.trusted_domains, limit)
