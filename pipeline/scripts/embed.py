"""Text embeddings for the pipeline: the concept registry (stage 3) and the fact store (stage 4d).

    from scripts.embed import Embedder
    emb = Embedder("Qwen/Qwen3-Embedding-0.6B", cache=Path("output/<course>/stage_3_registry/embed/cache.jsonl"))
    vecs = emb.embed(["head-mounted display", "headset"])            # documents: no instruction
    q = emb.embed(["what is an HMD?"], instruction=QUERY)           # queries: with the task's instruction
    sim = sum(a * b for a, b in zip(vecs[0], vecs[1]))              # cosine: the vectors are L2-normalised

Embedder(model, cache=None, device=None). `model` is a sentence-transformers model ID (Hugging Face, or a local
folder), or "fake": a deterministic hashed bag of words (512 dimensions, no download, standard library only) for
plumbing tests. `device` is passed to sentence-transformers (None: CUDA when there is one). The model is loaded at the
first text that is not in the cache, so a rerun answered wholly from the cache never loads it.

embed(texts, instruction=None) -> list of vectors, one per text, in order, each L2-normalised (plain Python floats).

Instructions. Some models expect a one-sentence task instruction in front of a query and nothing in front of a
document. Qwen3-Embedding (and models trained the same way: Octen-Embedding, harrier-oss) take
"Instruct: <instruction>\\nQuery:<text>" on the query side, and their model card says leaving it out costs 1-5%;
documents get none. Their sentence-transformers config sets no default prompt, so nothing is added unless asked.
`instruction` is applied only for those models (INSTRUCT below) and ignored for the others (all-mpnet-base-v2 has no
instruction convention). For a symmetric comparison (two concepts, stage 3) both sides get the same instruction; for
retrieval (a question against facts, stage 4d) only the question does.

Cache. One JSON line per text: {"key", "model", "dim", "vec"}; key = sha256 of model, the instruction prefix actually
used, and the text; vec = the normalised float32 vector, base64. Vectors are always returned from what the cache
holds (a newly computed vector goes through the same float32 encoding first), so a first run and a rerun from the
cache see exactly the same numbers. A text already embedded is never embedded again.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import struct
import threading
from pathlib import Path

FAKE_DIM = 512
INSTRUCT = {   # model ID pattern -> query format (the instruction goes in {i}); other models take no instruction
    r"(?i)qwen3-embedding": "Instruct: {i}\nQuery:",
    r"(?i)octen-embedding": "Instruct: {i}\nQuery:",
    r"(?i)harrier-oss": "Instruct: {i}\nQuery:",
}


def _pack(vec: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vec)}f", *vec)).decode()


def _unpack(s: str) -> list[float]:
    raw = base64.b64decode(s)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def _normalise(vec) -> list[float]:
    vec = [float(x) for x in vec]
    n = math.sqrt(sum(x * x for x in vec))
    return [x / n for x in vec] if n else vec


def fake_vector(text: str) -> list[float]:
    """Hashed bag of words: each lower-case word (letters and digits) adds 1 to one of FAKE_DIM dimensions, sign and
    dimension from its hash. Texts that share words point the same way; nothing is learned."""
    vec = [0.0] * FAKE_DIM
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        h = int.from_bytes(hashlib.sha256(w.encode()).digest()[:8], "big")
        vec[h % FAKE_DIM] += 1.0 if (h >> 32) & 1 else -1.0
    return vec


class Embedder:
    def __init__(self, model: str = "Qwen/Qwen3-Embedding-0.6B", cache: Path | None = None,
                 device: str | None = None):
        self.model, self.device = model, device
        self.cache = Path(cache) if cache else None
        self.computed = 0               # texts embedded by the model in this process (not from the cache)
        self._st = None
        self._lock = threading.Lock()
        self._entries: dict[str, list[float]] | None = None

    # ---------------------------------------------------------------- public
    def prefix(self, instruction: str | None) -> str:
        """What goes in front of each text: the model's instruction format, or "" (no instruction, or a model
        without the convention)."""
        if not instruction:
            return ""
        for pat, fmt in INSTRUCT.items():
            if re.search(pat, self.model):
                return fmt.format(i=instruction)
        return ""

    def embed(self, texts: list[str], instruction: str | None = None) -> list[list[float]]:
        pre = self.prefix(instruction)
        keys = [self._key(pre, t) for t in texts]
        with self._lock:
            entries = self._load()
            todo = list(dict.fromkeys(k for k in keys if k not in entries))
            if todo:
                text_of = dict(zip(keys, texts))
                vecs = self._compute([pre + text_of[k] for k in todo])
                new = []
                for k, v in zip(todo, vecs):
                    packed = _pack(_normalise(v))
                    entries[k] = _unpack(packed)          # the cache's numbers, also on the first run
                    new.append({"key": k, "model": self.model, "dim": len(entries[k]), "vec": packed})
                self.computed += len(todo)
                if self.cache:
                    self.cache.parent.mkdir(parents=True, exist_ok=True)
                    with self.cache.open("a") as f:
                        f.writelines(json.dumps(r) + "\n" for r in new)
            return [list(entries[k]) for k in keys]

    # ---------------------------------------------------------------- internals
    def _key(self, prefix: str, text: str) -> str:
        return hashlib.sha256(json.dumps([self.model, prefix, text]).encode()).hexdigest()[:24]

    def _load(self) -> dict:
        if self._entries is None:
            self._entries = {}
            if self.cache and self.cache.exists():
                for line in self.cache.read_text().splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        if rec.get("model") == self.model:
                            self._entries[rec["key"]] = _unpack(rec["vec"])
        return self._entries

    def _compute(self, texts: list[str]) -> list:
        if self.model == "fake":
            return [fake_vector(t) for t in texts]
        if self._st is None:
            from sentence_transformers import SentenceTransformer   # only for real models
            self._st = SentenceTransformer(self.model, device=self.device)
        return self._st.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True,
                               show_progress_bar=len(texts) > 256).tolist()
