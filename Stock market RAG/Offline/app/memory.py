"""Per-session history and follow-up rewriting. See SPEC.md section 6, 7."""
from __future__ import annotations

from app.config import get_settings
from app.prompts import REWRITE_SYSTEM


class SessionMemory:
    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = {}

    def add(self, session_id: str | None, role: str, text: str) -> None:
        if session_id is None:
            return
        turns = self._sessions.setdefault(session_id, [])
        turns.append({"role": role, "text": text})
        cap = get_settings().history_turns * 2
        if len(turns) > cap:
            del turns[: len(turns) - cap]

    def history(self, session_id: str | None) -> list[dict]:
        if session_id is None:
            return []
        return list(self._sessions.get(session_id, []))


def rewrite_question(question: str, history: list[dict], llm) -> str:
    """Make a follow-up question standalone with one LLM call."""
    messages = [{"role": turn["role"], "content": turn["text"]} for turn in history]
    messages.append({"role": "user", "content": question})
    result = llm.generate(REWRITE_SYSTEM, messages)
    return result.text.strip() or question
