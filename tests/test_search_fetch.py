from nepcode.config import DEFAULT_TRUSTED_DOMAINS
from nepcode.fetch import extract_markdown
from nepcode.search import rank_results


def test_rank_results_dedupes_and_puts_trusted_first():
    raw = [
        {"url": "https://blog.example.com/a", "title": "Blog", "content": "x"},
        {"url": "https://docs.spring.io/spring-boot/", "title": "Docs", "content": "y"},
        {"url": "https://blog.example.com/a", "title": "Dup"},
        {"url": "https://evil-docs.spring.io.attacker.com/", "title": "Fake"},
        {"title": "no url"},
    ]
    results = rank_results(raw, DEFAULT_TRUSTED_DOMAINS, limit=10)
    assert [r.title for r in results] == ["Docs", "Blog", "Fake"]
    assert results[0].trusted and not results[2].trusted


def test_extract_markdown_keeps_main_content_and_code():
    html = """<html><body><nav>Home | About | Login</nav>
    <article><h1>Records in Java</h1>
    <p>Records are transparent carriers for immutable data, introduced as a standard feature in Java 16.
    They generate the constructor, accessors, equals, hashCode and toString automatically.</p>
    <pre><code>public record Point(int x, int y) {}</code></pre>
    <p>Use a compact constructor to validate arguments before the fields are assigned.</p></article>
    <footer>Copyright 2026</footer></body></html>"""
    md = extract_markdown(html)
    assert "Records are transparent carriers" in md
    assert "public record Point" in md
    assert "Login" not in md


def test_auto_backend_falls_back_to_ddgs_when_searxng_is_down(monkeypatch, tmp_path):
    import httpx

    from nepcode import search
    from nepcode.config import Settings

    def down(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    calls = {}

    def fake_ddgs(query, time_range, limit):
        calls["args"] = (query, time_range, limit)
        return [{"title": "Boot docs", "url": "https://docs.spring.io/x", "content": "c"},
                {"title": "Blog", "url": "https://blog.example.com/y", "content": "d"}]

    monkeypatch.setattr(search.httpx, "get", down)
    monkeypatch.setattr(search, "_ddgs", fake_ddgs)
    settings = Settings(data_dir=tmp_path, search_backend="auto")
    results = search.web_search(settings, "spring boot", limit=5, time_range="year")
    assert calls["args"] == ("spring boot", "year", 5)
    assert [r.title for r in results] == ["Boot docs", "Blog"] and results[0].trusted


def test_fetch_url_pages_through_long_content(monkeypatch, tmp_path):
    from nepcode import fetch
    from nepcode.config import Settings

    text = "".join(f"{i:04d}" for i in range(5000))  # 20000 chars
    monkeypatch.setattr(fetch, "_fetch_full", lambda settings, url, use_cache: text)
    s = Settings(data_dir=tmp_path)
    first = fetch.fetch_url(s, "https://example.com", max_chars=8000)
    assert first.startswith(text[:8000]) and "offset=8000" in first and "12000 more characters" in first
    last = fetch.fetch_url(s, "https://example.com", max_chars=8000, offset=16000)
    assert last == text[16000:]
