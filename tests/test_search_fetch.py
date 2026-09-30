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
