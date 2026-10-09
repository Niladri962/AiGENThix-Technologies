"""FastAPI endpoints. See SPEC.md section 10.1."""
from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings, static_model_name
from app.pipeline import answer as run_pipeline
from app.retriever import collection_count
from app.schemas import AnswerResponse, AskRequest

app = FastAPI(title="Indian Market RAG")


@app.post("/ask", response_model=AnswerResponse)
def ask(request: AskRequest) -> AnswerResponse:
    return run_pipeline(request.question, request.session_id)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": static_model_name(settings),
        "chunks": collection_count(settings),
    }
