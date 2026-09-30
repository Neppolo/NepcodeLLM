"""Local knowledge base: curated Markdown notes + saved research, indexed with SQLite FTS5 (BM25).

Curated notes live in `knowledge/` (versioned in git). Notes the model saves while researching go to the
`learned` source so they can be reviewed and promoted into `knowledge/` later.
"""

from __future__ import annotations

import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

MAX_CHUNK_CHARS = 1800
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")


@dataclass
class Chunk:
    source: str
    title: str
    body: str


@dataclass
class Hit:
    source: str
    title: str
    snippet: str
    score: float


def chunk_markdown(text: str, source: str, root_title: str | None = None) -> list[Chunk]:
    """Split on headings, carrying the heading path as the chunk title; split long sections on blank lines.

    Headings inside fenced code blocks are ignored.
    """
    chunks: list[Chunk] = []
    path: list[str] = []
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        title = " > ".join(([root_title] if root_title else []) + path) or Path(source).stem
        for piece in _split_long(body):
            chunks.append(Chunk(source, title, piece))

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            del path[level - 1 :]
            path.append(m.group(2).strip())
        else:
            buf.append(line)
    flush()
    return chunks


def _split_long(body: str) -> list[str]:
    if len(body) <= MAX_CHUNK_CHARS:
        return [body]
    pieces, cur = [], ""
    for para in body.split("\n\n"):
        if cur and len(cur) + len(para) > MAX_CHUNK_CHARS:
            pieces.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        pieces.append(cur.strip())
    return pieces


def _fts_query(query: str) -> str:
    # Quote each term so user input can't inject FTS5 syntax; OR them so BM25 ranks by overlap.
    terms = re.findall(r"[\w.@#+-]+", query.lower())
    return " OR ".join(f'"{t}"' for t in terms)


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.settings = settings
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS kb USING fts5(source, title, body, origin UNINDEXED,"
                " added_at UNINDEXED, tokenize='porter unicode61')"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.settings.db_path)

    def reindex(self) -> int:
        """Rebuild the curated part of the index from `knowledge/`. Saved research notes are kept."""
        chunks: list[Chunk] = []
        for path in sorted(self.settings.kb_dir.rglob("*.md")):
            rel = path.relative_to(self.settings.kb_dir).as_posix()
            chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), rel))
        now = time.time()
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM kb WHERE origin = 'curated'")
            conn.executemany(
                "INSERT INTO kb VALUES (?, ?, ?, 'curated', ?)", [(c.source, c.title, c.body, now) for c in chunks]
            )
        return len(chunks)

    def add_note(self, title: str, body: str, source_url: str) -> int:
        chunks = chunk_markdown(body, source_url, root_title=title)
        now = time.time()
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                "INSERT INTO kb VALUES (?, ?, ?, 'learned', ?)", [(c.source, c.title, c.body, now) for c in chunks]
            )
        return len(chunks)

    def search(self, query: str, limit: int = 5) -> list[Hit]:
        q = _fts_query(query)
        if not q:
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT source, title, snippet(kb, 2, '', '', ' ... ', 64), bm25(kb, 1.0, 4.0, 1.0)"
                " FROM kb WHERE kb MATCH ? ORDER BY bm25(kb, 1.0, 4.0, 1.0) LIMIT ?",
                (q, limit),
            ).fetchall()
        return [Hit(source=r[0], title=r[1], snippet=r[2], score=-r[3]) for r in rows]

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT count(*) FROM kb").fetchone()[0]
