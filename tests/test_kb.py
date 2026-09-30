from pathlib import Path

import pytest

from nepcode.config import Settings
from nepcode.kb import KnowledgeBase, _fts_query, chunk_markdown


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir()
    (kb_dir / "spring.md").write_text(
        "# Spring\n\n## Injection\nUse constructor injection with final fields.\n\n"
        "## Persistence\nFix N+1 queries with JOIN FETCH or entity graphs.\n",
        encoding="utf-8",
    )
    return Settings(data_dir=tmp_path, kb_dir=kb_dir)


def test_chunk_markdown_tracks_heading_path_and_ignores_code_fences():
    text = "# A\nintro\n## B\n```\n# not a heading\n```\n### C\ndeep\n## D\nsibling"
    chunks = chunk_markdown(text, "x.md")
    assert [c.title for c in chunks] == ["A", "A > B", "A > B > C", "A > D"]
    assert "# not a heading" in chunks[1].body


def test_long_sections_are_split():
    body = "\n\n".join("word " * 100 for _ in range(10))
    chunks = chunk_markdown("# T\n" + body, "x.md")
    assert len(chunks) > 1
    assert all(len(c.body) <= 1800 for c in chunks)


def test_fts_query_quotes_terms():
    assert _fts_query('spring "boot" OR NEAR(') == '"spring" OR "boot" OR "or" OR "near"'
    assert _fts_query("!!!") == ""


def test_reindex_and_search(settings: Settings):
    kb = KnowledgeBase(settings)
    assert kb.reindex() == 2
    hits = kb.search("n+1 join fetch")
    assert hits and hits[0].title == "Spring > Persistence"


def test_saved_notes_survive_reindex(settings: Settings):
    kb = KnowledgeBase(settings)
    kb.reindex()
    kb.add_note("Virtual threads", "Pinning was removed in JDK 24 by JEP 491.", "https://openjdk.org/jeps/491")
    kb.reindex()
    hits = kb.search("pinning JEP 491")
    assert hits[0].source == "https://openjdk.org/jeps/491"
    assert hits[0].title == "Virtual threads"
