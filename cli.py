"""Simple CLI: index data/raw and ask questions against it.

Usage:
    python cli.py index
    python cli.py ask "What is a demat account?" [--session-id ID]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ingest.build_index import MANIFEST_PATH, RAW_DIR


def _cmd_index(_args: argparse.Namespace) -> int:
    manifest = Path(MANIFEST_PATH)
    raw_dir = Path(RAW_DIR)

    if not manifest.exists():
        print(f"Error: manifest not found at {manifest}. See SPEC.md section 5.1.", file=sys.stderr)
        return 1
    if not raw_dir.exists() or not any(raw_dir.glob("*.pdf")):
        print(f"Error: no source PDFs found in {raw_dir}.", file=sys.stderr)
        return 1

    from app.config import get_settings
    from ingest.build_index import build_index

    try:
        result = build_index(get_settings())
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Indexed {result['documents']} documents, {result['chunks']} chunks.")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    question = args.question.strip()
    if not question:
        print("Error: question must not be empty.", file=sys.stderr)
        return 1

    from app.pipeline import answer

    resp = answer(question, args.session_id)
    print(resp.answer)
    for c in resp.citations:
        print(f"  [{c.n}] {c.title} - {c.publisher}, p.{c.page} ({c.url})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cli.py")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("index", help=f"Build the vector index from {RAW_DIR} using {MANIFEST_PATH}")

    ask_parser = sub.add_parser("ask", help="Ask a question against the index")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--session-id", default=None)

    args = parser.parse_args(argv)
    if args.command == "index":
        return _cmd_index(args)
    return _cmd_ask(args)


if __name__ == "__main__":
    raise SystemExit(main())
