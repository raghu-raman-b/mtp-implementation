"""Quiz per part.

    plan    the model picks the key points worth testing (0 to MAX_QUIZ) and the item type of each
            (earlier lectures come back as spaced review after the part: act_spaced.py)
    write   one call per item; code puts the correct option at a fixed pseudo-random position and checks the format
            (options distinct, the correct one not much longer than the others, "?" where a question is asked)
    judge   answerable from the part, the marked answer right and the only right one, worth asking, explanations right
"""
from __future__ import annotations

import random
import re
import zlib

from pydantic import BaseModel, Field

from pipeline.llm import Call

from . import prompts as P
from .context import Lecture, Part, Run
from .judge import judge_fix, rewrite_call
from .s2_parts import prefix

MAX_QUIZ = 4
TYPES = ["multiple_choice", "true_false", "yes_no"]
LETTERS = "ABCD"


class MC(BaseModel):
    question: str
    correct: str
    wrong: list[str] = Field(min_length=3, max_length=3)
    explanation_correct: str
    explanations_wrong: list[str] = Field(min_length=3, max_length=3)


class TF(BaseModel):
    statement: str
    answer: str = Field(pattern="^(True|False)$")
    explanation_true: str
    explanation_false: str


class YN(BaseModel):
    question: str
    answer: str = Field(pattern="^(Yes|No)$")
    explanation_yes: str
    explanation_no: str


SPEC = {"multiple_choice": (P.QUIZ_MC, MC), "true_false": (P.QUIZ_TF, TF), "yes_no": (P.QUIZ_YN, YN)}


def format_errors(t: str, x) -> list[str]:
    """Format only: what a renderer needs to show the item correctly."""
    errs = []
    if t == "multiple_choice":
        opts = [x.correct] + x.wrong
        if len({re.sub(r"\W+", " ", o.lower()).strip() for o in opts}) < 4:
            errs.append("the four options must all be different")
        mean_wrong = sum(len(w) for w in x.wrong) / 3
        if len(x.correct) > 1.4 * mean_wrong + 15:
            errs.append(f"the correct option is much longer than the wrong ones ({len(x.correct)} vs about "
                        f"{mean_wrong:.0f} characters), which gives it away; make them similar in length")
        if not x.question.strip().endswith("?"):
            errs.append('the question must end with "?"')
    elif t == "true_false":
        if x.statement.strip().endswith("?"):
            errs.append("a true/false item is a statement, not a question")
    elif not x.question.strip().endswith("?"):
        errs.append('the question must end with "?"')
    return errs


def fields(t: str, x, key: str) -> dict:
    if t == "multiple_choice":
        opts = [x.correct] + x.wrong
        expl = [x.explanation_correct] + x.explanations_wrong
        order = list(range(4))
        random.Random(zlib.crc32(key.encode())).shuffle(order)
        return {"stem": x.question.strip(), "options": [opts[j].strip() for j in order],
                "correct_index": order.index(0), "explanations": [expl[j].strip() for j in order]}
    if t == "true_false":
        return {"stem": x.statement.strip(), "options": ["True", "False"], "correct_index": ["True", "False"].index(x.answer),
                "explanations": [x.explanation_true.strip(), x.explanation_false.strip()]}
    return {"stem": x.question.strip(), "options": ["Yes", "No"], "correct_index": ["Yes", "No"].index(x.answer),
            "explanations": [x.explanation_yes.strip(), x.explanation_no.strip()]}


def plan_calls(R: Run) -> list[tuple[str, Call]]:
    out = []
    for lec in R.lectures:
        for p in lec.parts:
            ids = [k["id"] for k in p.key_points]
            if not ids:
                continue
            hi = min(MAX_QUIZ, len(ids))
            schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
                "items": {"type": "array", "maxItems": hi, "items": {
                    "type": "object", "additionalProperties": False, "required": ["key_point", "type", "reason"],
                    "properties": {"key_point": {"type": "string", "enum": ids},
                                   "type": {"type": "string", "enum": TYPES}, "reason": {"type": "string"}}}}}}
            points = "\n".join(f"{k['id']}: {k['text']}" for k in p.key_points)

            def check(x):
                used = [i["key_point"] for i in x["items"]]
                return ["each item must test a different key point"] if len(set(used)) < len(used) else []
            out.append(("quiz_plan", Call(key=f"{p.id}/quiz_plan", lecture_id=lec.id, group=p.id, schema=schema,
                                          prompt=prefix(R, lec, p) + P.QUIZ_PLAN[2].format(points=points, hi=hi),
                                          prompt_id=P.QUIZ_PLAN[0], prompt_version=P.QUIZ_PLAN[1], check=check,
                                          ctx={"kind": "quiz_plan", "lec": lec, "part": p})))
    return out


