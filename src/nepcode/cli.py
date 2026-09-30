"""Command line: `nepcode serve | index | search | web | fetch`."""

from __future__ import annotations

import argparse
import json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nepcode")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the MCP server on stdio")
    sub.add_parser("index", help="rebuild the knowledge base index from knowledge/")
    p = sub.add_parser("search", help="query the knowledge base")
    p.add_argument("query")
    p = sub.add_parser("web", help="query the web through SearXNG")
    p.add_argument("query")
    p = sub.add_parser("fetch", help="fetch a URL as Markdown")
    p.add_argument("url")
    args = parser.parse_args(argv)

    if args.cmd == "serve":
        from .server import run

        run()
        return

    from .config import get_settings

    settings = get_settings()
    if args.cmd == "index":
        from .kb import KnowledgeBase

        print(f"Indexed {KnowledgeBase(settings).reindex()} chunks from {settings.kb_dir}")
    elif args.cmd == "search":
        from .kb import KnowledgeBase

        for h in KnowledgeBase(settings).search(args.query):
            print(f"[{h.score:.2f}] {h.source} :: {h.title}\n    {h.snippet}\n")
    elif args.cmd == "web":
        from .search import web_search

        print(json.dumps([r.to_dict() for r in web_search(settings, args.query)], indent=2))
    elif args.cmd == "fetch":
        from .fetch import fetch_url

        print(fetch_url(settings, args.url))


if __name__ == "__main__":
    main()
