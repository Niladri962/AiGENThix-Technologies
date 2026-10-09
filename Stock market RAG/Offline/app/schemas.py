"""Data contracts from SPEC.md section 6. Names and fields are fixed."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class Document:
    doc_id: str
    title: str
    publisher: str
    url: str
    pages: list[tuple[int, str]]


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    publisher: str
    url: str
    page: int
    section: str
    text: str


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float  # cosine similarity


@dataclass
class GuardResult:
    allowed: bool
    category: str | None
    text: str
    message: str | None


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str


class Citation(BaseModel):
    n: int
    title: str
    publisher: str
    url: str
    page: int


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    refusal_category: str | None = None
    trace_id: str
    provider: str
    model: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: str | None = None
