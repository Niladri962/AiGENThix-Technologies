"""Minimal end-to-end sanity check: ingest a small corpus, then ask a question."""
from __future__ import annotations

from app.guardrails import DISCLAIMER
from app.pipeline import answer


def test_end_to_end_sanity(built_index):
    assert built_index["documents"] == 2
    assert built_index["chunks"] > 0

    resp = answer("What is the NIFTY 50?")

    assert resp.refused is False
    assert resp.citations
    assert resp.answer.endswith(DISCLAIMER)
