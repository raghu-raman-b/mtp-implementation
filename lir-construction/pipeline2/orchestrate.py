"""The v2.1 run as a graph of tasks (see pipeline2/TASKS.md, "Run order"). Each part and each lecture moves on as soon
as its inputs are ready; the critical path has the highest priority, the rest fills the GPU around it.

    critical   per lecture: 1 parts -> per part: 2 objective + key points -> judge -> 3 key terms -> judge
               4 registry (all key terms of the course) -> 5 facets, lecture by lecture in course order
    behind     per lecture, once its facets exist: judge facets -> (all earlier lectures' facets judged) 6 links ->
               judge -> open questions -> judge; recall (once every lecture up to it has its links) -> judge
    filling    per part, once its key points are judged: activities -> judge
               per lecture, once its key points are judged: objectives + goal -> judge; then the course goals -> judge
    end        calibration answers; code: lecture map, concept maps, spaced review, scorer
"""
from __future__ import annotations

from . import (act_calibrate, act_open, act_part, act_recall, activities, s1_parts, s2_parts, s3_terms, s4_registry,
               s5_facets, s6_edges, s7_goals, s8_lecture_map)
from .context import Run
from .flow import CRIT, FILL, MID, Flow


def build(R: Run, flow: Flow | None = None):
    flow = R.flow = flow or R.flow or Flow(R.log, R.ui)
    go = flow.go
    fill: list = []                      # everything that is not on the way to the registry

    # ------------------------------------------------------------------ front: per lecture, then per part
    def part_front(lec, p):
        s2_parts.annotate(R, lec, p)
        s2_parts.judge(R, lec, p)

    def lecture_front(lec):
        s1_parts.run_lecture(R, lec)
        activities.init_lecture(R, lec)
        judged = [go("objective + key points", part_front, lec, p, prio=CRIT) for p in lec.parts]
        terms = []
        for p, j in zip(lec.parts, judged):
            terms.append(go("key terms", s3_terms.run_part, R, lec, p, deps=[j], prio=CRIT))
            a = go("part activities", act_part.run_part, R, lec, p, deps=[j], prio=FILL)
            fill.append(go("judge part activities", act_part.judge_part, R, lec, p, deps=[a], prio=FILL))
        g = go("goals", s7_goals.run_lecture, R, lec, deps=judged, prio=FILL)
        jg = go("judge goals", s7_goals.judge_lecture, R, lec, deps=[g], prio=FILL)
        flow.wait(terms)
        return jg

    fronts = [go("parts", lecture_front, lec, prio=CRIT) for lec in R.lectures]
    goals_judged = flow.wait(fronts)       # every lecture: parts, key points and key terms judged
    by_lec = dict(zip([l.id for l in R.lectures], goals_judged))
    cg = go("course goals", s7_goals.run_course, R, deps=goals_judged, prio=FILL)
    fill.append(go("judge course goals", s7_goals.judge_course, R, deps=[cg], prio=FILL))

    # ------------------------------------------------------------------ registry (the whole course)
    flow.wait([go("registry", s4_registry.run, R, prio=CRIT)])
    s5_facets.mentions(R)

    # ------------------------------------------------------------------ facet chain and the work behind it
    prev, j5s, j6s = None, [], []
    for lec in R.lectures:
        f = go("facets", s5_facets.run_lecture, R, lec, deps=[prev], prio=CRIT)
        j5 = go("judge facets", lambda lec=lec: flow.map("judge facets part",
                                                         lambda p: s5_facets.judge_part(R, lec, p), lec.parts),
                deps=[f], prio=MID)
        j5s.append(j5)
        lk = go("links", s6_edges.run_lecture, R, lec, deps=list(j5s), prio=MID)   # earlier facets judged too
        j6s.append(lk)
        oq = go("open questions", act_open.run_lecture, R, lec, deps=[lk, by_lec[lec.id]], prio=MID)
        fill.append(go("judge open questions", act_open.judge_lecture, R, lec, deps=[oq], prio=MID))
        fill.append(go("recall", act_recall.run_lecture, R, lec, deps=list(j6s), prio=MID))
        prev = f
    flow.wait(fill + j6s)

    # ------------------------------------------------------------------ end
    s6_edges.finalize(R)
    s8_lecture_map.run(R)
    act_calibrate.run(R)
    activities.finish(R)
