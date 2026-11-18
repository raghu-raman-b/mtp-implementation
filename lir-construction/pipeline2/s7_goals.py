"""Step 7: the goal hierarchy, bottom-up.

    lecture        one call per lecture: group the judged part objectives into contiguous learning objectives, and
                   the lecture goal. Code checks structure only (every part in exactly one objective, contiguous runs)
    judge lecture  one call: each objective and the goal accurate for what they group? Rewritten once; kept and
                   flagged if they still fail
    course         one call: course goals from every lecture's goal and objectives, each with the lectures that serve
                   it (every lecture serves one); judged in one call, rewritten once, kept and flagged if they fail
"""
from __future__ import annotations

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Lecture, Run
from .judge import Item, judge_unit, rewrite_items


def _tidy(text: str) -> str:
    return strip_ids(text).strip().rstrip(".")


def _schema(pids: list[str], lo: int, hi: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["objectives", "goal"], "properties": {
        "objectives": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
            "type": "object", "additionalProperties": False, "required": ["ability", "parts"], "properties": {
                "ability": {"type": "string"},
                "parts": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": pids}}}}},
        "goal": {"type": "string"}}}


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
        if not x["goal"].strip():
            errs.append("the goal is empty")
        return errs
    return check


def run_lecture(R: Run, lec: Lecture):
    n = len(lec.parts)
    lo, hi = min(2, n), min(6, n)
    parts = "\n".join(f"{p.id}: {p.objective}" for p in lec.parts)
    o = R.send("goals", Call(key=f"{lec.id}/goals", lecture_id=lec.id,
                             schema=_schema([p.id for p in lec.parts], lo, hi), check=_check(lec),
                             prompt=P.GOALS[2].format(role=P.ROLE, title=lec.inp.title, parts=parts, lo=lo, hi=hi),
                             prompt_id=P.GOALS[0], prompt_version=P.GOALS[1]))
    if o.parsed is None or not o.ok:
        R.flag(lec.id, f"objectives failed the checks ({o.errors}); one objective per part")
        R.decisions.add("goals", [lec.id], "one objective per part", f"answer failed the checks: {o.errors}", o,
                        R.model_of("goals"))
        groups = [{"ability": p.objective, "parts": [p.id]} for p in lec.parts]
        goal = (o.parsed or {}).get("goal") or f"Follow {lec.inp.title}"
    else:
        groups = sorted(o.parsed["objectives"], key=lambda g: min(lec.part(p).n for p in g["parts"]))
        goal = o.parsed["goal"]
    lec.objectives = []
    for i, g in enumerate(groups, 1):
        oid = f"{lec.id}/O{i}"
        text = _tidy(g["ability"])
        lec.objectives.append({"id": oid, "text": text[:1].lower() + text[1:],
                               "part_ids": sorted(set(g["parts"]), key=lambda p: lec.part(p).n)})
        for pid in g["parts"]:
            lec.part(pid).objective_id = oid
    lec.lecture_goal = _tidy(goal) + "."


def lecture_block(R: Run, lec: Lecture) -> str:
    parts = "\n".join(f"{p.id}: {p.objective}\n" + "\n".join(f"  - {k['text']}" for k in p.key_points)
                      for p in lec.parts)
    return f"{P.ROLE}\n\nLecture: {lec.inp.title}\nIts parts, each with its goal and key points:\n{parts}\n\n"


GOAL_CRIT = ("Learning objective: ok only if it accurately describes what a learner can do after the parts it "
             "groups, covers their main content, and claims nothing they do not teach. Overall goal: ok only if it "
             "accurately sums up what the lecture teaches, in line with its objectives, and claims nothing it does not "
             "teach.")


def judge_lecture(R: Run, lec: Lecture):
    pre = lecture_block(R, lec)
    items = [Item({"text": o["text"], "id": o["id"], "part_ids": o["part_ids"]}, "lecture_objective", [o["id"]])
             for o in lec.objectives] + [Item({"text": lec.lecture_goal}, "lecture_goal", [lec.id])]

    def show(it: Item) -> str:
        if it.kind == "lecture_goal":
            return f'Overall goal of the lecture: "{it.obj["text"]}"'
        return f'Learning objective for parts {it.obj["part_ids"]}: "You\'ll be able to {it.obj["text"]}"'

    def rewrite(failed):
        r = rewrite_items(R, key=f"{lec.id}/goals", lid=lec.id, prefix=pre, failed=failed, show=show,
                          item_schema={"properties": {"text": {"type": "string"}}},
                          rules="A learning objective completes \"You'll be able to ...\" (a verb in lower case) and "
                                "covers what its parts teach; the overall goal is one sentence that starts with a "
                                "verb. Neither claims anything the lecture does not teach.",
                          check=lambda it, x: [] if x["text"].strip() else ["empty"])
        return {k: {**failed[k].obj, "text": _tidy(x["text"])} for k, x in r.items()}

    items = judge_unit(R, key=f"{lec.id}/goals", lid=lec.id, prefix=pre, items=items, show=show, criteria=GOAL_CRIT,
                       rewrite=rewrite)
    for it, o in zip(items, lec.objectives):
        o["text"] = it.obj["text"][:1].lower() + it.obj["text"][1:]
        if not it.ok:
            R.flag(lec.id, f"{o['id']}: objective kept after failing the judge")
    g = items[-1]
    lec.lecture_goal = _tidy(g.obj["text"]) + "."
    if not g.ok:
        R.flag(lec.id, "lecture goal kept after failing the judge")


def _course_lines(R: Run) -> str:
    return "\n".join(f"{l.id} ({l.inp.title}): {l.lecture_goal}\n" + "\n".join(f"  - {o['text']}" for o in l.objectives)
                     for l in R.lectures)


def run_course(R: Run):
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

    o = R.send("goals", Call(key="course/goals", lecture_id="_course", schema=schema, check=check,
                             prompt=P.COURSE_GOALS[2].format(role=P.ROLE, course=R.course.title, lo=lo, hi=hi,
                                                             lectures=_course_lines(R)),
                             prompt_id=P.COURSE_GOALS[0], prompt_version=P.COURSE_GOALS[1]))
    goals = o.parsed["goals"] if o.parsed else [{"goal": f"Understand {R.course.title}", "lectures": lids}]
    if not o.ok:
        R.decisions.add("goals", ["course"], "kept despite failed checks" if o.parsed else "placeholder goal",
                        f"{o.errors}", o, R.model_of("goals"))
    R.course_goals = [{"id": f"G{i}", "text": _tidy(g["goal"]) + ".",
                       "lecture_ids": [l for l in lids if l in g["lectures"]]} for i, g in enumerate(goals, 1)]


def judge_course(R: Run):
    pre = (f"{P.ROLE}\n\nCourse: {R.course.title}\nIts lectures, each with its overall goal and learning "
           f"objectives:\n{_course_lines(R)}\n\n")

    def show(it: Item) -> str:
        return f'Course goal served by lectures {it.obj["lecture_ids"]}: "{it.obj["text"]}"'

    def rewrite(failed):
        r = rewrite_items(R, key="course/goals", lid="_course", prefix=pre, failed=failed, show=show,
                          item_schema={"properties": {"text": {"type": "string"}}},
                          rules="A course goal is one sentence that starts with a verb and sums up what a learner "
                                "gains from the lectures it lists.",
                          check=lambda it, x: [] if x["text"].strip() else ["empty"])
        return {k: {**failed[k].obj, "text": _tidy(x["text"]) + "."} for k, x in r.items()}

    items = judge_unit(R, key="course/goals", lid="_course", prefix=pre, show=show, rewrite=rewrite,
                       criteria="Course goal: ok only if it accurately sums up what a learner gains from the lectures "
                                "it lists and claims nothing they do not teach.",
                       items=[Item(dict(g), "course_goal", [g["id"]]) for g in R.course_goals])
    R.course_goals = [it.obj for it in items]
    R.dump("7_goals", {"course_goals": R.course_goals,
                       **{l.id: {"lecture_goal": l.lecture_goal, "objectives": l.objectives} for l in R.lectures}})
