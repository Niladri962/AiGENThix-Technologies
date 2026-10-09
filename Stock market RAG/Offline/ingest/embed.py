"""Embedding backends. See SPEC.md section 2: real + deterministic fake."""
from __future__ import annotations

import hashlib
import math
import re

from app.config import Settings

FAKE_DIM = 1024


class Embedder:
    def __init__(self, model_name: str, device: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device=device)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts), normalize_embeddings=True, convert_to_numpy=True
        )
        return vectors.tolist()


class FakeEmbedder:
    """Deterministic hashed bag-of-words vectors. No model download, no network."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * FAKE_DIM
            for word in re.findall(r"\w+", text.lower()):
                h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
                vec[h % FAKE_DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def _resolve_device(device_setting: str) -> str:
    if device_setting in ("cpu", "cuda"):
        return device_setting
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def get_embedder(settings: Settings, for_query: bool) -> Embedder | FakeEmbedder:
    """Query time is always CPU; ingestion resolves EMBED_DEVICE (auto/cpu/cuda)."""
    if settings.embed_model == "fake":
        return FakeEmbedder()
    device = "cpu" if for_query else _resolve_device(settings.embed_device)
    return Embedder(settings.embed_model, device)
