"""Ollama HTTP API provider (offline mode). See SPEC.md section 2, 9."""
from __future__ import annotations

import requests

from app.config import Settings
from app.schemas import LLMResult


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = settings.ollama_model

    def generate(self, system: str, messages: list[dict]) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "think": False,  # qwen3.5 thinking disabled, per section 2
            "options": {
                "num_ctx": self.settings.ollama_num_ctx,
                "temperature": self.settings.temperature,
                "num_predict": self.settings.max_tokens,
            },
        }
        response = requests.post(
            f"{self.settings.ollama_host}/api/chat", json=payload, timeout=120
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("message", {}).get("content", "")
        return LLMResult(
            text=text,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            model=self.model,
        )
