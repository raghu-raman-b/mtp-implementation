"""Sentence embeddings: one small model for the concept registry and for runtime scoring."""
from __future__ import annotations

import numpy as np

EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
_model = None


def _device() -> str:
    # always the CPU: the LLM servers need the whole GPU, and a CUDA context in this process would cost ~0.5 GB
    return "cpu"


def release_gpu():
    """Move the embedding model off the GPU (the judge needs the whole card); later calls run on the CPU."""
    global _model
    if _model is not None:
        try:
            import torch
            _model = _model.to("cpu")
            torch.cuda.empty_cache()
        except Exception:
            _model = None


def embed(texts: list[str]) -> np.ndarray:
    global _model
    if not texts:
        return np.zeros((0, 768), dtype=np.float32)
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL, device=_device())
    return _model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False,
                         convert_to_numpy=True).astype(np.float32)
