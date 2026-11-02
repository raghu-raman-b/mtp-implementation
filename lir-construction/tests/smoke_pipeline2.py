#!/usr/bin/env python3
"""Smoke test for the v2 pipeline: every step on real transcripts, with a fake model that gives simple, valid
answers. It checks the plumbing (addresses, merging, facets, edges, judge and rewrites, activities, schema), not the
quality. No GPU, no model calls. The fake judge fails about a quarter of first verdicts, so rewrites run too.

    python3 tests/smoke_pipeline2.py            # VR lectures 1-2, output in a temporary folder
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pipeline.config import load as load_config  # noqa: E402
from pipeline.context import Timer  # noqa: E402
from pipeline.llm import Outcome, parse, schema_of  # noqa: E402
from pipeline.transcript import discover, load_sentences  # noqa: E402
from pipeline2 import (activities, assemble, judge_knowledge, report, s1_parts, s2_parts, s3_terms,  # noqa: E402
                       s4_registry, s5_facets, s6_edges, s7_goals, s8_lecture_map)
from pipeline2.context import Lecture, Run  # noqa: E402

VOCAB = ["virtual reality", "augmented reality", "mixed reality", "extended reality", "immersion", "headset",
         "reality-virtuality continuum"]


def lines(prompt: str) -> list[tuple[int, str]]:
    return [(int(n), t) for n, t in re.findall(r"^\[(\d+)\] (.*)$", prompt, re.M)]


def answer(call) -> dict | list:
    pid, p, sch = call.prompt_id, call.prompt, schema_of(call.schema)
    if pid == "segment.standalone":
        n = len(lines(p))
        first = lines(p)[0][0]
        return list(range(first + 40, first + n, 40))
    if pid == "part.objective":
        return {"objective": "Explain the ideas of this part"}
    if pid == "part.key_points":
        ids = [n for n, _ in lines(p)]
        return {"key_points": [{"text": "A fact of the subject.", "sentence_ids": ids[:1]},
                               {"text": "Another fact.", "sentence_ids": ids[1:3] or ids[:1]}]}
    if pid == "terms.candidates":
        out = []
        for v in VOCAB:
            hit = next((n for n, t in lines(p) if v in t.lower()), None)
            if hit is not None:
                out.append({"term": v, "sentence_ids": [hit]})
        return {"terms": out}
    if pid == "terms.keep":
        term = re.search(r'Candidate key term: "([^"]+)"', p).group(1)
        return {"reason": "test", "keep": term != "headset"}
    if pid == "terms.name":
        term = re.search(r'Key term: "([^"]+)"', p).group(1)
        vr = next((n for n, t in lines(p) if re.search(r"\bVR\b", t)), None)
        if term == "virtual reality" and vr is not None:
            return {"name": term, "abbreviation": "VR", "abbreviation_sentence": vr}
        return {"name": term, "abbreviation": "", "abbreviation_sentence": -1}
    if pid in ("terms.define", "registry.refine"):
        return {"definition": "A concept that the lecturer explains with an example."}
    if pid in ("terms.grounded", "registry.grounded"):
        return {"reason": "test", "supported": True}
    if pid == "registry.same":
        a, b = re.findall(r'^[AB]: "([^"]+)"', p, re.M)[:2]
        return {"reason": "test", "same": a.lower()[:6] == b.lower()[:6]}
    if pid == "facets.part":
        ids = json.loads(re.search(r"named in sentences (\[[^\]]*\])", p).group(1))
        return {"only_mentioned": False, "says": "It is described here.", "sentence_ids": ids[:2]}
    if pid == "edges.relation":
        pool = sch["properties"]["evidence"]["items"]["enum"]
        return {"reason": "test", "relation": "a_kind_of_b", "evidence": pool[:8]}
    if pid == "edges.label":
        return {"label": "is a kind of"}
    if pid == "edges.label_check":
        return {"reason": "test", "ok": True}
    if pid == "goals.objectives":
        pids = sch["properties"]["objectives"]["items"]["properties"]["parts"]["items"]["enum"]
        lo = sch["properties"]["objectives"]["minItems"]
        k = max(1, len(pids) // lo)
        groups = [pids[i * k:(i + 1) * k] for i in range(lo - 1)] + [pids[(lo - 1) * k:]]
        return {"objectives": [{"ability": "explain things", "parts": g} for g in groups]}
    if pid == "judge.item":
        first = "/0/judge" in call.key
        return {"reason": "test", "ok": not (first and zlib.crc32(call.key.encode()) % 4 == 0)}
    if pid == "judge.key_point_rewrite":
        ids = json.loads(re.search(r"citing sentences (\[[^\]]*\])", p).group(1))
        return {"text": "A rewritten fact.", "sentence_ids": ids}
    if pid == "judge.objective_rewrite":
        return {"ability": "explain the rewritten idea"}
    if pid == "judge.course_goal_rewrite":
        return {"goal": "Understand the rewritten goal"}
    if pid == "act.recall":
        return {"question": "What is it?", "answer": "It is a concept."}
    if pid == "act.quiz_plan":
        ids = sch["properties"]["items"]["items"]["properties"]["key_point"]["enum"]
        hi = sch["properties"]["items"]["maxItems"]
        types = ["multiple_choice", "true_false", "yes_no"]
        return {"items": [{"key_point": k, "type": types[n % 3], "reason": "test"} for n, k in enumerate(ids[:hi])][:1]}
    if pid == "act.quiz_mc":
        topic = "virtual reality" if call.key.startswith("L01") else "it"
        return {"question": f"Which is right about {topic}?", "correct": "Option one", "wrong": ["Option two", "Option tri", "Option for"],
                "explanation_correct": "Right.", "explanations_wrong": ["No.", "No.", "No."]}
    if pid == "act.quiz_tf":
        return {"statement": "This is true.", "answer": "True", "explanation_true": "Yes.", "explanation_false": "No."}
    if pid == "act.quiz_yn":
        return {"question": "Is it?", "answer": "No", "explanation_yes": "No.", "explanation_no": "Right."}
    if pid == "act.recap":
        return {"recap": "The part explains things. It ties ideas."}
    if pid == "act.review":
        return {"question": "Why?", "answer": "Because."}
    if pid == "act.oq_plan":
        q = sch["properties"]["questions"]
        pids = q["items"]["properties"]["parts"]["items"]["enum"]
        types = q["items"]["properties"]["type"]["enum"]
        return {"questions": [{"type": types[n], "parts": [pids[n % len(pids)]], "focus": "the idea", "reason": "test"}
                              for n in range(q["minItems"])]}
    if pid == "act.oq_write":
        ids = [n for n, _ in lines(p)]
        ref = "Immersion blocks the senses. Headsets show images. Tracking follows motion."
        return {"question": "Explain how it works.", "reference_answer": ref,
                "key_points": [{"text": t, "keywords": k, "sentence_ids": ids[:1]} for t, k in
                               [("Senses are blocked", ["Immersion", "senses"]), ("Headsets show", ["Headsets", "images"]),
                                ("Tracking", ["Tracking", "motion"])]]}
    if pid == "act.calibrate":
        return {"good": "Immersion blocks the senses and headsets show images while tracking follows motion.",
                "partial": "Headsets show images.", "wrong": "It is about cooking."}
    if pid == "goals.lecture":
        return {"goal": "Understand the lecture"}
    if pid == "goals.course":
        lids = sch["properties"]["goals"]["items"]["properties"]["lectures"]["items"]["enum"]
        lo = sch["properties"]["goals"]["minItems"]
        return {"goals": [{"goal": "Understand the course", "lectures": lids}] * lo}
    raise KeyError(pid)


class FakeServer:
    engine, slots = "fake", 8

    @staticmethod
    def count_tokens(text):
        return len(text) // 4


class FakeLLM:
    def __init__(self, name):
        self.model, self.server, self.calls = name, FakeServer(), 0

    def _one(self, call, max_retries=2):
        self.calls += 1
        content = json.dumps(answer(call))
        for attempt in range(max_retries + 1):
            parsed = parse(call.schema, content)
            errors = call.check(parsed) if call.check else []
            if not errors:
                return Outcome(call, True, parsed, content, "", [], attempt, 0, 0, 0.0, False, "h")
        return Outcome(call, False, parsed, content, "", errors, max_retries, 0, 0, 0.0, False, "h")

    def run(self, stage, calls, desc, max_retries=2):
        return [self._one(c, max_retries) for c in calls]

    def run_jobs(self, stage, jobs, desc, max_retries=2):
        return [fn(lambda c: self._one(c, max_retries)) for fn in jobs]


class FakeModels:
    def __init__(self):
        self.llms = {"generator": FakeLLM("fake-generator"), "verifier": FakeLLM("fake-verifier"),
                     "judge": FakeLLM("fake-judge")}

    def get(self, role):
        return self.llms[role]

    def stop_all(self):
        pass


def log(msg="", kind="info"):
    print(msg)


def main():
    t0 = time.time()
    course = discover(HERE.parent / "dataset/virtual_and_augmented_reality", {1, 2})
    lectures = []
    for inp in course.lectures:
        inp.sentences = load_sentences(inp.srt)
        lectures.append(Lecture(inp, len(lectures) + 1))
    tmp = Path(tempfile.mkdtemp(prefix="lir2_smoke_"))
    cfg = load_config(HERE / "lir2_config.toml")
    R = Run(course, lectures, cfg, FakeModels(), tmp / "out", Timer(None), log)
    s1_parts.run(R)
    s2_parts.run(R)
    by_window = s3_terms.candidates(R)
    judge_knowledge.run_parts(R)
    s3_terms.run(R, by_window)
    s4_registry.run(R)
    s7_goals.run_objectives(R)
    s7_goals.run_lecture_goals(R)
    s7_goals.run_course_goals(R)
    s5_facets.run(R)
    judge_knowledge.run_goals_facets(R)
    s6_edges.run(R)
    s8_lecture_map.run(R)
    activities.generate(R)
    activities.judge(R)
    activities.finish(R)
    assemble.run(R, tmp / "lir")
    report.write(R, [], time.time() - t0)

    c = json.loads((tmp / "lir/course.json").read_text())
    names = [x["name"] for x in c["concepts"]]
    print("\nconcepts:", [(x["id"], x["name"], [a["text"] for a in x["aliases"]], len(x["facets"]),
                           [d["as_of"] for d in x["definitions"]]) for x in c["concepts"]])
    print("edges:", [(e["src"], e["rel"], e["dst"], e["label"], e["flags"]) for e in c["edges"]][:10])
    print("lecture map:", c["lecture_map"])
    print("counts:", R.counts)
    assert len(names) == len(set(n.lower() for n in names)), "duplicate concept names"
    assert "Headset" not in names, "a dropped term reached the registry"
    vr = next(x for x in c["concepts"] if x["name"].lower() == "virtual reality")
    assert all(a["kind"] != "abbreviation" or a["text"] == "VR" for a in vr["aliases"])
    for x in c["concepts"]:
        assert x["definitions"] and x["facets"], x["id"]
    a = json.loads((tmp / "lir/activities/L02.json").read_text())
    print("L02 activities:", {k: len(v) for k, v in a.items() if isinstance(v, list)},
          "quiz items:", sum(len(p["quiz"]) for p in a["parts"]), "sequence:", [x["type"] for x in a["sequence"]][:6])
    assert a["recall"] and a["open_questions"] and a["concept_map"]["nodes"], "missing activities"
    assert all(q["id"] and q["concept_ids"] is not None for p in a["parts"] for q in p["quiz"])
    assert all(k["embedding"] for q in a["open_questions"] for k in q["key_points"])
    assert any(d["decision"] == "repaired" for d in R.decisions.items), "no rewrite path ran"
    assert any(p["review"] for p in a["parts"]), "no review questions"
    spaced = [x for p in a["parts"] for x in p["spaced_review"]]
    print("spaced review in L02:", [(x["concept_id"], x["item"]["id"], x["default"], x["gap"]) for x in spaced])
    assert spaced and spaced[0]["default"] and spaced[0]["item"]["stem"], "no spaced review"
    assert len({x["concept_id"] for x in spaced if x["default"]}) == sum(x["default"] for x in spaced), \
        "a concept was reviewed twice in one lecture"
    print(f"\nOK: {len(names)} concepts, {len(c['edges'])} edges, {len(R.decisions.items)} decisions; files in {tmp}")


if __name__ == "__main__":
    main()
