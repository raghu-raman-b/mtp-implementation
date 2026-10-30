"""Stage 3: group sub-goals into objectives and a lecture goal; then course goals from the lecture goals."""
from __future__ import annotations

from . import prompts as P
from . import validate as V
from .context import Lec, Run
from .llm import Call


def _schema(seg_ids: list[str], lo: int, hi: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["objectives", "lecture_goal"], "properties": {
        "objectives": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
            "type": "object", "additionalProperties": False, "required": ["ability", "segments"], "properties": {
                "ability": {"type": "string", "maxLength": 200},
                "segments": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": seg_ids}}}}},
        "lecture_goal": {"type": "string", "maxLength": 250}}}


def _check(lec: Lec):
    order = [s.id for s in lec.segments]

    def check(x: dict) -> list[str]:
        errs = []
        seen = [sid for o in x["objectives"] for sid in o["segments"]]
        missing = [s for s in order if s not in seen]
        dup = sorted({s for s in seen if seen.count(s) > 1})
        if missing:
            errs.append(f"segments {missing} belong to no objective; every segment must be in exactly one")
        if dup:
            errs.append(f"segments {dup} are in more than one objective; every segment must be in exactly one")
        for i, o in enumerate(x["objectives"], 1):
            idx = sorted(order.index(s) for s in set(o["segments"]))
            if idx and idx != list(range(idx[0], idx[-1] + 1)):
                errs.append(f"objective {i} covers {o['segments']}, which is not a contiguous run of segments")
            errs += V.check_verb_first(_strip_prefix(o["ability"]), f"objective {i}")
        errs += V.check_verb_first(x["lecture_goal"], "lecture_goal")
        return errs
    return check


def _repair(lec: Lec, x: dict) -> list[list[str]]:
    """Code fallback: order objectives by their first segment and cut the segment list there."""
    order = [s.id for s in lec.segments]
    firsts = []
    for o in x["objectives"]:
        idx = [order.index(s) for s in o["segments"] if s in order]
        if idx and min(idx) not in [f for f, _ in firsts]:
            firsts.append((min(idx), o))
    firsts.sort(key=lambda t: t[0])
    if not firsts or firsts[0][0] != 0:
        firsts.insert(0, (0, {"ability": f"follow {lec.inp.title}"}))
    out = []
    for k, (f, o) in enumerate(firsts):
        end = firsts[k + 1][0] if k + 1 < len(firsts) else len(order)
        o["segments"] = order[f:end]
        out.append(o)
    return out


def _strip_prefix(text: str) -> str:
    t = text.strip().rstrip(".")
    for p in ("you'll be able to ", "you will be able to ", "be able to "):
        if t.lower().startswith(p):
            t = t[len(p):]
    return t


def _ability(text: str) -> str:
    t = _strip_prefix(text)
    return "You'll be able to " + t[:1].lower() + t[1:] + "."


def run(R: Run):
    calls = []
    for lec in R.lectures:
        n = len(lec.segments)
        lo, hi = min(2, n), min(6, n)
        subgoals = "\n".join(f"{s.id}: {s.subgoal}" for s in lec.segments)
        prompt = P.GOALS[2].format(role=P.ROLE, title=lec.inp.title, subgoals=subgoals, lo=lo, hi=hi)
        calls.append(Call(key=f"{lec.id}/goals", lecture_id=lec.id, prompt=prompt,
                          schema=_schema([s.id for s in lec.segments], lo, hi),
                          prompt_id=P.GOALS[0], prompt_version=P.GOALS[1], check=_check(lec)))
    for o in R.llm.run("stage3_goals", calls, "goal hierarchy"):
        lec = R.lec(o.call.lecture_id)
        R.record(o, "stage3_goals", f"{lec.id}.goal_hierarchy")
        x = o.parsed
        if x is None:
            R.flag(lec.id, f"goal hierarchy failed ({o.errors}); one objective per segment")
            x = {"objectives": [{"ability": s.subgoal, "segments": [s.id]} for s in lec.segments],
                 "lecture_goal": f"Understand {lec.inp.title}"}
        objs = x["objectives"]
        if not o.ok:
            R.flag(lec.id, f"goal hierarchy repaired by code after failed checks: {o.errors}")
            objs = _repair(lec, x)
        lec.lecture_goal = x["lecture_goal"].strip().rstrip(".") + "."
        lec.objectives = []
        for i, ob in enumerate(objs, 1):
            oid = f"O{i}"
            lec.objectives.append({"id": oid, "text": _ability(ob["ability"]), "segment_ids": list(ob["segments"])})
            for sid in ob["segments"]:
                lec.seg(sid).objective_id = oid
        R.log(f"  {lec.id}: {len(lec.objectives)} objectives; goal: {lec.lecture_goal}")

    # course goals, bottom-up from the lecture goals (one call per course)
    n = len(R.lectures)
    lids = [l.id for l in R.lectures]
    lo, hi = min(2, n), min(6, n)
    schema = {"type": "object", "additionalProperties": False, "required": ["goals"], "properties": {
        "goals": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
            "type": "object", "additionalProperties": False, "required": ["goal", "lectures"], "properties": {
                "goal": {"type": "string", "maxLength": 250},
                "lectures": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": lids}}}}}}}

    def check(x):
        errs = [e for i, g in enumerate(x["goals"], 1) for e in V.check_verb_first(g["goal"], f"goal {i}")]
        covered = {l for g in x["goals"] for l in g["lectures"]}
        if set(lids) - covered:
            errs.append(f"lectures {sorted(set(lids) - covered)} serve no goal")
        return errs

    prompt = P.COURSE_GOALS[2].format(role=P.ROLE, course=R.course.title, lo=lo, hi=hi, lectures="\n".join(
        f"{l.id} ({l.inp.title}): {l.lecture_goal}" for l in R.lectures))
    o, = R.llm.run("stage3_goals", [Call(key="course/goals", lecture_id="_course", prompt=prompt, schema=schema,
                                         prompt_id=P.COURSE_GOALS[0], prompt_version=P.COURSE_GOALS[1],
                                         check=check)], "course goals")
    R.record(o, "stage3_goals", "course.goals")
    goals = (o.parsed or {"goals": [{"goal": f"Understand {R.course.title}", "lectures": lids}]})["goals"]
    R.course_goals = [{"id": f"G{i}", "text": g["goal"].strip().rstrip(".") + ".",
                       "lecture_ids": [l for l in lids if l in g["lectures"]]} for i, g in enumerate(goals, 1)]
    R.dump("stage3_goals", {"course_goals": R.course_goals,
                            **{l.id: {"lecture_goal": l.lecture_goal, "objectives": l.objectives} for l in R.lectures}})
