from __future__ import annotations

import pytest

from app.config import get_settings
from app.guardrails import DISCLAIMER
from app.llm.base import get_provider
from app.llm.fake_provider import FakeProvider
from app.llm.ollama_provider import OllamaProvider
from app.pipeline import answer
from app.retriever import retrieve


def test_at05_retrieve_sorted_with_metadata(built_index):
    results = retrieve("What is a demat account?", k=1)
    assert len(results) <= 1

    results = retrieve("What is a demat account?", k=5)
    assert len(results) <= 5
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    for r in results:
        assert r.chunk.doc_id
        assert r.chunk.title
        assert r.chunk.publisher
        assert r.chunk.url
        assert r.chunk.page >= 1


def test_at06_supported_question_answers_with_citation(built_index):
    resp = answer("What is a demat account?")
    assert resp.refused is False
    assert resp.citations
    assert DISCLAIMER in resp.answer


def test_at07_provider_selection(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    assert isinstance(get_provider(get_settings()), FakeProvider)

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert isinstance(get_provider(get_settings()), OllamaProvider)

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError):
        get_provider(get_settings())

    monkeypatch.setenv("LLM_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        get_provider(get_settings())
