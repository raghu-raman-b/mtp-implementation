"""Calibrate the open-answer scorer's m (keywords needed) and tau (similarity threshold) without a human.

1. generate_answers (generator model, right after stage 5): for a sample of open questions, write three student
   answers: good (covers every key point in the student's own words), partial (about half), wrong (plausible but
   misses or misunderstands the key points).
2. fit (code, after the judge): grid-search m and tau so the scorer puts good answers at >= 0.75, partial ones in
   [0.25, 0.75) and wrong ones below 0.25. Ties go to the setting closest to the doc's defaults (m=2, tau=0.6).
"""
from __future__ import annotations

import itertools

import numpy as np

import scorer

from .context import Run
from .embed import embed
from .llm import Call
from .s2_annotate import prefix

SAMPLE = 16
M_GRID = [1, 2, 3, 4]
TAU_GRID = [round(0.30 + 0.05 * i, 2) for i in range(12)]  # 0.30 .. 0.85
BANDS = {"good": (0.75, 1.01), "partial": (0.25, 0.75), "wrong": (-0.01, 0.25)}

TASK = """Task: write three answers to this open-ended question, as three different students would, in their own words \
(do not copy the reference answer):
Question: {q}
Reference answer: {ref}
Key points a good answer covers:
{kps}

- good: a correct answer that covers every key point.
- partial: a correct but incomplete answer that covers about half of the key points.
- wrong: a plausible-sounding answer that misses or misunderstands the key points.
Each answer is 2 to 5 sentences."""


def generate_answers(R: Run):
    oqs = [(lec, q) for lec in R.lectures for ph in lec.phases if ph["type"] == "constructive"
           for q in ph["open_questions"]]
    by_type = {}
    for lec, q in oqs:
        by_type.setdefault(q["question_type"], []).append((lec, q))
    sample = [x for x in itertools.chain.from_iterable(itertools.zip_longest(*by_type.values())) if x][:SAMPLE]
    schema = {"type": "object", "additionalProperties": False, "required": ["good", "partial", "wrong"],
              "properties": {k: {"type": "string", "maxLength": 1200} for k in ("good", "partial", "wrong")}}
    calls = []
    for lec, q in sample:
        seg = lec.seg(q["segment_ids"][0])
        task = TASK.format(q=q["prompt"], ref=q["reference_answer"],
                           kps="\n".join(f"- {k['text']}" for k in q["key_points"]))
        calls.append(Call(key=f"{lec.id}/{q['id']}/calibration", lecture_id=lec.id, prompt=prefix(R, lec, seg) + task,
                          schema=schema, prompt_id="calibrate.answers", prompt_version="1", required=False,
                          stage="stage6_calibrate", ctx={"lid": lec.id, "oq": q["id"]}))
    for o in R.llm.run("stage6_calibrate", calls, f"calibration answers ({len(calls)} questions)"):
        R.record(o, "stage6_calibrate", f"{o.call.lecture_id}.{o.call.ctx['oq']}.calibration")
        if o.parsed:
            R.calibration_answers.append({"lecture_id": o.call.ctx["lid"], "oq_id": o.call.ctx["oq"], **o.parsed})


def fit(R: Run) -> dict:
    default = {"m": 2, "tau": 0.6, "calibrated": False}
    rows = []  # (label, keyword hit counts per kp, keyword counts per kp, max sims per kp)
    for a in R.calibration_answers:
        lec = R.lec(a["lecture_id"])
        q = next((q for ph in lec.phases if ph["type"] == "constructive" for q in ph["open_questions"]
                  if q["id"] == a["oq_id"]), None)
        if q is None:  # the judge dropped this question
            continue
        K = embed([k["text"] for k in q["key_points"]])
        for label in ("good", "partial", "wrong"):
            ans = a[label]
            sents = scorer.sentences(ans)
            sims = (embed(sents) @ K.T).max(axis=0) if sents else np.zeros(len(K))
            hits = [len(scorer.keyword_hits(k["keywords"], ans)) for k in q["key_points"]]
            nkw = [len(scorer.keyword_words(k["keywords"])) for k in q["key_points"]]
            rows.append((label, hits, nkw, sims))
    if len(rows) < 6:
        return {**default, "note": "too few calibration answers; using the doc's defaults"}
    best = None
    for m, tau in itertools.product(M_GRID, TAU_GRID):
        right = 0
        for label, hits, nkw, sims in rows:
            cov = [(h >= min(m, n) and n > 0) or s >= tau for h, n, s in zip(hits, nkw, sims)]
            sc = sum(cov) / len(cov)
            lo, hi = BANDS[label]
            right += lo <= sc < hi
        key = (right, -abs(m - 2) - abs(tau - 0.6))
        if best is None or key > best[0]:
            best = (key, m, tau)
    (right, _), m, tau = best
    by_label = {}
    for label in BANDS:
        sub = [r for r in rows if r[0] == label]
        sc = [sum(((h >= min(m, n) and n > 0) or s >= tau) for h, n, s in zip(r[1], r[2], r[3])) / len(r[1]) for r in sub]
        by_label[label] = round(float(np.mean(sc)), 3) if sc else None
    return {"m": m, "tau": tau, "calibrated": True, "answers": len(rows), "agreement": round(right / len(rows), 3),
            "mean_score_by_label": by_label,
            "method": "LLM-written good/partial/wrong answers; grid search over m in 1-4 and tau in 0.30-0.85"}
