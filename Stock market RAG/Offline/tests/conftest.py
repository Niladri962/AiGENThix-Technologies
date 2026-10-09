from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from tests.fixtures import make_pdf

DOC_A_PAGES = [
    (
        "Introduction to Demat Accounts\n\n"
        "A demat account holds securities in electronic form. It removes the "
        "need for physical share certificates and makes transactions faster "
        "and safer for investors across India.\n\n"
        "Opening a Demat Account\n\n"
        "An investor opens a demat account through a depository participant "
        "registered with a depository. The participant verifies identity "
        "documents and activates the account before trading can begin.\n\n"
        "Why Investors Need It\n\n"
        "Every investor who wants to buy or sell listed shares needs a demat "
        "account. Without one, settlement of trades in the secondary market "
        "is not possible under current regulations."
    ),
    (
        "Charges and Maintenance\n\n"
        "Depository participants charge annual maintenance fees for demat "
        "accounts. Investors should compare these charges before choosing a "
        "participant for their trading needs.\n\n"
        "Closing a Demat Account\n\n"
        "An investor can close a demat account by submitting a closure form "
        "to the depository participant once all holdings have been "
        "transferred or sold completely."
    ),
    (
        "Detailed Settlement Process\n\n"
        "The settlement process for a trade executed in the secondary market "
        "begins once the exchange matches a buy order with a sell order at "
        "an agreed price, after which the clearing corporation guarantees "
        "the trade and instructs the depositories to transfer the shares "
        "from the seller's demat account to the buyer's demat account while "
        "simultaneously arranging the corresponding transfer of funds "
        "between the two trading members on behalf of their respective "
        "clients within the prescribed settlement cycle."
    ),
]

DOC_B_PAGES = [
    (
        "What Is the NIFTY 50\n\n"
        "The NIFTY 50 is a stock market index that tracks fifty of the "
        "largest and most liquid companies listed on the National Stock "
        "Exchange of India.\n\n"
        "Rebalancing Schedule\n\n"
        "The index composition is reviewed and rebalanced on a semi-annual "
        "basis by the index committee, which may add or remove companies "
        "based on eligibility rules."
    ),
    (
        "Computation Method\n\n"
        "The NIFTY 50 is computed using the free float market "
        "capitalisation method, where only shares available for public "
        "trading are counted toward the index value.\n\n"
        "Eligibility Criteria\n\n"
        "A company must meet minimum trading frequency, market "
        "capitalisation and listing history requirements to be considered "
        "eligible for inclusion in the index."
    ),
]

TINY_PAGE = "Too Short\n\nx"  # under 50 characters after cleaning; must be skipped


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_manifest(manifest_path: Path, rows: list[dict]) -> None:
    fields = ["doc_id", "title", "publisher", "url", "licence_note", "filename", "sha256", "fetched_on"]
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture(autouse=True)
def _clear_provider_and_retriever_caches():
    """lru_cache keys are relative paths, so a chdir between tests is not
    enough on its own to isolate the Chroma collection and provider caches."""
    from app.llm.base import get_provider
    from app.retriever import _get_query_embedder, get_collection

    get_provider.cache_clear()
    get_collection.cache_clear()
    _get_query_embedder.cache_clear()
    yield
    get_provider.cache_clear()
    get_collection.cache_clear()
    _get_query_embedder.cache_clear()


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBED_MODEL", "fake")
    monkeypatch.setenv("CHUNK_SIZE", "200")
    monkeypatch.setenv("CHUNK_OVERLAP", "40")
    monkeypatch.setenv("TOP_K", "5")
    monkeypatch.setenv("MIN_SCORE", "0.2")
    monkeypatch.setenv("HISTORY_TURNS", "3")


@pytest.fixture
def project_dir(tmp_path, monkeypatch, fake_env):
    """A tmp project root with data/manifest.csv + data/raw/*.pdf, cwd set to it."""
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)

    doc_a_path = raw_dir / "doc_a.pdf"
    doc_b_path = raw_dir / "doc_b.pdf"
    make_pdf(doc_a_path, DOC_A_PAGES)
    make_pdf(doc_b_path, DOC_B_PAGES)

    rows = [
        {
            "doc_id": "doc_a",
            "title": "Demat Account Basics",
            "publisher": "Test Publisher A",
            "url": "https://example.com/doc_a",
            "licence_note": "test fixture",
            "filename": "doc_a.pdf",
            "sha256": _sha256(doc_a_path),
            "fetched_on": "2026-01-01",
        },
        {
            "doc_id": "doc_b",
            "title": "NIFTY 50 Overview",
            "publisher": "Test Publisher B",
            "url": "https://example.com/doc_b",
            "licence_note": "test fixture",
            "filename": "doc_b.pdf",
            "sha256": _sha256(doc_b_path),
            "fetched_on": "2026-01-01",
        },
    ]
    _write_manifest(tmp_path / "data" / "manifest.csv", rows)

    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def built_index(project_dir):
    from app.config import get_settings
    from ingest.build_index import build_index

    return build_index(get_settings())
