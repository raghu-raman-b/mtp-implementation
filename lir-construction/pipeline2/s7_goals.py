"""Step 7: the goal hierarchy, bottom-up, in three separate calls.

    7a objectives    per lecture: group the part objectives into contiguous learning objectives
    7b lecture goal  per lecture: one sentence from its objectives
    7c course goals  one call: goals from the lecture goals, each with the lectures that serve it
Code checks structure only: every part in exactly one objective, contiguous runs, every lecture serves a goal.
"""
from __future__ import annotations

from pydantic import BaseModel

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Lecture, Run


class Goal(BaseModel):
    goal: str


def _tidy(text: str) -> str:
    return strip_ids(text).strip().rstrip(".")


def _objectives_schema(pids: list[str], lo: int, hi: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["objectives"], "properties": {
        "objectives": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
            "type": "object", "additionalProperties": False, "required": ["ability", "parts"], "properties": {
                "ability": {"type": "string"},
                "parts": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": pids}}}}}}}


def _check(lec: Lecture):
    order = [p.id for p in lec.parts]

    def check(x: dict) -> list[str]:
        errs = []
        seen = [pid for o in x["objectives"] for pid in o["parts"]]
        missing = [p for p in order if p not in seen]
        dup = sorted({p for p in seen if seen.count(p) > 1})
        if missing:
            errs.append(f"parts {missing} belong to no objective; every part must be in exactly one")
        if dup:
            errs.append(f"parts {dup} are in more than one objective; every part must be in exactly one")
        for i, o in enumerate(x["objectives"], 1):
            idx = sorted(order.index(p) for p in set(o["parts"]))
            if idx != list(range(idx[0], idx[-1] + 1)):
                errs.append(f"objective {i} covers {o['parts']}, which is not a contiguous run of parts")
            if not o["ability"].strip():
                errs.append(f"objective {i} is empty")
        return errs
    return check


def run_objectives(R: Run):
    llm = R.llm("goals")
    calls = []
    for lec in R.lectures:
        n = len(lec.parts)
        lo, hi = min(2, n), min(6, n)
        parts = "\n".join(f"{p.id}: {p.objective}" for p in lec.parts)
        calls.append(Call(key=f"{lec.id}/objectives", lecture_id=lec.id, schema=_objectives_schema([p.id for p in lec.parts], lo, hi),
                          prompt=P.OBJECTIVES[2].format(role=P.ROLE, title=lec.inp.title, parts=parts, lo=lo, hi=hi),
                          prompt_id=P.OBJECTIVES[0], prompt_version=P.OBJECTIVES[1], check=_check(lec)))
    for o in llm.run("v2_goals", calls, "lecture objectives"):
        lec = R.lec(o.call.lecture_id)
        R.record(o, "goals", llm, o.call.key)
        if o.parsed is None or not o.ok:
            R.flag(lec.id, f"objectives failed the checks ({o.errors}); one objective per part")
            R.decisions.add("goals", [lec.id], "one objective per part", f"answer failed the checks: {o.errors}", o, llm.model)
            groups = [{"ability": p.objective, "parts": [p.id]} for p in lec.parts]
        else:
            groups = sorted(o.parsed["objectives"], key=lambda g: min(lec.part(p).n for p in g["parts"]))
        lec.objectives = []
        for i, g in enumerate(groups, 1):
            oid = f"{lec.id}/O{i}"
            text = _tidy(g["ability"])
            lec.objectives.append({"id": oid, "text": text[:1].lower() + text[1:],
                                   "part_ids": sorted(set(g["parts"]), key=lambda p: lec.part(p).n)})
            for pid in g["parts"]:
                lec.part(pid).objective_id = oid


def run_lecture_goals(R: Run):
    llm = R.llm("goals")
    calls = [Call(key=f"{lec.id}/goal", lecture_id=lec.id, schema=Goal, prompt_id=P.LECTURE_GOAL[0],
                  prompt_version=P.LECTURE_GOAL[1],
                  prompt=P.LECTURE_GOAL[2].format(role=P.ROLE, title=lec.inp.title,
                                                  objectives="\n".join(f"- {o['text']}" for o in lec.objectives)),
                  check=lambda x: [] if x.goal.strip() else ["the goal is empty"]) for lec in R.lectures]
    for o in llm.run("v2_goals", calls, "lecture goals"):
        lec = R.lec(o.call.lecture_id)
        R.record(o, "goals", llm, o.call.key)
        lec.lecture_goal = (_tidy(o.parsed.goal) + ".") if o.parsed else f"Follow {lec.inp.title}."


def run_course_goals(R: Run):
    llm = R.llm("goals")
    lids = [l.id for l in R.lectures]
    n = len(lids)
    lo, hi = min(2, n), min(6, n)
    schema = {"type": "object", "additionalProperties": False, "required": ["goals"], "properties": {
        "goals": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
            "type": "object", "additionalProperties": False, "required": ["goal", "lectures"], "properties": {
                "goal": {"type": "string"},
                "lectures": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": lids}}}}}}}

    def check(x):
        left = set(lids) - {l for g in x["goals"] for l in g["lectures"]}
        return [f"lectures {sorted(left)} serve no goal"] if left else []

    prompt = P.COURSE_GOALS[2].format(role=P.ROLE, course=R.course.title, lo=lo, hi=hi, lectures="\n".join(
        f"{l.id} ({l.inp.title}): {l.lecture_goal}" for l in R.lectures))
    o, = llm.run("v2_goals", [Call(key="course/goals", lecture_id="_course", prompt=prompt, schema=schema, check=check,
                                   prompt_id=P.COURSE_GOALS[0], prompt_version=P.COURSE_GOALS[1])], "course goals")
    R.record(o, "goals", llm, "course.goals")
    goals = o.parsed["goals"] if o.parsed else [{"goal": f"Understand {R.course.title}", "lectures": lids}]
    if not o.ok:
        R.decisions.add("goals", ["course"], "kept despite failed checks" if o.parsed else "placeholder goal",
                        f"{o.errors}", o, llm.model)
    R.course_goals = [{"id": f"G{i}", "text": _tidy(g["goal"]) + ".",
                       "lecture_ids": [l for l in lids if l in g["lectures"]]} for i, g in enumerate(goals, 1)]
    R.dump("7_goals", {"course_goals": R.course_goals,
                       **{l.id: {"lecture_goal": l.lecture_goal, "objectives": l.objectives} for l in R.lectures}})
