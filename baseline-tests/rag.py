"""RAG baseline index: the lecture transcripts in ~400-token chunks (60-token overlap), embedded with
Qwen/Qwen3-Embedding-0.6B on the CPU (scripts/embed.py Embedder, the pipeline's embedder; chunks embedded with no
instruction, queries with an instruction, as the pipeline does for facts).

    python3 baseline-tests/rag.py build        # rag/chunks.json + rag/embeddings.json
    python3 baseline-tests/rag.py "question"   # print the top 8
"""
from __future__ import annotations

import json
import sys

import numpy as np

from chunks import chunks, lecture_titles
from common import OUT, PIPE, log

sys.path.insert(0, str(PIPE))
R = OUT / "rag"
R.mkdir(exist_ok=True)
MODEL = "Qwen/Qwen3-Embedding-0.6B"
QUERY_INSTRUCTION = "Given a learner's question about a lecture course, retrieve the transcript passages that answer it"
TARGET, OVERLAP, K = 400, 60, 8

_emb = None
_idx = None


def embedder():
    global _emb
    if _emb is None:
        from scripts.embed import Embedder
        _emb = Embedder(MODEL, cache=R / "embed_cache.jsonl", device="cpu")
    return _emb


def build():
    cs = chunks(TARGET, OVERLAP)
    titles = lecture_titles()
    for c in cs:
        c["title"] = titles[c["lecture"]]
    log(f"{len(cs)} chunks, mean {sum(c['tokens_est'] for c in cs) / len(cs):.0f} tokens")
    vecs = embedder().embed([c["text"] for c in cs])
    (R / "chunks.json").write_text(json.dumps(cs, ensure_ascii=False))
    (R / "embeddings.json").write_text(json.dumps(vecs))


def index():
    global _idx
    if _idx is None:
        cs = json.loads((R / "chunks.json").read_text())
        m = np.asarray(json.loads((R / "embeddings.json").read_text()), dtype="float32")
        _idx = (cs, m)
    return _idx


def retrieve(q: str, k: int = K) -> list[dict]:
    cs, m = index()
    qv = np.asarray(embedder().embed([q], instruction=QUERY_INSTRUCTION)[0], dtype="float32")
    s = m @ qv
    top = np.argsort(-s)[:k]
    return [{**cs[i], "score": round(float(s[i]), 4)} for i in top]


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build()
    else:
        for c in retrieve(sys.argv[1]):
            print(c["id"], c["score"], c["text"][:120])
