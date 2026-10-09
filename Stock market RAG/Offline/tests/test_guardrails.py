from __future__ import annotations

from app.guardrails import REFUSE_NO_CONTEXT, check_input, check_output
from app.pipeline import answer
from app.schemas import Chunk, RetrievedChunk


def _no_llm(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("LLM must not be called for this refusal path")

    monkeypatch.setattr("app.pipeline.get_provider", _boom)


def test_at08_advice_refused_without_llm_call(built_index, monkeypatch):
    _no_llm(monkeypatch)
    resp = answer("Should I buy Reliance shares now?")
    assert resp.refused is True
    assert resp.refusal_category == "advice"


def test_at09_live_data_refused(built_index, monkeypatch):
    _no_llm(monkeypatch)
    resp = answer("What is the NIFTY 50 level today?")
    assert resp.refused is True
    assert resp.refusal_category == "live_data"


def test_at10_pii_redacted_before_llm(built_index, monkeypatch):
    seen_messages = []
    from app.llm.fake_provider import FakeProvider

    original_generate = FakeProvider.generate

    def spy(self, system, messages):
        seen_messages.append(messages)
        return original_generate(self, system, messages)

    monkeypatch.setattr(FakeProvider, "generate", spy)

    question = (
        "My PAN is ABCDE1234F, Aadhaar 1234 5678 9123, phone 9876543210 and "
        "email test@example.com. What is a demat account?"
    )
    resp = answer(question)

    blob = " ".join(m["content"] for msgs in seen_messages for m in msgs)
    assert "ABCDE1234F" not in blob
    assert "1234 5678 9123" not in blob
    assert "9876543210" not in blob
    assert "test@example.com" not in blob
    assert "[PAN]" in blob and "[AADHAAR]" in blob and "[PHONE]" in blob and "[EMAIL]" in blob
    assert resp.refused is False


def test_at10_redact_pii_patterns():
    text = check_input(
        "PAN ABCDE1234F, Aadhaar 123456789012, phone +91 9876543210, "
        "email a.b@example.co.in"
    ).text
    assert "[PAN]" in text
    assert "[AADHAAR]" in text
    assert "[PHONE]" in text
    assert "[EMAIL]" in text


def test_at11_off_topic_refused_without_llm_call(built_index, monkeypatch):
    _no_llm(monkeypatch)
    # Deliberately free of stopwords shared with the corpus, since the
    # FakeEmbedder hashes every word (no stopword removal).
    resp = answer("Describe photosynthesis chlorophyll chloroplast pigments.")
    assert resp.refused is True
    assert resp.refusal_category == "no_context"


def test_at12_no_citation_answer_becomes_refusal():
    chunk = Chunk(
        chunk_id="doc_a:1:0",
        doc_id="doc_a",
        title="t",
        publisher="p",
        url="u",
        page=1,
        section="",
        text="some text",
    )
    guard = check_output("This answer cites nothing at all.", [RetrievedChunk(chunk=chunk, score=0.9)])
    assert guard.allowed is False
    assert guard.text == REFUSE_NO_CONTEXT


def test_at12_pipeline_replaces_uncited_answer(built_index, monkeypatch):
    from app.llm.fake_provider import FakeProvider
    from app.schemas import LLMResult

    def no_citation(self, system, messages):
        return LLMResult(text="No citation here.", prompt_tokens=1, completion_tokens=1, model="fake-model")

    monkeypatch.setattr(FakeProvider, "generate", no_citation)

    resp = answer("What is a demat account?")
    assert resp.refused is True
    assert resp.refusal_category == "no_context"
    assert resp.answer == REFUSE_NO_CONTEXT
