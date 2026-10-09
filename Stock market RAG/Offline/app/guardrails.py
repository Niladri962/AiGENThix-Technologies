"""Input/output guardrails. See SPEC.md section 8. All patterns live here."""
from __future__ import annotations

import re

from app.schemas import GuardResult, RetrievedChunk

# ---- 8.4 Fixed strings (verbatim; never edit without updating SPEC.md) ----
REFUSE_ADVICE = "I can explain how the market works, but I can't give buy, sell or hold recommendations."
REFUSE_LIVE = "I don't have live market data. I can explain concepts and rules from my source documents."
REFUSE_NO_CONTEXT = "I couldn't find this in my source documents."
DISCLAIMER = "Educational information only, not investment advice."

# ---- 8.2 PII patterns, applied in this order ----
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[AADHAAR]"),
    (re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b"), "[PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
]

# ---- 8.1 Input classification, case-insensitive ----
_ADVICE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bshould i (buy|sell|hold|invest)\b",
        r"\bwhat (stock|share)s? (should|do) i (buy|sell|invest)\b",
        r"\bwhich stock\b",
        r"\bbest stock\b",
        r"\bbest share\b",
        r"\brecommend\b",
        r"\btarget price\b",
        r"\bwill it go up\b",
    ]
]
_LIVE_SUBJECT = re.compile(r"\b(price|level|nav|trading at)\b", re.IGNORECASE)
_LIVE_QUALIFIER = re.compile(r"\b(today|now|current|latest|live)\b", re.IGNORECASE)


def redact_pii(text: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _is_advice(text: str) -> bool:
    return any(p.search(text) for p in _ADVICE_PATTERNS)


def _is_live_data(text: str) -> bool:
    return bool(_LIVE_SUBJECT.search(text) and _LIVE_QUALIFIER.search(text))


def check_input(question: str) -> GuardResult:
    """Redact PII, then classify. Rule-based only; makes no LLM call."""
    redacted = redact_pii(question)

    if _is_advice(redacted):
        return GuardResult(allowed=False, category="advice", text=redacted, message=REFUSE_ADVICE)
    if _is_live_data(redacted):
        return GuardResult(allowed=False, category="live_data", text=redacted, message=REFUSE_LIVE)

    category = "pii" if redacted != question else None
    return GuardResult(allowed=True, category=category, text=redacted, message=None)


_CITATION_RE = re.compile(r"\[(\d+)\]")


def check_output(answer: str, chunks: list[RetrievedChunk]) -> GuardResult:
    """The answer must cite at least one valid context number, else refuse."""
    valid_range = range(1, len(chunks) + 1)
    cited = {int(n) for n in _CITATION_RE.findall(answer)}
    valid_cited = cited & set(valid_range)

    if not valid_cited:
        return GuardResult(
            allowed=False, category="no_context", text=REFUSE_NO_CONTEXT, message=REFUSE_NO_CONTEXT
        )

    def _keep(match: re.Match) -> str:
        n = int(match.group(1))
        return match.group(0) if n in valid_range else ""

    cleaned = _CITATION_RE.sub(_keep, answer)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return GuardResult(allowed=True, category=None, text=cleaned, message=None)


def cited_numbers(text: str) -> list[int]:
    """Unique citation numbers in first-appearance order."""
    seen: list[int] = []
    for n in _CITATION_RE.findall(text):
        n = int(n)
        if n not in seen:
            seen.append(n)
    return seen
