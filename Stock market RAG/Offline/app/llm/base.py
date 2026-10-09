"""LLM provider protocol and factory. See SPEC.md section 2, 4, 6."""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.config import Settings
from app.schemas import LLMResult


class LLMProvider(Protocol):
    name: str

    def generate(self, system: str, messages: list[dict]) -> LLMResult: ...


@lru_cache(maxsize=4)
def get_provider(settings: Settings) -> LLMProvider:
    """Cached per distinct Settings value so Groq's startup model check
    (one network call) runs once per configuration, not once per request."""
    if settings.llm_provider == "groq":
        from app.llm.groq_provider import GroqProvider

        return GroqProvider(settings)
    if settings.llm_provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(settings)
    if settings.llm_provider == "fake":
        from app.llm.fake_provider import FakeProvider

        return FakeProvider(settings)
    raise ValueError(
        f"Unknown LLM_PROVIDER={settings.llm_provider!r}; expected one of groq, ollama, fake"
    )
