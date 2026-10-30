"""Runtime scorer for open answers (CPU only).

An answer is scored against the question's key points, not against one ideal answer. A key point counts as
covered if either test passes:
  - keywords:  the answer contains at least m words of the key point's keyword set (stemmed, with WordNet synonyms
               when available; all of them if the set is smaller than m);
  - meaning:   some sentence of the answer has cosine similarity >= tau with the key point's stored embedding.
Score = share of key points covered, shown as a tier. m and tau are calibrated at build time (see calibrate.py).

The same code scores at build time (calibration) and at runtime (serve.py), so the two always agree.
"""
from __future__ import annotations

import re

STOP = set("a an the of to in on for and or with by from is are be as at this that these those its it".split())
TIERS = [(0.75, "excellent", "Excellent: you showed understanding"),
         (0.5, "good", "Good: most of the way there"),
         (0.25, "acceptable", "Acceptable: some key ideas are missing"),
         (0.0, "try_again", "Try again: look at the points below")]


def stem(w: str) -> str:
    for suf in ("ization", "isation", "ations", "ation", "ings", "ing", "ies", "ied", "ers", "er", "es", "ed", "s", "ly"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return w


def words(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def sentences(text: str) -> list[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if len(s.strip().split()) >= 2]
    return parts or ([text.strip()] if text.strip() else [])


_wn = None


def _synonyms(w: str) -> set[str]:
    """Single-word WordNet synonyms (stemmed); empty if WordNet is not installed."""
    global _wn
    if _wn is None:
        try:
            from nltk.corpus import wordnet
            wordnet.synsets("test")
            _wn = wordnet
        except Exception:
            _wn = False
    if not _wn:
        return set()
    out = set()
    for syn in _wn.synsets(w)[:4]:
        for lemma in syn.lemma_names()[:6]:
            if "_" not in lemma:
                out.add(stem(lemma.lower()))
    return out


def keyword_words(keywords: list[str]) -> dict[str, set[str]]:
    """The key point's keyword set as words: each stemmed word with the forms that count as a match."""
    out = {}
    for k in keywords:
        for raw in re.findall(r"[a-z0-9]+", k.lower()):
            if raw in STOP or len(raw) < 3:
                continue
            w = stem(raw)
            out.setdefault(w, {w}).update(_synonyms(raw))
    return out


def keyword_hits(keywords: list[str], answer: str) -> list[str]:
    """Words of the keyword set that occur in the answer (directly or as a synonym)."""
    aw = set(words(answer))
    return [w for w, forms in keyword_words(keywords).items() if forms & aw]


def tier(score: float) -> dict:
    for lo, tid, label in TIERS:
        if score >= lo:
            return {"id": tid, "label": label}
    return {"id": TIERS[-1][1], "label": TIERS[-1][2]}


def score(answer: str, key_points: list[dict], m: int, tau: float, embed=None) -> dict:
    """key_points: [{text, keywords, embedding}]. embed: callable(list[str]) -> unit vectors, or None."""
    sims = None
    sents = sentences(answer)
    if embed is not None and sents and all(kp.get("embedding") for kp in key_points):
        import numpy as np
        A = np.asarray(embed(sents), dtype="float32")
        K = np.asarray([kp["embedding"] for kp in key_points], dtype="float32")
        sims = (A @ K.T).max(axis=0)
    out = []
    for j, kp in enumerate(key_points):
        hits = keyword_hits(kp["keywords"], answer)
        need = min(m, len(keyword_words(kp["keywords"])))
        by_kw = len(hits) >= need and need > 0
        sim = float(sims[j]) if sims is not None else None
        by_sim = sim is not None and sim >= tau
        out.append({"text": kp["text"], "covered": by_kw or by_sim, "keyword_hits": hits,
                    "similarity": round(sim, 3) if sim is not None else None,
                    "by": "keywords" if by_kw else ("meaning" if by_sim else None)})
    s = sum(k["covered"] for k in out) / max(1, len(out))
    return {"score": round(s, 3), "tier": tier(s), "key_points": out,
            "missed": [k["text"] for k in out if not k["covered"]], "used_embeddings": sims is not None}
