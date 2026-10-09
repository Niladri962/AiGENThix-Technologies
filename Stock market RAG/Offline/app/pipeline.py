"""The single entry point used by the API, the UI and the evaluation script.

Implements the request flow in SPEC.md section 7.
"""
from __future__ import annotations

import time
import uuid

from app.config import get_settings, static_model_name
from app.guardrails import (
    DISCLAIMER,
    REFUSE_NO_CONTEXT,
    check_input,
    check_output,
    cited_numbers,
)
from app.llm.base import get_provider
from app.memory import SessionMemory, rewrite_question
from app.prompts import build_messages
from app.retriever import retrieve
from app.router import route_context, route_input
from app.schemas import AnswerResponse, Citation, RetrievedChunk
from app.tracing import write_trace

_memory = SessionMemory()


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _build_citations(text: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    citations = []
    for n in cited_numbers(text):
        rc = chunks[n - 1]
        citations.append(
            Citation(n=n, title=rc.chunk.title, publisher=rc.chunk.publisher, url=rc.chunk.url, page=rc.chunk.page)
        )
    return citations


def answer(question: str, session_id: str | None = None) -> AnswerResponse:
    settings = get_settings()
    trace_id = uuid.uuid4().hex
    model = static_model_name(settings)
    latency = {"guard": 0, "rewrite": 0, "retrieve": 0, "generate": 0, "total": 0}
    total_start = time.perf_counter()

    def finish(
        route: str,
        guard_category: str | None,
        redacted_question: str,
        rewritten_question: str | None,
        retrieved: list[dict],
        refused: bool,
        refusal_category: str | None,
        answer_text: str,
        prompt_tokens: int,
        completion_tokens: int,
        citations: list[Citation],
        resolved_model: str,
    ) -> AnswerResponse:
        latency["total"] = _ms(total_start)
        write_trace(
            {
                "trace_id": trace_id,
                "ts": _now_iso(),
                "session_id": session_id,
                "question": redacted_question,
                "rewritten_question": rewritten_question,
                "route": route,
                "guard_category": guard_category,
                "pii_found": redacted_question != question,
                "retrieved": retrieved,
                "provider": settings.llm_provider,
                "model": resolved_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency,
                "refused": refused,
                "error": None,
            }
        )
        return AnswerResponse(
            answer=answer_text,
            citations=citations,
            refused=refused,
            refusal_category=refusal_category,
            trace_id=trace_id,
            provider=settings.llm_provider,
            model=resolved_model,
        )

    # 1. Redact PII, then classify. No retrieval, no LLM call if refused.
    g0 = time.perf_counter()
    guard = check_input(question)
    latency["guard"] = _ms(g0)
    redacted_question = guard.text

    if route_input(guard) == "refuse":
        return finish(
            route="refuse_input",
            guard_category=guard.category,
            redacted_question=redacted_question,
            rewritten_question=None,
            retrieved=[],
            refused=True,
            refusal_category=guard.category,
            answer_text=guard.message,
            prompt_tokens=0,
            completion_tokens=0,
            citations=[],
            resolved_model=model,
        )

    # 2. Rewrite follow-up questions using capped session history.
    history = _memory.history(session_id)
    capped_history = history[-settings.history_turns * 2 :]
    rewritten_question: str | None = None
    query_text = redacted_question
    r0 = time.perf_counter()
    if capped_history:
        llm = get_provider(settings)
        rewritten_question = rewrite_question(redacted_question, capped_history, llm)
        query_text = rewritten_question
    latency["rewrite"] = _ms(r0)

    # 3. Retrieve the top TOP_K chunks.
    rt0 = time.perf_counter()
    chunks = retrieve(query_text, settings.top_k)
    latency["retrieve"] = _ms(rt0)
    retrieved_trace = [{"chunk_id": rc.chunk.chunk_id, "score": rc.score} for rc in chunks]

    # 4. Score gate: refuse with no_context if nothing clears MIN_SCORE.
    if route_context(chunks, settings.min_score) == "refuse":
        return finish(
            route="refuse_context",
            guard_category="no_context",
            redacted_question=redacted_question,
            rewritten_question=rewritten_question,
            retrieved=retrieved_trace,
            refused=True,
            refusal_category="no_context",
            answer_text=REFUSE_NO_CONTEXT,
            prompt_tokens=0,
            completion_tokens=0,
            citations=[],
            resolved_model=model,
        )

    # 5. Build numbered context and generate.
    system, messages = build_messages(redacted_question, chunks, capped_history)
    llm = get_provider(settings)
    gen0 = time.perf_counter()
    result = llm.generate(system, messages)
    latency["generate"] = _ms(gen0)
    model = result.model

    # 6. Require a valid citation, else replace with the no_context refusal.
    out_guard = check_output(result.text, chunks)
    if not out_guard.allowed:
        return finish(
            route="refuse_output",
            guard_category="no_context",
            redacted_question=redacted_question,
            rewritten_question=rewritten_question,
            retrieved=retrieved_trace,
            refused=True,
            refusal_category="no_context",
            answer_text=REFUSE_NO_CONTEXT,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            citations=[],
            resolved_model=model,
        )

    # 7. Append the disclaimer, map citations, save memory, return.
    final_text = f"{out_guard.text} {DISCLAIMER}"
    citations = _build_citations(out_guard.text, chunks)
    _memory.add(session_id, "user", redacted_question)
    _memory.add(session_id, "assistant", final_text)

    return finish(
        route="answer",
        guard_category=None,
        redacted_question=redacted_question,
        rewritten_question=rewritten_question,
        retrieved=retrieved_trace,
        refused=False,
        refusal_category=None,
        answer_text=final_text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        citations=citations,
        resolved_model=model,
    )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
