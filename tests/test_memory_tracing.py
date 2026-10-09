from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.pipeline import answer


def test_at13_followup_rewrites_once_and_caps_history(built_index, monkeypatch):
    from app.llm.fake_provider import FakeProvider

    calls = []
    original = FakeProvider.generate

    def counting(self, system, messages):
        calls.append(system)
        return original(self, system, messages)

    monkeypatch.setattr(FakeProvider, "generate", counting)

    session_id = "s1"
    answer("What is the NIFTY 50?", session_id)
    calls_before_followup = len(calls)

    answer("How often is it rebalanced?", session_id)

    from app.prompts import REWRITE_SYSTEM

    rewrite_calls = [c for c in calls[calls_before_followup:] if c == REWRITE_SYSTEM]
    assert len(rewrite_calls) == 1

    from app.pipeline import _memory

    settings = get_settings()
    cap = settings.history_turns * 2

    # Push well past the cap and confirm history is trimmed, not just small.
    for _ in range(5):
        answer("What is a demat account?", session_id)

    history = _memory.history(session_id)
    assert len(history) == cap


def test_at14_one_trace_per_request_no_raw_pii(built_index):
    settings = get_settings()
    trace_path = Path(settings.trace_path)
    before = trace_path.read_text(encoding="utf-8").splitlines() if trace_path.exists() else []

    question = "My PAN is ABCDE1234F. What is a demat account?"
    answer(question)

    after = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(after) == len(before) + 1

    record = json.loads(after[-1])
    expected_fields = {
        "trace_id", "ts", "session_id", "question", "rewritten_question", "route",
        "guard_category", "pii_found", "retrieved", "provider", "model",
        "prompt_tokens", "completion_tokens", "latency_ms", "refused", "error",
    }
    assert expected_fields <= record.keys()
    assert "ABCDE1234F" not in json.dumps(record)
    assert record["pii_found"] is True
