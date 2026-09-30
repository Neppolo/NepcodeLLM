"""Runtime settings, read from environment variables so the MCP client config stays the single source of truth."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Sources we trust for Java / Spring answers. Results from these domains are ranked first.
DEFAULT_TRUSTED_DOMAINS = (
    "docs.oracle.com",
    "openjdk.org",
    "docs.spring.io",
    "spring.io",
    "github.com",
    "baeldung.com",
    "junit.org",
    "hibernate.org",
    "maven.apache.org",
    "docs.gradle.org",
    "owasp.org",
    "cheatsheetseries.owasp.org",
    "inside.java",
    "stackoverflow.com",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # "auto": SearXNG if it answers, otherwise the ddgs metasearch library (no Docker, no API key).
    search_backend: str = field(default_factory=lambda: os.environ.get("NEPCODE_SEARCH_BACKEND", "auto"))
    searxng_url: str = field(default_factory=lambda: os.environ.get("NEPCODE_SEARXNG_URL", "http://localhost:8888"))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("NEPCODE_DATA_DIR", _repo_root() / "data")))
    kb_dir: Path = field(default_factory=lambda: Path(os.environ.get("NEPCODE_KB_DIR", _repo_root() / "knowledge")))
    fetch_max_bytes: int = int(os.environ.get("NEPCODE_FETCH_MAX_BYTES", 3_000_000))
    fetch_cache_ttl_s: int = int(os.environ.get("NEPCODE_FETCH_CACHE_TTL", 7 * 24 * 3600))
    timeout_s: float = float(os.environ.get("NEPCODE_TIMEOUT", 20))
    trusted_domains: tuple[str, ...] = DEFAULT_TRUSTED_DOMAINS

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nepcode.sqlite"


def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
