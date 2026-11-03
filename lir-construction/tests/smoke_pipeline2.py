#!/usr/bin/env python3
"""Smoke test for the v2.1 pipeline: the whole task graph (pipeline2/orchestrate.py) on real transcripts, with a fake
model that gives simple, valid answers. It checks the plumbing (scheduling, addresses, the registry, facets, links,
judge and rewrites, activities, schema), not the quality. No GPU, no model calls. The fake judge fails about a quarter
of first verdicts, so the rewrite paths run too.

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
from pipeline2 import assemble, orchestrate, report  # noqa: E402
from pipeline2.context import Lecture, Run  # noqa: E402
from pipeline2.flow import Flow  # noqa: E402

VOCAB = ["virtual reality", "augmented reality", "mixed reality", "extended reality", "immersion", "headset",
         "reality-virtuality continuum"]


def lines(prompt: str) -> list[tuple[int, str]]:
    return [(int(n), t) for n, t in re.findall(r"^\[(\d+)\] (.*)$", prompt, re.M)]


def first_ids(prompt: str) -> list[int]:
    return [n for n, _ in lines(prompt)]


def item_props(sch: dict) -> dict:
    return sch["properties"]["items"]["items"]["properties"]


def oq_answer(ref_ids: list[int], qtype: str = "explain_mechanism", parts=None) -> dict:
    ref = "Immersion blocks the senses. Headsets show images. Tracking follows motion."
    return {"type": qtype, "parts": parts or [], "question": "Explain how it works.", "reference_answer": ref,
            "key_points": [{"text": t, "keywords": k, "sentence_ids": ref_ids[:1]} for t, k in
                           [("Senses are blocked", ["Immersion", "senses"]), ("Headsets show", ["Headsets", "images"]),
                            ("Tracking", ["Tracking", "motion"])]]}


def rewrite_answer(p: str, sch: dict) -> dict:
    props = item_props(sch)
    n = len(props["item"]["enum"])
    blocks = re.split(r"^\[\d+\] ", p.split("A reviewer rejected these items:", 1)[1], flags=re.M)[1:]
    out = []
    for k in range(1, n + 1):
        b = blocks[k - 1] if k - 1 < len(blocks) else ""
        x: dict = {"item": k}
        if "objective" in props:
            x["objective"] = "Explain the rewritten idea"
        if "sentence_ids" in props and "text" in props:
            ids = json.loads(re.search(r"cited sentences (\[[^\]]*\])", b).group(1))
            x.update(text="A rewritten fact.", sentence_ids=ids)
        elif "text" in props:
            x["text"] = "explain the rewritten goal"
        if "definition" in props:
            x.update(name=re.search(r'Key term "([^"]+)"', b).group(1), definition="A rewritten definition.")
        if "only_mentioned" in props:
            ids = json.loads(re.search(r"cited sentences (\[[^\]]*\])", b).group(1))
            x.update(only_mentioned=False, says="It is rewritten here.", sentence_ids=ids)
        if "stem" in props:
            t = re.search(r"Quiz item \(([a-z ]+)\)", b).group(1).replace(" ", "_")
            x.update(quiz(t))
        if "recap" in props:
            x["recap"] = "A rewritten recap. It ties ideas."
        if "question" in props and "answer" in props:
            x.update(question="Why is it so?", answer="Because it is.")
        if "reference_answer" in props:
            ids = first_ids(p)
            x.update(oq_answer(ids, re.search(r"asks the learner to ([^)]+)\)", b) and "explain_mechanism",
                               [props["parts"]["items"]["enum"][0]]))
        out.append(x)
    return {"items": out}


def quiz(t: str, topic: str = "it") -> dict:
    if t == "multiple_choice":
        return {"type": t, "stem": f"Which is right about {topic}?", "correct": "Option one",
                "wrong": ["Option two", "Option tri", "Option for"], "explanation_correct": "Right.",
                "explanations_wrong": ["No.", "No.", "No."]}
    if t == "true_false":
        return {"type": t, "stem": "This is true.", "correct": "True", "wrong": ["False"],
                "explanation_correct": "Yes.", "explanations_wrong": ["No."]}
    return {"type": t, "stem": "Is it?", "correct": "No", "wrong": ["Yes"], "explanation_correct": "Right.",
            "explanations_wrong": ["No."]}


def answer(call) -> dict | list:
    pid, p, sch = call.prompt_id, call.prompt, schema_of(call.schema)
    if pid == "segment.standalone":
        ids = first_ids(p)
        return list(range(ids[0] + 40, ids[0] + len(ids), 40))
    if pid == "part.annotate":
        ids = first_ids(p)
        return {"objective": "Explain the ideas of this part",
                "key_points": [{"text": "A fact of the subject.", "sentence_ids": ids[:1], "about": "subject"},
                               {"text": "Another fact.", "sentence_ids": ids[1:3] or ids[:1], "about": "subject"},
                               {"text": "The course covers this.", "sentence_ids": ids[:1], "about": "course"}]}
    if pid == "terms.window":
        out = []
        for v in VOCAB:
            hit = next((n for n, t in lines(p) if v in t.lower()), None)
            if hit is None:
                continue
            vr = next((n for n, t in lines(p) if re.search(r"\bVR\b", t)), None)
            ab = ("VR", vr) if v == "virtual reality" and vr is not None else ("", -1)
            out.append({"term": v, "sentence_ids": [hit], "reason": "test", "keep": v != "headset", "name": v,
                        "abbreviation": ab[0], "abbreviation_sentence": ab[1],
                        "definition": "" if v == "headset" else "A concept that the lecturer explains."})
        return {"terms": out}
    if pid == "registry.group":
        ents = re.findall(r'^E(\d+): "([^"]+)"', p, re.M)
        groups: dict[str, list[int]] = {}
        for n, name in ents:
            groups.setdefault(name.lower()[:6], []).append(int(n))
        return {"concepts": [{"entries": g, "reason": "test", "name": ents[g[0] - 1][1],
                              "definition": "A concept of the course."} for g in groups.values()]}
    if pid == "goals.lecture":
        pids = sch["properties"]["objectives"]["items"]["properties"]["parts"]["items"]["enum"]
        lo = sch["properties"]["objectives"]["minItems"]
        k = max(1, len(pids) // lo)
        groups = [pids[i * k:(i + 1) * k] for i in range(lo - 1)] + [pids[(lo - 1) * k:]]
        return {"objectives": [{"ability": "explain things", "parts": g} for g in groups], "goal": "Understand it"}
    if pid == "goals.course":
        lids = sch["properties"]["goals"]["items"]["properties"]["lectures"]["items"]["enum"]
        lo = sch["properties"]["goals"]["minItems"]
        return {"goals": [{"goal": "Understand the course", "lectures": lids}] * lo}
    if pid == "facets.part":
        labels = sch["properties"]["facets"]["items"]["properties"]["concept"]["enum"]
        named = [json.loads(x) for x in re.findall(r"Named in sentences (\[[^\]]*\])", p)]
        return {"facets": [{"concept": c, "only_mentioned": not ids, "says": "It is described here.",
                            "sentence_ids": ids[:2]} for c, ids in zip(labels, named)]}
    if pid == "links.lecture":
        labels = sch["properties"]["links"]["items"]["properties"]["a"]["enum"]
        shown = [int(x) for x in re.findall(r"^  \[(\d+)\] ", p, re.M)]
        return {"links": [{"a": labels[k], "relation": "kind_of", "b": labels[0], "label": "is a kind of",
                           "evidence": shown[:3]} for k in range(1, min(len(labels), 4))]}
    if pid == "judge.items":
        n = len(sch["properties"]["verdicts"]["items"]["properties"]["item"]["enum"])
        rev = "reversed" in sch["properties"]["verdicts"]["items"]["properties"]
        first = call.key.endswith("/judge")
        out = []
        for k in range(1, n + 1):
            bad = first and (zlib.crc32(f"{call.key}#{k}".encode()) % 4 == 0 or (rev and k == 2))
            v = {"item": k, "reason": "test", "ok": not bad}
            if rev:
                v["reversed"] = bad and k == 2
            out.append(v)
        return {"verdicts": out}
    if pid == "judge.rewrite":
        return rewrite_answer(p, sch)
    if pid == "act.part":
        q = sch["properties"]["quiz"]["items"]["properties"]
        ids = q["key_point"]["enum"]
        topic = "virtual reality" if call.key.startswith("L01") else "it"
        items = [{"key_point": ids[0], "reason": "test", **quiz("multiple_choice", topic)}]
        if len(ids) > 2:
            items.append({"key_point": ids[1], "reason": "test", **quiz("true_false")})
        rev = [{"key_point": k, "question": "Why?", "answer": "Because."} for k in ids[len(items):]]
        return {"quiz": items, "recap": "The part explains things. It ties ideas.", "review": rev}
    if pid == "act.oq":
        qs = sch["properties"]["questions"]
        pids = qs["items"]["properties"]["parts"]["items"]["enum"]
        types = qs["items"]["properties"]["type"]["enum"]
        ids = [int(x) for x in re.findall(r"^\[(\d+)\] ", p, re.M)]
        return {"questions": [oq_answer(ids, types[n], [pids[n % len(pids)]]) for n in range(qs["minItems"])]}
    if pid == "act.recall":
        labels = sch["properties"]["items"]["items"]["properties"]["concept"]["enum"]
        return {"items": [{"concept": c, "question": "What is it?", "answer": "It is a concept."} for c in labels]}
    if pid == "act.calibrate":
        return {"good": "Immersion blocks the senses and headsets show images while tracking follows motion.",
                "partial": "Headsets show images.", "wrong": "It is about cooking."}
    raise KeyError(pid)


class FakeServer:
    engine, slots, think_end = "fake", 8, ""

    @staticmethod
    def count_tokens(text):
        return len(text) // 4


class FakeLLM:
    def __init__(self, name):
        self.model, self.server, self.calls = name, FakeServer(), 0

    def one(self, stage, call, max_retries=2):
        self.calls += 1
        content = json.dumps(answer(call))
        parsed = parse(call.schema, content)
        errors = call.check(parsed) if call.check else []
        return Outcome(call, not errors, parsed, content, "", errors, 0 if not errors else max_retries, 0, 0, 0.0,
                       False, "h")


class FakeModels:
    def __init__(self):
        self.llms = {"generator": FakeLLM("fake-generator"), "verifier": FakeLLM("fake-verifier"),
                     "judge": FakeLLM("fake-judge")}

    def get(self, role):
        return self.llms[role]

    def start_all(self):
        pass

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
    models = FakeModels()
    R = Run(course, lectures, cfg, models, tmp / "out", Timer(None), log)
    R.flow = Flow(log, None)
    orchestrate.build(R)
    assemble.run(R, tmp / "lir")
    R.timer.stages = R.flow.spans()
    report.write(R, [], time.time() - t0)
    R.flow.shutdown()

    failed = {s: st["failed"] for s, st in R.flow.steps.items() if st["failed"]}
    assert not failed, f"tasks failed: {failed}"
    c = json.loads((tmp / "lir/course.json").read_text())
    names = [x["name"] for x in c["concepts"]]
    print("\nconcepts:", [(x["id"], x["name"], [a["text"] for a in x["aliases"]], len(x["facets"])) for x in c["concepts"]])
    print("edges:", [(e["src"], e["rel"], e["dst"], e["label"], e["flags"]) for e in c["edges"]][:10])
    print("lecture map:", c["lecture_map"])
    print("calls:", {k: m.calls for k, m in models.llms.items()}, "counts:", R.counts)
    print("steps:", [(s["stage"], s["tasks"]) for s in R.flow.spans()])
    assert len(names) == len(set(n.lower() for n in names)), "duplicate concept names"
    assert "Headset" not in names, "a dropped term reached the registry"
    vr = next(x for x in c["concepts"] if x["name"].lower() == "virtual reality")
    assert any(a["kind"] == "abbreviation" and a["text"] == "VR" for a in vr["aliases"]), "VR abbreviation lost"
    for x in c["concepts"]:
        assert x["definition"] and x["facets"] and x["reason"], x["id"]
    l1 = json.loads((tmp / "lir/L01.json").read_text())
    assert all(t["concept_name"] for p in l1["parts"] for t in p["terms"]), "term without its concept name"
    assert c["edges"], "no links"
    a = json.loads((tmp / "lir/activities/L02.json").read_text())
    print("L02 activities:", {k: len(v) for k, v in a.items() if isinstance(v, list)},
          "quiz items:", sum(len(p["quiz"]) for p in a["parts"]), "sequence:", [x["type"] for x in a["sequence"]][:6])
    assert a["recall"] and a["open_questions"] and a["concept_map"]["nodes"], "missing activities"
    assert all(q["id"] and q["concept_ids"] is not None for p in a["parts"] for q in p["quiz"])
    assert all(k["embedding"] for q in a["open_questions"] for k in q["key_points"])
    assert any(d["decision"] == "repaired" for d in R.decisions.items), "no rewrite path ran"
    assert any(d["decision"] == "flipped" for d in R.decisions.items), "no link was flipped"
    assert any(p["review"] for p in a["parts"]), "no review questions"
    spaced = [x for p in a["parts"] for x in p["spaced_review"]]
    print("spaced review in L02:", [(x["concept_id"], x["item"]["id"], x["default"], x["gap"]) for x in spaced])
    assert spaced and spaced[0]["default"] and spaced[0]["item"]["stem"], "no spaced review"
    assert len({x["concept_id"] for x in spaced if x["default"]}) == sum(x["default"] for x in spaced), \
        "a concept was reviewed twice in one lecture"
    print(f"\nOK: {len(names)} concepts, {len(c['edges'])} edges, {len(R.decisions.items)} decisions; files in {tmp}")


if __name__ == "__main__":
    main()
