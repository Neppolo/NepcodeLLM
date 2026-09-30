"""MCP server exposing research tools to any MCP-capable coding client (Cline, Continue, OpenCode, ...)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .config import get_settings
from .fetch import fetch_url as _fetch_url
from .kb import KnowledgeBase
from .search import web_search as _web_search

INSTRUCTIONS = """\
Research tools for a Java / Spring coding assistant.
- Check kb_search first: it holds curated best practices and notes saved from earlier research.
- Use web_search + fetch_url when the question involves versions, release notes, deprecations, CVEs,
  or anything that may have changed after your training data. Prefer official docs (marked trusted).
- After verifying something new and durable from an official source, save it with kb_save_note.
- Budget: context is limited. Prefer snippets from web_search; fetch at most 2-3 pages per task.
"""

settings = get_settings()
kb = KnowledgeBase(settings)
mcp = MCPServer("nepcode", instructions=INSTRUCTIONS)


@mcp.tool()
def web_search(query: str, limit: int = 5, time_range: str | None = None) -> list[dict]:
    """Search the web. time_range: optional 'day' | 'month' | 'year' to get only recent results.
    Results from official documentation sites are marked trusted and listed first."""
    return [r.to_dict() for r in _web_search(settings, query, limit=min(limit, 10), time_range=time_range)]


@mcp.tool()
def fetch_url(url: str, offset: int = 0) -> str:
    """Fetch a page's main content as Markdown (navigation and ads removed, code kept), 8000 characters at a time.
    If the page is longer, the result ends with the offset to pass for the next part; only continue if needed."""
    return _fetch_url(settings, url, max_chars=8000, offset=max(offset, 0))


@mcp.tool()
def kb_search(query: str, limit: int = 5) -> list[dict]:
    """Search the local knowledge base of curated Java/Spring best practices and saved research notes."""
    return [h.__dict__ for h in kb.search(query, limit=min(limit, 20))]


@mcp.tool()
def kb_save_note(title: str, content: str, source_url: str) -> str:
    """Save a verified, durable finding (Markdown) with the URL it came from, so later sessions can reuse it."""
    n = kb.add_note(title, content, source_url)
    return f"Saved {n} chunk(s) from {source_url}"


def run() -> None:
    if kb.count() == 0:
        kb.reindex()
    mcp.run("stdio")
