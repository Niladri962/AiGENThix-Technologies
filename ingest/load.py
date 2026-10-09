"""Manifest/checksum validation and PDF loading. See SPEC.md sections 5.1, 5.4."""
from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

from app.schemas import Document

MIN_PAGE_CHARS = 50
# A line repeated on more than this fraction of a document's pages is treated
# as a running header/footer and stripped from every page.
BOILERPLATE_RATIO = 0.5
BOILERPLATE_MAX_LEN = 100


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_pages(path: Path) -> list[tuple[int, str]]:
    pages = []
    with fitz.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            pages.append((i, page.get_text()))
    return pages


def _clean_pages(raw_pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    page_lines = [(n, [ln.strip() for ln in text.splitlines()]) for n, text in raw_pages]

    boilerplate = set()
    if len(page_lines) > 1:
        counts = Counter()
        for _, lines in page_lines:
            for ln in lines:
                if ln and len(ln) <= BOILERPLATE_MAX_LEN:
                    counts[ln] += 1
        threshold = max(2, int(len(page_lines) * BOILERPLATE_RATIO))
        boilerplate = {ln for ln, c in counts.items() if c >= threshold}

    cleaned: list[tuple[int, str]] = []
    for page_no, lines in page_lines:
        kept: list[str] = []
        for ln in lines:
            if ln in boilerplate:
                continue
            collapsed = " ".join(ln.split())
            kept.append(collapsed)
        # Collapse runs of blank lines to a single paragraph break.
        text_lines: list[str] = []
        blank_run = False
        for ln in kept:
            if ln == "":
                if not blank_run:
                    text_lines.append("")
                blank_run = True
            else:
                text_lines.append(ln)
                blank_run = False
        page_text = "\n".join(text_lines).strip()
        if len(page_text) < MIN_PAGE_CHARS:
            continue
        cleaned.append((page_no, page_text))
    return cleaned


def load_documents(manifest_path: str, raw_dir: str) -> list[Document]:
    """Validate the manifest against data/raw/ and return cleaned Documents.

    Raises FileNotFoundError or ValueError with a clear message if a listed
    file is missing or its checksum does not match.
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Manifest {manifest_path} has no rows")

    raw = Path(raw_dir)
    documents: list[Document] = []
    for row in rows:
        doc_id = row["doc_id"]
        file_path = raw / row["filename"]
        if not file_path.exists():
            raise FileNotFoundError(
                f"Missing source file for doc_id={doc_id!r}: {file_path} "
                f"(listed in {manifest_path})"
            )
        actual_sha256 = _sha256(file_path)
        expected_sha256 = row["sha256"]
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"Checksum mismatch for doc_id={doc_id!r} ({file_path}): "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        raw_pages = _extract_pages(file_path)
        pages = _clean_pages(raw_pages)
        documents.append(
            Document(
                doc_id=doc_id,
                title=row["title"],
                publisher=row["publisher"],
                url=row["url"],
                pages=pages,
            )
        )
    return documents
