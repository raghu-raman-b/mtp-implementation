"""Step 9: the activity layer, built on the knowledge layer. Every item is tagged with the key points and concepts it
tests and cites its sentences.

    per part      act_part.py: quiz, recap, review questions (one call), judged in one call
    per lecture   act_open.py: open questions (one call from the lecture's knowledge), judged in one call
                  act_recall.py: recall items (one call), judged in one call
    course        act_calibrate.py: good / partial / wrong answers for a sample of open questions
    finish (code) concept tags, concept maps, spaced review after each part, scorer calibration, key-point embeddings

Activities live in R.acts[lecture id]:
    {recall: [...], parts: {part id: {quiz: [...], recap: {...}, review: [...], spaced_review: [...]}},
     open_questions: [...], concept_map: {...}}
"""
from __future__ import annotations

from pipeline.embed import embed

from . import act_calibrate, act_map, act_spaced
from .context import Lecture, Run
from .match import ConceptMatcher


def init_lecture(R: Run, lec: Lecture):
    R.acts[lec.id] = {"recall": [], "parts": {p.id: {"quiz": [], "recap": None, "review": [], "spaced_review": []}
                                              for p in lec.parts},
                      "open_questions": [], "concept_map": None}


def tag(R: Run):
    """Concept tags (needs the registry): what each item names, among concepts introduced up to its lecture."""
    m = ConceptMatcher(R.registry.concepts.values())
    for lec in R.lectures:
        a = R.acts[lec.id]
        for pa in a["parts"].values():
            for q in pa["quiz"]:
                q["concept_ids"] = m.find(" ".join([q["_point"], q["stem"], q["options"][q["correct_index"]]]), lec.pos)
            for v in pa["review"]:
                v["concept_ids"] = m.find(v["_point"] + " " + v["question"], lec.pos)
        for q in a["open_questions"]:
            q["concept_ids"] = m.find(q["prompt"] + " " + q["reference_answer"], lec.pos)
    R.matcher = m


def finish(R: Run):
    tag(R)
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
