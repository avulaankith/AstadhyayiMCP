"""Small offline server and explicit snapshot-management commands."""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from .adapters import PINNED_REVISION, load_active
from .domain import DataError
from .sync import sync


def default_data_dir() -> Path:
    configured = os.environ.get("ASHTADHYAYI_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "ashtadhyayi-mcp"


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Ashtadhyayi.com evidence via MCP")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("sync", help="Download and validate a pinned upstream snapshot")
    download.add_argument("--revision", default=PINNED_REVISION)
    download.add_argument(
        "--profile",
        choices=["core", "full"],
        default="full",
        help="full includes all stored dhātu/śabda paradigms; core is smaller",
    )
    sub.add_parser("serve", help="Run the offline stdio MCP server")
    http = sub.add_parser("serve-http", help="Run the public read-only Streamable HTTP MCP server")
    http.add_argument("--host", default="127.0.0.1")
    http.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    http.add_argument("--public-host", default=os.environ.get("ASHTADHYAYI_PUBLIC_HOST"))
    sub.add_parser("status", help="Validate and describe the active snapshot")
    demo = sub.add_parser("demo", help="Run the evidence-first demonstration MCP client")
    demo.add_argument("question")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    try:
        if args.command == "sync":
            manifest = sync(args.data_dir, args.revision, profile=args.profile)
            print(f"Synced {len(manifest.files)} files at {manifest.upstream_revision}")
            print("Source: Ashtadhyayi.com — Neelesh Bodas and contributors.")
        elif args.command == "status":
            corpus = load_active(args.data_dir)
            print(
                json.dumps(
                    {
                        "snapshot": corpus.snapshot.model_dump(),
                        "sutras": len(corpus.sutras),
                        "dhatus": len(corpus.dhatus),
                        "shabdas": len(corpus.shabdas),
                        "form_sources": len(corpus.form_coverage),
                        "unparsed_form_groups": sum(
                            s.data.unparsed_groups for s in corpus.form_coverage
                        ),
                        "credit": "Ashtadhyayi.com — Neelesh Bodas and contributors",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "serve":
            from .server import serve

            asyncio.run(serve(args.data_dir))
        elif args.command == "serve-http":
            import uvicorn

            from .http import create_http_app

            if not 1 <= args.port <= 65535:
                parser.error("port must be in 1..65535")
            uvicorn.run(
                create_http_app(args.data_dir, public_host=args.public_host),
                host=args.host,
                port=args.port,
                limit_concurrency=32,
                timeout_keep_alive=5,
            )
        else:
            from .demo import demonstrate

            print(asyncio.run(demonstrate(args.question, args.data_dir)))
    except (DataError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
