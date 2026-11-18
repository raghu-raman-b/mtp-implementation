"""Step 2, per part: one call for the objective and the key points, then one judge call for all of them.

    annotate   objective + 2-5 key points (tagged subject / course; course ones are dropped)
    judge      each: accurate, supported, about the subject, self-contained? Failed items are rewritten once (judge
               model) and judged again; a key point that still fails is dropped, an objective is kept and flagged
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pipeline import validate as V
from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Lecture, Part, Run
from .judge import Item, judge_unit, rewrite_items


class AnnKP(BaseModel):
    text: str = Field(max_length=400)
    sentence_ids: list[int] = Field(min_length=1, max_length=12)
    about: Literal["subject", "course"]


class Annotate(BaseModel):
    objective: str
    key_points: list[AnnKP] = Field(min_length=1, max_length=6)


def prefix(R: Run, lec: Lecture, p: Part) -> str:
    return P.excerpt_block(R.course.title, lec.inp.title, lec.numbered(p.a, p.b))


def _tidy_objective(text: str) -> str:
    t = strip_ids(text).strip().rstrip(".")
    return t[:1].upper() + t[1:]


def annotate(R: Run, lec: Lecture, p: Part):
    o = R.send("annotate", Call(key=f"{p.id}/annotate", lecture_id=lec.id, prompt=prefix(R, lec, p) + P.ANNOTATE[2],
                                schema=Annotate, prompt_id=P.ANNOTATE[0], prompt_version=P.ANNOTATE[1],
                                check=lambda x: [] if x.objective.strip() else ["the objective is empty"]))
    x: Annotate | None = o.parsed
    if x is None:
        R.flag(lec.id, f"{p.id}: objective and key points unusable ({o.errors})")
        p.objective = f"Follow part {p.n} of {lec.inp.title}"
        return
    p.objective = _tidy_objective(x.objective)
    kept = []
    for kp in x.key_points:  # a point that cites outside the part, or is about the course, is dropped
        ids = sorted({i for i in kp.sentence_ids if p.contains(i)})
        if not ids or not kp.text.strip():
            R.decisions.add("annotate", [p.id], "key point dropped", "cites no sentence of the part", o,
                            R.model_of("annotate"), text=kp.text)
            continue
        if kp.about == "course":
            R.decisions.add("annotate", [p.id], "key point dropped", "about the course, not the subject", o,
                            R.model_of("annotate"), text=kp.text)
            R.count("key_points_course_dropped")
            continue
        kept.append({"id": "", "text": strip_ids(kp.text), "sentences": ids})
    p.key_points = kept


KP_CRIT = ("Objective: ok only if it accurately states what a learner can do after watching this part, is specific "
           "to this part, and claims nothing the part does not teach. Key point: ok only if it is stated or clearly "
           "implied by its cited sentences, is about the subject (not about the course, the lecture or its "
           "organisation), and is one self-contained statement a learner can understand without the transcript.")


def judge(R: Run, lec: Lecture, p: Part):
    pre = prefix(R, lec, p)
    items = [Item({"text": p.objective}, "part_objective", [p.id])] + \
            [Item(dict(k), "key_point", [lec.s(i) for i in k["sentences"]]) for k in p.key_points]

    def show(it: Item) -> str:
        if it.kind == "part_objective":
            return f'Objective of this part: "{it.obj["text"]}"'
        return f'Key point: "{it.obj["text"]}" (cited sentences {it.obj["sentences"]})'

    def rewrite(failed: list[Item]) -> dict:
        out = {}
        objs = [(k, it) for k, it in enumerate(failed) if it.kind == "part_objective"]
        kps = [(k, it) for k, it in enumerate(failed) if it.kind == "key_point"]
        if objs:
            r = rewrite_items(R, key=f"{p.id}/objective", lid=lec.id, prefix=pre, failed=[it for _, it in objs],
                              show=show, item_schema={"properties": {"objective": {"type": "string"}}},
                              rules="An objective states what the learner can do after this part, as one phrase that "
                                    "starts with a verb, at most 20 words, claiming nothing the part does not teach.",
                              check=lambda it, x: [] if x["objective"].strip() else ["empty"])
            out.update({objs[k][0]: {"text": _tidy_objective(x["objective"])} for k, x in r.items()})
        if kps:
            r = rewrite_items(R, key=f"{p.id}/key_points", lid=lec.id, prefix=pre, failed=[it for _, it in kps],
                              show=show, item_schema={"properties": {"text": {"type": "string"},
                                                                     "sentence_ids": {"type": "array",
                                                                                      "items": {"type": "integer"}}}},
                              rules="A key point is one atomic, self-contained statement of a fact, claim, step or "
                                    "result of the subject, supported by the sentences it cites (give their numbers), "
                                    "understandable without the transcript, written as a fact of the subject.",
                              check=lambda it, x: V.check_ids(x["sentence_ids"], p.a, p.b, "the key point"))
            out.update({kps[k][0]: {"text": strip_ids(x["text"]), "sentences": sorted(set(x["sentence_ids"]))}
                        for k, x in r.items()})
        return out

    items = judge_unit(R, key=f"{p.id}/annotate", lid=lec.id, prefix=pre, items=items, show=show, criteria=KP_CRIT,
                       rewrite=rewrite)
    obj = items[0]
    p.objective = obj.obj["text"]
    if not obj.ok:
        R.flag(lec.id, f"{p.id}: objective kept after failing the judge")
    kept = []
    for it in items[1:]:
        if it.ok:
            kept.append({"id": "", "text": it.obj["text"], "sentences": it.obj["sentences"]})
        else:
            R.decisions.add("judge", it.subject, "key point dropped", "failed the judge after a rewrite",
                            text=it.obj["text"])
    for k, kp in enumerate(kept, 1):
        kp["id"] = f"{p.id}/K{k}"
    p.key_points = kept
    R.count("key_points", len(kept))
