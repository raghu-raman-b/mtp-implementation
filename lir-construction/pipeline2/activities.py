"""Step 9: the activity layer, built on the knowledge layer. Every item is tagged with the key points and concepts it
tests and cites its sentences.

    generate   (generator) batch 1: recall items, quiz plans, recaps, open-question plans
                           batch 2: quiz items, review questions, open questions
                           batch 3: calibration answers for the scorer
    judge      (verifier)  every item; one rewrite with the reason; then dropped (a recap falls back to key points)
    finish     (code)      concept maps, spaced review after each part, scorer calibration, key-point embeddings

Activities live in R.acts[lecture id]:
    {recall: [...], parts: {part id: {quiz: [...], recap: {...}, review: [...], spaced_review: [...]}},
     open_questions: [...], concept_map: {...}}
"""
from __future__ import annotations

from pipeline.embed import embed

from . import act_calibrate, act_map, act_open, act_quiz, act_recall, act_spaced, act_summary
from .context import Run
from .match import ConceptMatcher

TAKE = {"recall": act_recall.take, "quiz_plan": act_quiz.take_plan, "quiz": act_quiz.take_item,
        "recap": act_summary.take_recap, "review": act_summary.take_review, "oq_plan": act_open.take_plan,
        "oq": act_open.take_write, "calibrate": act_calibrate.take}


def _run(R: Run, stage: str, pairs: list, desc: str):
    groups: dict[int, tuple] = {}
    for step, call in pairs:
        llm = R.llm(step)
        groups.setdefault(id(llm), (llm, []))[1].append(call)
    for llm, calls in groups.values():
        for o in llm.run(stage, calls, f"{desc} ({len(calls)})"):
            R.record(o, o.call.ctx["kind"], llm, o.call.key)
            TAKE[o.call.ctx["kind"]](R, o)


def generate(R: Run):
    R.matcher = ConceptMatcher(R.registry.concepts.values())
    for lec in R.lectures:
        R.acts[lec.id] = {"recall": [], "parts": {p.id: {"quiz": [], "recap": None, "review": [], "spaced_review": []}
                                                  for p in lec.parts},
                          "open_questions": [], "concept_map": None}
    _run(R, "v2_act_plan", act_recall.calls(R) + act_quiz.plan_calls(R) + act_summary.recap_calls(R)
         + act_open.plan_calls(R), "recall, quiz plans, recaps, open-question plans")
    _run(R, "v2_act_write", act_quiz.item_calls(R) + act_summary.review_calls(R) + act_open.write_calls(R),
         "quiz items, review questions, open questions")
    _run(R, "v2_act_calibrate", act_calibrate.calls(R), "calibration answers")


def _part_job(R: Run, lec, p, llm):
    def job(send):
        act_quiz.judge_part(send, R, lec, p, llm)
        act_summary.judge_part(send, R, lec, p, llm)
    return job


def judge(R: Run):
    llm = R.llm("judge")
    jobs, oq_slots = [], []
    for lec in R.lectures:
        jobs.append(act_recall.judge_job(R, lec, llm))
        jobs += [_part_job(R, lec, p, llm) for p in lec.parts]
        for it in R.acts[lec.id]["open_questions"]:
            oq_slots.append((len(jobs), lec.id))
            jobs.append(act_open.judge_job(R, lec, it, llm))
    results = llm.run_jobs("v2_judge_activities", jobs, f"judge activities ({len(jobs)} groups)")
    for lec in R.lectures:
        R.acts[lec.id]["open_questions"] = []
    for k, lid in oq_slots:
        if results[k] is not None:
            R.acts[lid]["open_questions"].append(results[k])
    for lec in R.lectures:
        for n, q in enumerate(R.acts[lec.id]["open_questions"], 1):
            q["id"] = f"{lec.id}/OQ{n}"


def finish(R: Run):
    for lec in R.lectures:
        R.acts[lec.id]["concept_map"] = act_map.concept_map(R, lec)
    act_spaced.run(R)
    R.scoring = act_calibrate.fit(R)
    kps = [k for lec in R.lectures for q in R.acts[lec.id]["open_questions"] for k in q["key_points"]]
    for k, e in zip(kps, embed([k["text"] for k in kps])):
        k["embedding"] = [round(float(x), 5) for x in e]
    for lec in R.lectures:
        a = R.acts[lec.id]
        R.count("recall_items", len(a["recall"]))
        R.count("quiz_items", sum(len(p["quiz"]) for p in a["parts"].values()))
        R.count("review_questions", sum(len(p["review"]) for p in a["parts"].values()))
        R.count("open_questions", len(a["open_questions"]))
        R.count("map_nodes", len(a["concept_map"]["nodes"]))
        R.count("map_links", len(a["concept_map"]["edges"]))
    oa = R.scoring["open_answer"]
    R.log(f"  scorer: m={oa['m']}, tau={oa['tau']}"
          + (f", agreement {oa['agreement']:.0%} on {oa['answers']} answers" if oa.get("calibrated") else
             f" ({oa.get('note', 'defaults')})"))
