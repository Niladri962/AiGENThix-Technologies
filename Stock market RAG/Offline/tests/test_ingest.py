from __future__ import annotations

import csv
import itertools

import pytest

from app.config import get_settings
from ingest.build_index import MANIFEST_PATH, RAW_DIR, build_index
from ingest.chunk import chunk_document
from ingest.load import load_documents

FIELDS = {"chunk_id", "doc_id", "title", "publisher", "url", "page", "section", "text"}


def test_at01_index_has_metadata(project_dir):
    documents = load_documents(MANIFEST_PATH, RAW_DIR)
    assert len(documents) == 2

    all_chunks = []
    for doc in documents:
        chunks = chunk_document(doc, size=200, overlap=40)
        assert chunks
        all_chunks.extend(chunks)

    for chunk in all_chunks:
        for field in FIELDS:
            value = getattr(chunk, field)
            assert value not in (None, ""), f"{field} missing on {chunk.chunk_id}"

    result = build_index(get_settings())
    assert result["documents"] == 2
    assert result["chunks"] == len(all_chunks)


def test_at02_rebuild_is_idempotent(project_dir):
    settings = get_settings()
    first = build_index(settings)
    second = build_index(settings)
    assert first["chunks"] == second["chunks"]
    assert first["documents"] == second["documents"]


def test_at03_chunk_size_and_overlap(project_dir):
    documents = load_documents(MANIFEST_PATH, RAW_DIR)
    size, overlap = 200, 40
    doc_a = next(d for d in documents if d.doc_id == "doc_a")
    chunks = chunk_document(doc_a, size=size, overlap=overlap)

    for c in chunks:
        assert len(c.text) <= size * 1.1

    # Page 3 holds one long paragraph with no heading inside it, so it must
    # be split into more than one chunk with a genuine text overlap.
    page3 = [c for c in chunks if c.page == 3]
    assert len(page3) >= 2
    for prev, nxt in itertools.pairwise(page3):
        prev_words = prev.text.split()
        overlap_found = any(
            " ".join(prev_words[-n:]) in nxt.text
            for n in range(min(len(prev_words), 10), 0, -1)
        )
        assert overlap_found, f"no overlap between {prev.chunk_id} and {nxt.chunk_id}"


def test_at04_missing_file_stops_ingestion(project_dir):
    (project_dir / "data" / "raw" / "doc_a.pdf").unlink()
    with pytest.raises(FileNotFoundError):
        load_documents(MANIFEST_PATH, RAW_DIR)


def test_at04_bad_checksum_stops_ingestion(project_dir):
    manifest_path = project_dir / "data" / "manifest.csv"
    with open(manifest_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows[0]["sha256"] = "0" * 64
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError):
        load_documents(MANIFEST_PATH, RAW_DIR)
