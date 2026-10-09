"""Settings loaded from environment variables. See SPEC.md section 4."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    groq_api_key: str
    groq_model: str
    ollama_host: str
    ollama_model: str
    ollama_num_ctx: int
    embed_model: str
    embed_device: str
    chroma_dir: str
    collection: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    min_score: float
    history_turns: int
    max_tokens: int
    temperature: float
    trace_path: str


def get_settings() -> Settings:
    """Read settings fresh from the environment on every call.

    Not cached: tests change env vars between cases via monkeypatch, so a
    cached singleton would leak stale values across them.
    """
    return Settings(
        llm_provider=os.environ.get("LLM_PROVIDER", "ollama"),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        groq_model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen3.5:4b"),
        ollama_num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "4096")),
        embed_model=os.environ.get("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embed_device=os.environ.get("EMBED_DEVICE", "auto"),
        chroma_dir=os.environ.get("CHROMA_DIR", "data/chroma"),
        collection=os.environ.get("COLLECTION", "market_docs"),
        chunk_size=int(os.environ.get("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", "150")),
        top_k=int(os.environ.get("TOP_K", "5")),
        min_score=float(os.environ.get("MIN_SCORE", "0.40")),
        history_turns=int(os.environ.get("HISTORY_TURNS", "3")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "512")),
        temperature=float(os.environ.get("TEMPERATURE", "0.1")),
        trace_path=os.environ.get("TRACE_PATH", "logs/traces.jsonl"),
    )


def static_model_name(settings: Settings) -> str:
    """The configured model name without constructing a provider (no network)."""
    if settings.llm_provider == "groq":
        return settings.groq_model
    if settings.llm_provider == "ollama":
        return settings.ollama_model
    return "fake-model"