def take_plan(R: Run, o):
    lec, p = o.call.ctx["lec"], o.call.ctx["part"]
    plan = (o.parsed or {}).get("items", []) if o.ok else []
    R.acts[lec.id]["parts"][p.id]["_plan"] = plan
    R.decisions.add("quiz_plan", [p.id], f"{len(plan)} item(s)",
                    "; ".join(f"{i['key_point']} {i['type']}: {i['reason']}" for i in plan) or
                    (f"no usable plan: {o.errors}" if not o.ok else "nothing worth testing"), o)


def _item_prompt(R: Run, lec: Lecture, p: Part, i: dict) -> tuple[str, str, list[str]]:
    """prompt, point text, sources"""
    kp = next(k for k in p.key_points if k["id"] == i["key_point"])
    spec, _ = SPEC[i["type"]]
    return (prefix(R, lec, p) + spec[2].format(point=kp["text"], rules=P.QUIZ_RULES), kp["text"],
            [lec.s(j) for j in kp["sentences"]])


def item_calls(R: Run) -> list[tuple[str, Call]]:
    out = []
    for lec in R.lectures:
        for p in lec.parts:
            for n, i in enumerate(R.acts[lec.id]["parts"][p.id].get("_plan", []), 1):
                prompt, point, sources = _item_prompt(R, lec, p, i)
                spec, schema = SPEC[i["type"]]
                out.append(("quiz", Call(key=f"{p.id}/quiz/{n}", lecture_id=lec.id, group=p.id, prompt=prompt,
                                         schema=schema, prompt_id=spec[0], prompt_version=spec[1],
                                         check=lambda x, t=i["type"]: format_errors(t, x),
                                         ctx={"kind": "quiz", "lec": lec, "part": p, "plan": i, "point": point,
                                              "sources": sources})))
    return out


def _build(R: Run, lec: Lecture, i: dict, x, key: str, point: str, sources: list[str]) -> dict:
    f = fields(i["type"], x, key)
    cids = R.matcher.find(" ".join([point, f["stem"], f["options"][f["correct_index"]]]), lec.pos)
    return {"type": i["type"], "key_point": i["key_point"], "concept_ids": cids, **f, "sources": sources}


def take_item(R: Run, o):
    lec, p, i = o.call.ctx["lec"], o.call.ctx["part"], o.call.ctx["plan"]
    if o.parsed is None or not o.ok:
        R.decisions.add("quiz", [p.id], "item dropped", f"failed the format checks: {o.errors}", o,
                        key_point=i["key_point"])
        return
    item = _build(R, lec, i, o.parsed, o.call.key, o.call.ctx["point"], o.call.ctx["sources"])
    item.update({"_key": o.call.key, "_prompt": o.call.prompt, "_plan": i, "_point": o.call.ctx["point"],
                 "_raw": o.parsed.model_dump_json()})
    R.acts[lec.id]["parts"][p.id]["quiz"].append(item)


def _show(it: dict) -> str:
    opts = "\n".join(f"{LETTERS[k]}. {o}" for k, o in enumerate(it["options"]))
    expl = "\n".join(f"{LETTERS[k]}: {e}" for k, e in enumerate(it["explanations"]))
    return (f"Quiz item ({it['type'].replace('_', ' ')}) testing: {it['_point']}\n{it['stem']}\n{opts}\n"
            f"Marked correct: {LETTERS[it['correct_index']]}\nExplanations:\n{expl}")


def judge_part(send, R: Run, lec: Lecture, p: Part, llm):
    acts = R.acts[lec.id]["parts"][p.id]
    pre = prefix(R, lec, p)
    kept = []
    for it in acts["quiz"]:
        i = it["_plan"]
        spec, schema = SPEC[i["type"]]

        def rw(x, reason, it=it, i=i, schema=schema, spec=spec):
            y = rewrite_call(send, R, llm, key=it["_key"], lid=lec.id, prompt=it["_prompt"], spec=spec, schema=schema,
                             previous=it["_raw"], reason=reason, check=lambda z: format_errors(i["type"], z))
            if y is None:
                return None
            new = _build(R, lec, i, y, it["_key"], it["_point"], it["sources"])
            return {**new, **{k: v for k, v in it.items() if k.startswith("_")}, "_raw": y.model_dump_json()}
        new, ok = judge_fix(send, R, llm, key=it["_key"], lid=lec.id, prefix=pre, item=it, show=_show,
                            criteria="ok is true only if the item is answerable from this part alone, the marked "
                                     "answer is "
                                     "correct and the only correct one, the item tests understanding of the subject "
                                     "that is worth asking (not trivia, not what the lecture or the instructor says), "
                                     "and every explanation is correct.",
                            subject=it["sources"], kind="quiz", rewrite=rw)
        if ok:
            kept.append(new)
        else:
            R.decisions.add("judge", it["sources"], "quiz item dropped", "failed the judge after a rewrite",
                            item=it["_key"])
    for n, it in enumerate(kept, 1):
        it["id"] = f"{p.id}/Q{n}"
    acts["quiz"] = kept
