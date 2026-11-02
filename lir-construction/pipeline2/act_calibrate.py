"""Calibrate the open-answer scorer (m keywords, tau similarity; see scorer.py) without a human, as in v1:
the generator writes a good, a partial and a wrong student answer for a sample of open questions; code then picks the
m and tau that put good answers at 0.75 or more, partial ones in [0.25, 0.75) and wrong ones below 0.25."""
from __future__ import annotations

import itertools

import numpy as np
from pydantic import BaseModel

import scorer
from pipeline.embed import EMBED_MODEL, embed
from pipeline.llm import Call

from . import prompts as P
from .context import Run

SAMPLE = 16
M_GRID = [1, 2, 3, 4]
TAU_GRID = [round(0.30 + 0.05 * i, 2) for i in range(12)]
BANDS = {"good": (0.75, 1.01), "partial": (0.25, 0.75), "wrong": (-0.01, 0.25)}


class Answers(BaseModel):
    good: str
    partial: str
    wrong: str


def calls(R: Run) -> list[tuple[str, Call]]:
    by_type: dict[str, list] = {}
    for lec in R.lectures:
        for q in R.acts[lec.id]["open_questions"]:
            by_type.setdefault(q["type"], []).append((lec, q))
    sample = [x for x in itertools.chain.from_iterable(itertools.zip_longest(*by_type.values())) if x][:SAMPLE]
    out = []
    for lec, q in sample:
        task = P.CALIBRATE[2].format(q=q["prompt"], ref=q["reference_answer"],
                                     kps="\n".join(f"- {k['text']}" for k in q["key_points"]))
        out.append(("calibrate", Call(key=f"{q['_key']}/calibration", lecture_id=lec.id, prompt=q["_block"] + task,
                                      schema=Answers, prompt_id=P.CALIBRATE[0], prompt_version=P.CALIBRATE[1],
                                      ctx={"kind": "calibrate", "key": q["_key"]})))
    return out


def take(R: Run, o):
    if o.parsed is not None:
        R.calibration = getattr(R, "calibration", [])
        R.calibration.append({"key": o.call.ctx["key"], **o.parsed.model_dump()})


def fit(R: Run) -> dict:
    default = {"m": 2, "tau": 0.6, "calibrated": False}
    qs = {q["_key"]: q for lec in R.lectures for q in R.acts[lec.id]["open_questions"]}
    rows = []
    for a in getattr(R, "calibration", []):
        q = qs.get(a["key"])
        if q is None:  # dropped by the judge
            continue
        K = embed([k["text"] for k in q["key_points"]])
        for label in BANDS:
            ans = a[label]
            sents = scorer.sentences(ans)
            sims = (embed(sents) @ K.T).max(axis=0) if sents else np.zeros(len(K))
            hits = [len(scorer.keyword_hits(k["keywords"], ans)) for k in q["key_points"]]
            nkw = [len(scorer.keyword_words(k["keywords"])) for k in q["key_points"]]
            rows.append((label, hits, nkw, sims))
    if len(rows) < 6:
        cal = {**default, "note": "too few calibration answers; defaults used"}
    else:
        def score(m, tau, r):
            return sum((h >= min(m, n) and n > 0) or s >= tau for h, n, s in zip(r[1], r[2], r[3])) / len(r[1])
        best = max(((sum(BANDS[r[0]][0] <= score(m, tau, r) < BANDS[r[0]][1] for r in rows),
                     -abs(m - 2) - abs(tau - 0.6)), m, tau) for m, tau in itertools.product(M_GRID, TAU_GRID))
        (right, _), m, tau = best
        cal = {"m": m, "tau": tau, "calibrated": True, "answers": len(rows), "agreement": round(right / len(rows), 3),
               "mean_score_by_label": {lb: round(float(np.mean([score(m, tau, r) for r in rows if r[0] == lb])), 3)
                                       for lb in BANDS},
               "method": "LLM-written good/partial/wrong answers; grid search over m in 1-4 and tau in 0.30-0.85"}
    return {"embedding_model": EMBED_MODEL,
            "open_answer": {**cal, "tiers": [{"min": lo, "id": t, "label": lb} for lo, t, lb in scorer.TIERS]},
            "concept_map": {"node_match_tau": 0.75, "label_bonus_tau": 0.6, "label_bonus": 0.25}}
