"""Step 2: per part, two separate calls on the same prompt start: (a) the part's objective, (b) its key points."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pipeline import validate as V
from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Lecture, Part, Run


class Objective(BaseModel):
    objective: str


class KP(BaseModel):
    text: str
    sentence_ids: list[int] = Field(min_length=1, max_length=12)


class AnnKP(BaseModel):              # v1 pipeline/s2_annotate.py KP
    text: str = Field(max_length=300)
    sentence_ids: list[int] = Field(min_length=1, max_length=8)
    about: Literal["subject", "course"]


class KeyPoints(BaseModel):          # v1: 2 to 5
    key_points: list[AnnKP] = Field(min_length=2, max_length=5)


def prefix(R: Run, lec: Lecture, p: Part) -> str:
    return P.excerpt_block(R.course.title, lec.inp.title, lec.numbered(p.a, p.b))


def _check_kp(p: Part):
    def check(x: KeyPoints) -> list[str]:
        errs = []
        for i, kp in enumerate(x.key_points, 1):
            errs += V.check_ids(kp.sentence_ids, p.a, p.b, f"key point {i}")
            if not kp.text.strip():
                errs.append(f"key point {i} is empty")
        return errs
    return check


def run(R: Run):
    llm = R.llm("objective")
    if R.llm("key_points") is not llm:
        raise SystemExit("steps 'objective' and 'key_points' must use the same model (they share a prompt start)")
    calls = []
    for lec in R.lectures:
        for p in lec.parts:
            pre = prefix(R, lec, p)
            calls.append(Call(key=f"{p.id}/objective", lecture_id=lec.id, prompt=pre + P.OBJECTIVE[2], schema=Objective,
                              prompt_id=P.OBJECTIVE[0], prompt_version=P.OBJECTIVE[1], group=p.id,
                              check=lambda x: [] if x.objective.strip() else ["the objective is empty"],
                              ctx={"part": p, "kind": "objective"}))
            calls.append(Call(key=f"{p.id}/key_points", lecture_id=lec.id, prompt=pre + P.KEY_POINTS[2],
                              schema=KeyPoints, prompt_id=P.KEY_POINTS[0], prompt_version=P.KEY_POINTS[1], group=p.id,
                              check=_check_kp(p), ctx={"part": p, "kind": "key_points"}))
    for o in llm.run("v2_part_annotate", calls, "objective and key points per part"):
        lec, p = R.lec(o.call.lecture_id), o.call.ctx["part"]
        R.record(o, o.call.ctx["kind"], llm, o.call.key)
        if o.call.ctx["kind"] == "objective":
            if o.parsed is None:
                R.flag(lec.id, f"{p.id}: no usable objective ({o.errors})")
                p.objective = f"Follow part {p.n} of {lec.inp.title}"
            else:
                p.objective = strip_ids(o.parsed.objective).strip().rstrip(".")
                p.objective = p.objective[:1].upper() + p.objective[1:]
            continue
        x: KeyPoints | None = o.parsed
        if x is None:
            R.flag(lec.id, f"{p.id}: key points unusable ({o.errors}); none kept")
            continue
        kept = []
        for kp in x.key_points:  # after the retries, a point that still cites outside the part is dropped
            ids = sorted({i for i in kp.sentence_ids if p.contains(i)})
            if not ids or not kp.text.strip():
                R.decisions.add("key_points", [p.id], "key point dropped", "cites no sentence of the part",
                                o, llm.model, text=kp.text)
                continue
            if kp.about == "course":  # v2 keeps the subject only
                R.decisions.add("key_points", [p.id], "key point dropped", "about the course, not the subject",
                                o, llm.model, text=kp.text)
                R.count("key_points_course_dropped")
                continue
            kept.append({"id": f"{p.id}/K{len(kept) + 1}", "text": strip_ids(kp.text), "sentences": ids})
        p.key_points = kept
        R.count("key_points", len(kept))
    R.dump("2_parts", {l.id: [{"id": p.id, "objective": p.objective, "key_points": p.key_points} for p in l.parts]
                       for l in R.lectures})
