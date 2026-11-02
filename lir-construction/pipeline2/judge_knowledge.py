"""The judge on the knowledge layer (verifier). Key terms, definitions, merges, relations and labels are already
checked inside their steps; this covers the rest.

    run_parts            after step 2: each part's objective and each key point, against the part's transcript
                         (a key point that still fails is dropped; an objective is kept and flagged)
    run_goals_facets     after steps 5 and 7: lecture objectives, lecture goals, course goals (kept and flagged if
                         they still fail) and facets (a facet that still fails becomes a mention)
"""
from __future__ import annotations

from pydantic import BaseModel

from pipeline import validate as V
from pipeline.s2_annotate import strip_ids

from . import addr as A
from . import prompts as P
from .context import Lecture, Run
from .judge import judge_fix, rewrite_call
from .s2_parts import KP, Objective, prefix
from .s5_facets import Facet


class Ability(BaseModel):
    ability: str


class GoalText(BaseModel):
    goal: str


# ------------------------------------------------------------------ parts: objective and key points
def _part_job(R: Run, lec: Lecture, p, llm):
    pre = prefix(R, lec, p)

    def job(send):
        # objective
        def rw_obj(obj, reason):
            x = rewrite_call(send, R, llm, key=f"{p.id}/objective", lid=lec.id, prompt=pre + P.OBJECTIVE[2],
                             spec=P.OBJECTIVE, schema=Objective, previous=obj, reason=reason,
                             check=lambda x: [] if x.objective.strip() else ["the objective is empty"])
            return strip_ids(x.objective).strip().rstrip(".") if x else None
        obj, ok = judge_fix(send, R, llm, key=f"{p.id}/objective", lid=lec.id, prefix=pre, item=p.objective,
                            show=lambda o: f'The goal of this part for the learner: "{o}"',
                            criteria="ok is true only if this goal accurately states what a learner can do after "
                                     "watching this part, is specific to this part, and claims nothing the part does "
                                     "not teach.",
                            subject=[p.id], kind="part_objective", rewrite=rw_obj)
        p.objective = obj[:1].upper() + obj[1:]
        if not ok:
            R.flag(lec.id, f"{p.id}: objective kept after failing the judge")

        # key points
        kept = []
        for kp in p.key_points:
            def rw_kp(k, reason):
                x = rewrite_call(send, R, llm, key=f"{kp['id']}", lid=lec.id,
                                 prompt=pre + P.KP_REWRITE[2].format(text=k["text"], ids=k["sentences"]),
                                 spec=P.KP_REWRITE, schema=KP, previous=k["text"], reason=reason,
                                 check=lambda x: V.check_ids(x.sentence_ids, p.a, p.b, "the key point"))
                return {**k, "text": strip_ids(x.text), "sentences": sorted(set(x.sentence_ids))} if x else None
            new, ok = judge_fix(send, R, llm, key=kp["id"], lid=lec.id, prefix=pre, item=kp,
                                show=lambda k: f'Key point: "{k["text"]}"\nCited sentences: {k["sentences"]}',
                                criteria="ok is true only if the key point is stated or clearly implied by its cited "
                                         "sentences, is about the subject (not about the course, the lecture or its "
                                         "organisation), and is one self-contained statement a learner can "
                                         "understand without the transcript.",
                                subject=[lec.s(i) for i in kp["sentences"]], kind="key_point", rewrite=rw_kp)
            if ok:
                kept.append(new)
            else:
                R.decisions.add("judge", [lec.s(i) for i in kp["sentences"]], "key point dropped",
                                "failed the judge after a rewrite", item=kp["id"], text=kp["text"])
        for k, kp in enumerate(kept, 1):  # renumber: nothing refers to key points yet
            kp["id"] = f"{p.id}/K{k}"
        p.key_points = kept
    return job


def run_parts(R: Run):
    llm = R.llm("judge")
    jobs = [_part_job(R, lec, p, llm) for lec in R.lectures for p in lec.parts]
    llm.run_jobs("v2_judge_parts", jobs, f"judge objectives and key points ({len(jobs)} parts)")


# ------------------------------------------------------------------ goals and facets
def _lecture_block(R: Run, lec: Lecture) -> str:
    parts = "\n".join(f"{p.id}: {p.objective}\n" + "\n".join(f"  - {k['text']}" for k in p.key_points)
                      for p in lec.parts)
    return f"{P.ROLE}\n\nLecture: {lec.inp.title}\nIts parts, each with its goal and key points:\n{parts}\n\n"


