"""Transcript chunks with lecture and time labels (shared by the RAG and GraphRAG baselines).

Sentences are stage 0a's (the human-written subtitles split into sentences); a sentence's start time is its cue time,
or, when it begins inside a cue, the estimate stage 1b uses for segment boundaries (scripts/s1b_verify_segments.py
load_timing: the cue's time plus the words spoken before it at the course's speaking rate). A chunk is a run of whole
sentences of one lecture up to about `target` tokens (1.18 Gemma tokens per word, measured over the course), and
the next chunk starts `overlap` tokens back.
"""
from __future__ import annotations

import json
import sys

from common import DATA, PIPE

sys.path.insert(0, str(PIPE))
from scripts import lectures as lec  # noqa: E402
from scripts.s1b_verify_segments import load_timing  # noqa: E402

TOK_PER_WORD = 1.18


def lecture_keys() -> list[str]:
    return json.loads((DATA / "knowledge" / "index.json").read_text())["lectures"]


def lecture_titles() -> dict[str, str]:
    out = {}
    for k in lecture_keys():
        p = DATA / "knowledge" / "lectures" / f"{lec.stem_of(k)}.json"
        out[k] = json.loads(p.read_text())["title"]
    return out


def sentences(k: str) -> list[dict]:
    """[{"id", "text", "start"}] of lecture k, in order."""
    s = json.loads((DATA / "stage_0a_preprocess" / f"{lec.stem_of(k)}.json").read_text())
    timing = load_timing("nptel_vr", k, s)
    return [{"id": i, "text": t, "start": timing.before(n)[0]} for n, (i, t) in enumerate(s.items())]


def chunks(target: int = 400, overlap: int = 60) -> list[dict]:
    out = []
    for k in lecture_keys():
        ss = sentences(k)
        i = 0
        while i < len(ss):
            j, tok = i, 0
            while j < len(ss) and (tok == 0 or tok + len(ss[j]["text"].split()) * TOK_PER_WORD <= target):
                tok += len(ss[j]["text"].split()) * TOK_PER_WORD
                j += 1
            out.append({"id": f"{k}/C{len([c for c in out if c['lecture'] == k])}", "lecture": k,
                        "start": ss[i]["start"], "end_sentence": ss[j - 1]["id"], "first_sentence": ss[i]["id"],
                        "text": " ".join(x["text"] for x in ss[i:j]), "tokens_est": round(tok)})
            if j >= len(ss):
                break
            # step back about `overlap` tokens (at least one sentence forward)
            back, b = 0, j
            while b - 1 > i + 0 and back + len(ss[b - 1]["text"].split()) * TOK_PER_WORD <= overlap:
                b -= 1
                back += len(ss[b]["text"].split()) * TOK_PER_WORD
            i = max(b, i + 1)
    return out


if __name__ == "__main__":
    c = chunks(int(sys.argv[1]) if len(sys.argv) > 1 else 400, int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    print(len(c), sum(x["tokens_est"] for x in c) / len(c), c[0]["id"], c[0]["start"], c[1]["start"])
