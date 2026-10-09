"""Retrieve/generate/refuse routing. See SPEC.md section 6, 7."""
from __future__ import annotations

from app.schemas import GuardResult, RetrievedChunk


def route_input(guard: GuardResult) -> str:
    return "retrieve" if guard.allowed else "refuse"


def route_context(chunks: list[RetrievedChunk], min_score: float) -> str:
    best = max((rc.score for rc in chunks), default=0.0)
    return "generate" if best >= min_score else "refuse"