def _lecture_goals_job(R: Run, lec: Lecture, llm):
    pre = _lecture_block(R, lec)

    def job(send):
        for o in lec.objectives:
            def rw(text, reason, o=o):
                x = rewrite_call(send, R, llm, key=o["id"], lid=lec.id,
                                 prompt=pre + P.OBJ_REWRITE[2].format(pids=o["part_ids"], text=text),
                                 spec=P.OBJ_REWRITE, schema=Ability, previous=text, reason=reason)
                return strip_ids(x.ability).strip().rstrip(".") if x else None
            text, ok = judge_fix(send, R, llm, key=o["id"], lid=lec.id, prefix=pre, item=o["text"],
                                 show=lambda t, o=o: f'Learning objective for parts {o["part_ids"]}: "You\'ll be able '
                                                     f'to {t}"',
                                 criteria="ok is true only if this objective accurately describes what a learner can "
                                          "do after the parts it groups, covers their main content, and claims "
                                          "nothing they do not teach.",
                                 subject=[o["id"]], kind="lecture_objective", rewrite=rw)
            o["text"] = text[:1].lower() + text[1:]
            if not ok:
                R.flag(lec.id, f"{o['id']}: objective kept after failing the judge")
        objs = "\n".join(f"- {o['text']}" for o in lec.objectives)

        def rw_goal(text, reason):
            x = rewrite_call(send, R, llm, key=f"{lec.id}/goal", lid=lec.id,
                             prompt=P.LECTURE_GOAL[2].format(role=P.ROLE, title=lec.inp.title, objectives=objs),
                             spec=P.LECTURE_GOAL, schema=GoalText, previous=text, reason=reason)
            return strip_ids(x.goal).strip().rstrip(".") + "." if x else None
        goal, ok = judge_fix(send, R, llm, key=f"{lec.id}/goal", lid=lec.id, prefix=pre, item=lec.lecture_goal,
                             show=lambda g: f"The lecture's learning objectives:\n{objs}\n\nOverall goal of the "
                                            f'lecture: "{g}"',
                             criteria="ok is true only if the overall goal accurately sums up what the lecture "
                                      "teaches, in line with its objectives, and claims nothing it does not teach.",
                             subject=[lec.id], kind="lecture_goal", rewrite=rw_goal)
        lec.lecture_goal = goal
        if not ok:
            R.flag(lec.id, "lecture goal kept after failing the judge")
    return job


def _course_goals_job(R: Run, llm):
    lectures = "\n".join(f"{l.id} ({l.inp.title}): {l.lecture_goal}" for l in R.lectures)
    pre = f"{P.ROLE}\n\nCourse: {R.course.title}\nIts lectures, each with its overall goal:\n{lectures}\n\n"

    def job(send):
        for g in R.course_goals:
            def rw(text, reason, g=g):
                x = rewrite_call(send, R, llm, key=f"course/{g['id']}", lid="_course",
                                 prompt=pre + P.COURSE_GOAL_REWRITE[2].format(lids=g["lecture_ids"], text=text),
                                 spec=P.COURSE_GOAL_REWRITE, schema=GoalText, previous=text, reason=reason)
                return strip_ids(x.goal).strip().rstrip(".") + "." if x else None
            text, ok = judge_fix(send, R, llm, key=f"course/{g['id']}", lid="_course", prefix=pre, item=g["text"],
                                 show=lambda t, g=g: f'Course goal served by lectures {g["lecture_ids"]}: "{t}"',
                                 criteria="ok is true only if the goal accurately sums up what a learner gains from "
                                          "the lectures it lists and claims nothing they do not teach.",
                                 subject=[g["id"]], kind="course_goal", rewrite=rw)
            g["text"] = text
    return job


def _facet_job(R: Run, lec: Lecture, p, facets: list, llm):
    pre = prefix(R, lec, p)
    C = R.registry.concepts

    def job(send):
        for cid, f in facets:
            c = C[cid]
            ids = [A.parse_sent(s)[1] for s in f["sentences"]]
            d = c.definition_as_of(R, lec.id)

            def rw(item, reason):
                named = [A.parse_sent(s)[1] for s in f["named_in"]]
                text = P.FACET[2].format(name=c.name, aliases=c.alias_text(), definition=d["text"] if d else "",
                                         ids=named)
                x = rewrite_call(send, R, llm, key=f["id"], lid=lec.id, prompt=pre + text, spec=P.FACET, schema=Facet,
                                 previous=item["says"], reason=reason,
                                 check=lambda x: [] if x.only_mentioned or (x.says.strip() and x.sentence_ids and all(
                                     p.contains(i) for i in x.sentence_ids)) else
                                 [f"give what the part teaches and sentence numbers in this part ({p.a} to {p.b}), or "
                                  f"set only_mentioned"])
                if x is None or x.only_mentioned:
                    return None
                return {**item, "says": strip_ids(x.says), "sentences": [lec.s(i) for i in sorted(set(x.sentence_ids))]}
            new, ok = judge_fix(send, R, llm, key=f["id"], lid=lec.id, prefix=pre, item=f,
                                show=lambda x: f'Concept "{c.name}". What this part teaches about it: "{x["says"]}" '
                                               f'(cited sentences {[A.parse_sent(s)[1] for s in x["sentences"]]})',
                                criteria="ok is true only if the statement is supported by the cited sentences and "
                                         "says something this part teaches about the concept.",
                                subject=f["sentences"], kind="facet", rewrite=rw)
            if ok:
                f.update(new)
            else:
                f.update({"only_mentioned": True, "says": None, "sentences": []})
                R.decisions.add("judge", [f["id"]], "facet became a mention", "failed the judge after a rewrite")
    return job


def run_goals_facets(R: Run):
    llm = R.llm("judge")
    jobs = [_lecture_goals_job(R, lec, llm) for lec in R.lectures] + [_course_goals_job(R, llm)]
    by_part: dict[str, list] = {}
    for c in R.registry.concepts.values():
        for f in c.facets:
            if not f["only_mentioned"]:
                by_part.setdefault(f["part"], []).append((c.id, f))
    for pid, fs in by_part.items():
        lec = R.lec(pid.split("/")[0])
        jobs.append(_facet_job(R, lec, lec.part(pid), fs, llm))
    llm.run_jobs("v2_judge_goals_facets", jobs, f"judge goals and facets ({len(jobs)} groups)")
