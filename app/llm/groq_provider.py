"""Groq SDK provider (online mode). See SPEC.md section 2, 9."""
from __future__ import annotations

from app.config import Settings
from app.schemas import LLMResult


class GroqProvider:
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")

        from groq import Groq

        self.settings = settings
        self.model = settings.groq_model
        self._client = Groq(api_key=settings.groq_api_key)

        available = {m.id for m in self._client.models.list().data}
        if self.model not in available:
            raise ValueError(
                f"GROQ_MODEL={self.model!r} is not available from Groq. "
                f"Available models: {sorted(available)}"
            )

    def generate(self, system: str, messages: list[dict]) -> LLMResult:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        choice = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResult(
            text=choice,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=self.model,
        )
