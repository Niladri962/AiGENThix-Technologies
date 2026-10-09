"""Deterministic LLM double for offline tests. No network. See SPEC.md section 2."""
from __future__ import annotations

import re

from app.config import Settings
from app.guardrails import REFUSE_NO_CONTEXT
from app.prompts import REWRITE_SYSTEM
from app.schemas import LLMResult

_CITATION_RE = re.compile(r"\[(\d+)\]")


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, system: str, messages: list[dict]) -> LLMResult:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        if system == REWRITE_SYSTEM:
            # Rewriting: echo the latest question verbatim. Deterministic and
            # sufficient for tests, which only assert on call count.
            text = last_user.strip()
        elif _CITATION_RE.search(last_user):
            # Answering: cite the first available context block.
            n = min(int(m) for m in _CITATION_RE.findall(last_user))
            text = f"The source documents answer this directly [{n}]."
        else:
            text = REFUSE_NO_CONTEXT

        return LLMResult(
            text=text,
            prompt_tokens=len(last_user.split()),
            completion_tokens=len(text.split()),
            model=self.model,
        )
