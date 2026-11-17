"""Citations in the answers, and the course text at each one (for the judge).

Each system's citations become (claim, lecture, time):
- ours: qa's citations (each a fact with its lecture, start time and text); the claim is the answer sentence that
  carries the "(lecture N, m:ss)" label.
- rag, graphrag, plain: every "lecture N, m:ss" the answer writes; the claim is the sentence it closes.
The course text shown for a written citation is the transcript of that lecture from 30 s before the time to 240 s
after it (a RAG chunk is about 2.5 min, a GraphRAG text unit about 4 min, both labelled with their start), and the
two sentences of that window that share the most content words with the claim. "auto_overlap" is the share of the
claim's content words found anywhere in the window: a hint for the judge, not the verdict.
"""
from __future__ import annotations

import re
from functools import lru_cache

from chunks import lecture_keys, sentences

LECT_TIME = re.compile(r"[Ll]ecture\s+(\d+[a-z]?)\s*,\s*(?:at\s+)?(\d{1,2}:\d{2}(?::\d{2})?)")
STOP = set("""a an the of and or to in on for with by is are was were be been it its this that these those as at from
which what how why when where who can may not no do does into than then so such their there they them he she we you
your our also only more most other each any all both one two three four five six about between through used use uses
using also lecture course""".split())
BEFORE, AFTER = 30, 240


def secs(t: str) -> int:
    p = [int(x) for x in t.split(":")]
    return p[0] * 60 + p[1] if len(p) == 2 else p[0] * 3600 + p[1] * 60 + p[2]


def words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2}


@lru_cache(maxsize=None)
def lecture_sentences(k: str):
    return sentences(k) if k in set(lecture_keys()) else []


def window(k: str, t: float) -> list[dict]:
    return [s for s in lecture_sentences(k) if t - BEFORE <= (s["start"] or 0) <= t + AFTER]


def claims(answer: str):
    """(claim sentence, label text) for each "lecture N, m:ss" in the answer."""
    out = []
    for m in LECT_TIME.finditer(answer):
        start = max(answer.rfind(". ", 0, m.start()), answer.rfind("\n", 0, m.start()))
        # the claim: the text since the end of the previous sentence (skipping the label's own parenthesis)
        prev = answer[:m.start()]
        cut = max(prev.rfind(". ", 0, max(0, len(prev) - 3)), prev.rfind("\n"))
        claim = prev[cut + 1:].strip(" (;*-") if cut >= 0 else prev.strip(" (;*-")
        out.append((claim[-400:], m.group(1), m.group(2)))
        del start
    return out


def written_citations(answer: str) -> list[dict]:
    out = []
    for claim, k, t in claims(answer):
        win = window(k, secs(t))
        cw = words(claim)
        best = sorted(win, key=lambda s: -len(cw & words(s["text"])))[:2]
        allw = set().union(*(words(s["text"]) for s in win)) if win else set()
        out.append({"claim": claim, "lecture": k, "time": t, "lecture_exists": k in set(lecture_keys()),
                    "window_sentences": len(win),
                    "best_sentences": [f'[{s["id"]}] {s["text"][:260]}' for s in best],
                    "auto_overlap": round(len(cw & allw) / len(cw), 2) if cw else None})
    return out


def ours_citations(rec: dict) -> list[dict]:
    from common import fmt_time
    out = []
    ans = rec.get("answer", "")
    for c in rec.get("citations", []):
        label = f'lecture {c["lecture"]}, {fmt_time(c["start"])}'
        i = ans.find(label)
        claim = ""
        if i >= 0:
            prev = ans[:i]
            cut = max(prev.rfind(". ", 0, max(0, len(prev) - 3)), prev.rfind("\n"))
            claim = prev[cut + 1:].strip(" (;*-")[-400:]
        cw, fw = words(claim), words(c["text"])
        out.append({"claim": claim, "lecture": c["lecture"], "time": fmt_time(c["start"]),
                    "id": c["fact"] or c["segment"], "source_text": c["text"][:400],
                    "auto_overlap": round(len(cw & fw) / len(cw), 2) if cw else None})
    return out
