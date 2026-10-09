"""Prompt assembly. See SPEC.md section 9."""
from __future__ import annotations

from app.guardrails import REFUSE_NO_CONTEXT
from app.schemas import RetrievedChunk

SYSTEM_PROMPT = (
    "You are an assistant that explains how the Indian stock market works, "
    "using only the numbered context blocks supplied with each question. "
    f'If the context does not contain the answer, reply with exactly "{REFUSE_NO_CONTEXT}" '
    "and nothing else. "
    "Put a citation like [1] after every factual sentence, naming the context "
    "block it came from. "
    "Give no advice, no predictions and no prices. "
    "Write plain English, at most 150 words, with no tables."
)

REWRITE_SYSTEM = (
    "Rewrite the user's latest question as a standalone question, using the "
    "conversation history for context. Reply with only the rewritten question."
)


def _format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = [
        f"[{i}] {rc.chunk.title} (p.{rc.chunk.page})\n{rc.chunk.text}"
        for i, rc in enumerate(chunks, start=1)
    ]
    return "\n\n".join(blocks)


def build_messages(
    question: str, chunks: list[RetrievedChunk], history: list[dict]
) -> tuple[str, list[dict]]:
    context = _format_context(chunks)
    messages = [{"role": turn["role"], "content": turn["text"]} for turn in history]
    messages.append(
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
    )
    return SYSTEM_PROMPT, messages
