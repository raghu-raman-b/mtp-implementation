"""Test of stage 2c (concepts and relationships per segment) with a scripted fake model, on the local PC.

    python3 tests/fake_2c.py [--work DIR] [--keep] [--s2c FILE]

Runs in a copy of the pipeline folder (scripts, prompts, configs, the course's metadata, the segment maps and the
verified facts of lectures 4 and 16) in a new temporary folder, so nothing under output/ is written; the test checks
that at the end. The fake model listens on a free port (never 8094 or 8095, the SSH forward to the EC2) through a
copy of the Qwen config with that port, model_path "fake/qwen" (so no cache hash can match a real one) and no wait.
--s2c runs the test on another s2c_concepts.py (copied into the copy), to see that the tests fail on a broken one.

The fake is scripted per segment (found by its first fact in the prompt); the attempt is the request's seed:
  4/S0   never JSON: no answer, no turn 2
  4/S1   turn 1: an empty name and a fact number out of range, then right; turn 2: a number out of range, then right
  4/S2   the 2c trial's real answers (brackets: "computer-aided design (CAD) system"): one attempt each
  16/S0  turn 1: the name "XR" and an alias no fact writes, then right; turn 2: a vague label, a duplicate and a
         triple from a concept to itself, then right
  16/S1  the trial's real answers (apostrophes: "tracking the user's sense organs"): one attempt each
  16/S2  turn 1 never right: 2, 1, 3 problems (the second kept); turn 2 right
  16/S3  turn 1 with only report-only problems (acronym in a longer name, a name in none of its facts, the same name
         twice, a fact without concept); turn 2 never right: 2, 1, 2 problems (the second kept)

What it looks for (each line is what a broken stage would show):
  unit     the word matching wrong on the trial's false alarms (apostrophes, "X (Y) Z") or too loose; an acronym
           name not caught, or a product name ("HoloLens") or an acronym inside a longer name sent to a retry; an
           empty name not caught; a report-only kind giving a problem line, or a retry kind none; the problem lines
           not the decided texts; a triple from a concept to itself counted as its own reverse; lost and added wrong
  run      a segment asked more or fewer times than its script needs (a retry on a report-only kind, none on a retry
           kind); the retry without the earlier answer and the decided problem lines; turn 2 not continuing from
           turn 1's prompt and kept answer only (the turn-1 retries shown, or another attempt's answer); the answer
           with the fewest problems not kept, or lost; an unresolved answer not marked or its problems not listed;
           an unparseable answer not "no answer", or a parseable one counted as no answer; lost and added not logged
           per retried answer or not counted in the run summary; the new prompt rules not sent; the trial's false
           alarms back in the checks
  rerun    any output file different when rerun from the cache, or the model called again
  output   any file under the real output/ or analysis/ created or changed
"""
from __future__ import annotations

import argparse
import importlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from scripts.llm.client import FEEDBACK  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402

COURSE = "nptel_vr"
KEYS = ["4", "16"]
FORBIDDEN = {8094, 8095}
TRIAL = REPO / "analysis" / "concepts" / "data" / "trial_fresh_2b" / "llm" / "cache.jsonl"
FAILURES: list[str] = []
s2c = None   # the module under test, imported from the copy


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file() and "logs" not in p.relative_to(folder).parts}


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in FORBIDDEN:
            return port


def tree_bytes(folder: Path, skip=("calls.jsonl",)) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and p.name not in skip}


# ---------------------------------------------------------------- the copy
def make_copy(work: Path, s2c_file: Path | None) -> Path:
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("scripts", "prompts", "configs"):
        shutil.copytree(ROOT / d, work / d, ignore=ign)
    if s2c_file:
        shutil.copy(s2c_file, work / "scripts" / "s2c_concepts.py")
    meta = work / "input" / COURSE / "input"
    meta.mkdir(parents=True)
    for f in ("course.json", "titles.tsv"):
        shutil.copy(ROOT / "input" / COURSE / "input" / f, meta / f)
    src, dst = ROOT / "output" / COURSE, work / "output" / COURSE
    for sub in ("stage_1b_verify_segments/segment_maps", "stage_2b_verify_facts/fact_maps"):
        (dst / sub).mkdir(parents=True)
        for k in KEYS:
            shutil.copy(src / sub / f"lec_{k}.json", dst / sub / f"lec_{k}.json")
    cfg = json.loads((ROOT / "configs" / "qwen38_27b_vllm.json").read_text())
    cfg.update(port=free_port(), model_path="fake/qwen", attach_wait_s=0, server_log="fake_server.log", seed=0,
               retries=2)
    assert cfg["port"] not in FORBIDDEN
    path = work / "configs" / "fake_qwen.json"
    path.write_text(json.dumps(cfg, indent=1))
    return path


def facts_of(work: Path) -> dict[str, list[str]]:
    out = {}
    for k in KEYS:
        d = json.loads((work / "output" / COURSE / "stage_2b_verify_facts" / "fact_maps" / f"lec_{k}.json").read_text())
        for fid, f in d.items():
            out.setdefault(fid.rsplit("/", 1)[0], []).append(f["text"])
    return out


# ---------------------------------------------------------------- the scripted fake
def C(name, facts, aliases=(), defined=False):
    return {"name": name, "aliases": list(aliases), "facts": list(facts), "defined": defined}


def T(subject, label, obj, facts):
    return {"facts": list(facts), "subject": subject, "label": label, "object": obj}


def trial_answers() -> dict:
    """The 2c trial's real answers: segment -> {"concepts": ..., "relations": ...}."""
    out = {}
    for line in TRIAL.read_text().splitlines():
        r = json.loads(line)
        out.setdefault(r["key"], {}).update(json.loads(r["content"]))
    return out


def scripts_for() -> dict:
    """Segment -> {"t1": [answer per attempt], "t2": [...]}; the last answer repeats for later attempts. An answer
    is a dict (sent as JSON) or a string (sent as it is)."""
    trial = trial_answers()
    tracking4 = [1, 2, 3, 4]
    return {
        "4/S0": {"t1": ["I cannot answer in JSON."]},
        "4/S1": {"t1": [{"concepts": [C("", [1]), C("virtual reality system", [1, 99], ["VR system"], True)]},
                        {"concepts": [C("virtual reality system", [1], ["VR system"], True),
                                      C("artificial environment", [2, 3])]}],
                 "t2": [{"relations": [T("virtual reality system", "has", "artificial environment", [99])]},
                        {"relations": [T("virtual reality system", "has", "artificial environment", [2])]}]},
        "4/S2": {"t1": [{"concepts": trial["4/S2"]["concepts"]}], "t2": [{"relations": trial["4/S2"]["relations"]}]},
        "16/S0": {"t1": [{"concepts": [C("XR", [1, 2]), C("tracking", tracking4, ["trackers"], True),
                                       C("three-dimensional space", [4], ["3D space"]),
                                       C("virtual reality", [2, 3], ["VR"]), C("augmented reality", [4], ["AR"])]},
                         {"concepts": [C("extended reality", [1, 2], ["XR"]), C("tracking", tracking4, [], True),
                                       C("three-dimensional space", [4], ["3D space"]),
                                       C("virtual reality", [2, 3], ["VR"]), C("augmented reality", [4], ["AR"])]}],
                  "t2": [{"relations": [T("tracking", "is related to", "extended reality", [1]),
                                        T("tracking", "is a part of", "extended reality", [1]),
                                        T("tracking", "is a part of", "extended reality", [2]),
                                        T("virtual reality", "is a kind of", "virtual reality", [2])]},
                         {"relations": [T("tracking", "is an integral hardware component of", "extended reality", [1, 2]),
                                        T("tracking", "translates physical motion into virtual motion in",
                                          "virtual reality", [3]),
                                        T("augmented reality", "registers virtual content in", "three-dimensional space",
                                          [4])]}]},
        "16/S1": {"t1": [{"concepts": trial["16/S1"]["concepts"]}], "t2": [{"relations": trial["16/S1"]["relations"]}]},
        "16/S2": {"t1": [{"concepts": [C("VR", [4]), C("AR", [1]), C("tracking", [1, 2, 3, 4, 5, 6, 7], [], True)]},
                         {"concepts": [C("VR", [4]), C("augmented reality", [1]), C("tracking", [1, 2, 3, 4, 5, 6, 7])]},
                         {"concepts": [C("VR", [4]), C("AR", [1]), C("XR", [1]), C("tracking", [1, 2, 3])]}],
                  "t2": [{"relations": [T("tracking", "is used in", "augmented reality", [1])]}]},
        "16/S3": {"t1": [{"concepts": [C("tracking", [1, 2]), C("Tracking", [3]), C("VR headset", [1]),
                                       C("body-part tracking", [2]), C("registration", [2, 4], [], True)]}],
                  "t2": [{"relations": [T("tracking", "is used by", "VR headset", [1]),
                                        T("tracking", "is used by", "VR headset", [2]),
                                        T("VR headset", "is shown in", "VR headset", [1])]},
                         {"relations": [T("tracking", "is used by", "VR headset", [1]),
                                        T("VR headset", "uses", "tracking", [1]),
                                        T("VR headset", "is shown in", "VR headset", [1])]},
                         {"relations": [T("tracking", "involves", "VR headset", [1]),
                                        T("VR headset", "is shown in", "VR headset", [1])]}]},
    }


class ScriptedServer(FakeServer):
    """Answers each request from the script of its segment; logs every request with its segment, turn and attempt."""

    def __init__(self, port: int, model: str, script: dict, first_fact: dict):
        super().__init__(port, model)
        self.script, self.first_fact, self.sent = script, first_fact, []

    def answer(self, body: dict) -> dict:
        msgs = body["messages"]
        prompt = msgs[0]["content"]
        tail = prompt[prompt.rindex("### Your segment"):]
        first = tail.split("FACTS:\n[1] ", 1)[1].split("\n", 1)[0]
        sid = self.first_fact[first]
        turn = "t2" if any(m["role"] == "user" and m["content"].startswith("Now give the relationships")
                           for m in msgs[1:]) else "t1"
        attempt = body["seed"]
        answers = self.script[sid][turn]
        a = answers[min(attempt, len(answers) - 1)]
        content = a if isinstance(a, str) else json.dumps(a)
        with self.lock:
            self.sent.append({"segment": sid, "turn": turn, "attempt": attempt, "messages": msgs,
                              "schema": body.get("response_format", {}).get("json_schema", {}).get("schema"),
                              "content": content})
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10}}


# ---------------------------------------------------------------- unit tests
F16_0_3 = ("In augmented reality (AR), tracking is primarily about registering virtual content in three-dimensional "
           "(3D) space with respect to an anchor in the real world, and it requires tracking the user's pose, position, "
           "and orientation as well as tracking moving real-world objects in the field of view.")
F16_1_0 = ("Tracking can be categorized by what is being tracked into three categories: tracking the user's sense "
           "organs, tracking the user's other body parts, and tracking the surrounding environment not related to "
           "the user.")
F16_1_1 = "Tracking of the user's sense organs, such as eyes and ears, is needed because they have body-controlled"
F4_2_0 = ("A system is a virtual reality (VR) system if it satisfies all three characteristics of a VR system")
F4_2_1 = "A computer-aided design (CAD) system is not a virtual reality (VR) system because"
F4_2_3 = "A three-dimensional (3D) movie experience is not a virtual reality (VR) system because"


def test_unit():
    print("unit", flush=True)
    a = s2c.appears
    hits = [("three-dimensional space", F16_0_3), ("3D space", F16_0_3),
            ("tracking the user's sense organs", F16_1_0), ("tracking of the user's sense organs", F16_1_1),
            ("tracking the user's other body parts", F16_1_0), ("tracking the user’s sense organs", F16_1_0),
            ("virtual reality system", F4_2_0), ("VR system", F4_2_0), ("computer-aided design system", F4_2_1),
            ("CAD system", F4_2_1), ("three-dimensional movie experience", F4_2_3), ("3D movie experience", F4_2_3),
            ("augmented reality systems", "virtual reality (VR) and augmented reality (AR) systems"),
            ("AR systems", "virtual reality (VR) and augmented reality (AR) systems")]
    missed = [t for t, x in hits if not a(t, x)]
    check(not missed, f"the trial's false alarms now match (apostrophes, brackets){': missed ' + str(missed) if missed else ''}")
    misses = [("display", "displayed"), ("AR", "Art is not a term."), ("CAD design system", F4_2_1),
              ("3D experience", F4_2_3), ("VR augmented reality", "virtual reality (VR) and augmented reality (AR)"),
              ("user tracking", F16_1_0)]
    wrong = [t for t, x in misses if a(t, x)]
    check(not wrong, f"the matching is not too loose{': matched ' + str(wrong) if wrong else ''}")
    check(a("head-mounted display", "Head mounted displays block vision.") and a("XR", "Extended reality (XR) is ..."),
          "plural, hyphen and an acronym in brackets still match")

    facts = ["Virtual reality (VR) uses a head-mounted display.", "Microsoft HoloLens is a headset.", "Nothing here."]
    concepts = [C("VR", [1]), C("3D", [1]), C("VR headset", [2]), C("Microsoft HoloLens", [2]), C("", [1]),
                C("head-mounted display", [1], ["HMD", "display"])]
    fl = s2c.concept_checks(concepts, facts)
    check(fl["name_is_acronym"] == ["VR", "3D"], f"name_is_acronym: VR and 3D, not HoloLens ({fl['name_is_acronym']})")
    check(fl["acronym_in_name"] == [{"concept": "VR headset", "acronyms": ["VR"]}],
          f"acronym_in_name: VR headset only ({fl['acronym_in_name']})")
    check(fl["empty_name"] == [{"facts": [1]}], "an empty name is caught")
    check(fl["alias_not_written"] == [{"concept": "head-mounted display", "alias": "HMD"}],
          "alias_not_written: HMD only")
    check(fl["fact_without_concept"] == [3], "fact_without_concept")

    lines = s2c.concept_check(facts)({"concepts": concepts})
    want = ['The name "VR" is an acronym. A concept\'s name is always the full term in words; put "VR" in its '
            'aliases. If your list already has this concept under its full name, join the two.',
            'The name "3D" is an acronym. A concept\'s name is always the full term in words; put "3D" in its '
            'aliases. If your list already has this concept under its full name, join the two.',
            "A concept that cites the facts 1 has an empty name. Give it its name: the full term in words.",
            'The alias "HMD" of "head-mounted display" is written in none of the facts. Remove it.']
    check(lines == want, "turn-1 problem lines: the decided texts, for the retry kinds only")
    oor = s2c.concept_check(facts)({"concepts": [C("head-mounted display", [1, 7])]})
    check(oor == ['The concept "head-mounted display" cites the fact numbers 7, which are not in the list. '
                  'The facts are numbered 1 to 3.'], "turn-1 problem line: a number out of range")
    report_only = {"concepts": [C("VR headset", [2]), C("tracking", [1]), C("Tracking", [2])]}
    check(s2c.concept_check(facts)(report_only) == [],
          "no problem line for report-only kinds (acronym_in_name, name_not_in_facts, merged, fact_without_concept)")
    check(s2c.concept_check(facts)({"concept": []}) == ["The answer has no list of concepts."],
          "an answer of the wrong form is a problem")

    cs = [C("a", [1]), C("b", [2]), C("c", [1])]
    rels = [T("a", "is related to", "b", [1]), T("b", "contains", "a", [1]), T("a", "Is Related  To", "b", [3]),
            T("c", "is", "c", [1]), T("a", "uses", "c", [5])]
    rf = s2c.relation_checks(cs, rels, 3)
    check(rf["vague_label"] == [0, 2] and rf["duplicate_triple"] == [2] and rf["self_triple"] == [3]
          and rf["reverse"] == [0, 1, 2] and rf["no_shared_fact"] == [0, 1, 2, 4]
          and rf["out_of_range"] == [{"triple": 4, "facts": [5]}] and rf["no_triple"] == [],
          f"each triple check fires on its case; a triple to itself is not its own reverse ({rf})")
    tl = s2c.relation_check(cs, 3)({"relations": rels})
    check(tl == ['The relationship "a | uses | c" cites the fact numbers 5, which are not in the list. The facts are '
                 'numbered 1 to 3.',
                 'The label "is related to" of the relationship "a | is related to | b" does not say what the '
                 'relationship is. Write a label as specific as the facts, or remove the relationship if the facts '
                 'state none.',
                 'The label "Is Related  To" of the relationship "a | Is Related  To | b" does not say what the '
                 'relationship is. Write a label as specific as the facts, or remove the relationship if the facts '
                 'state none.',
                 'The relationship "c | is | c" joins a concept to itself. A relationship joins two different '
                 'concepts: give it the right subject or object, or remove it.',
                 'The relationship "a | Is Related  To | b" is written 2 times. Write it once, citing the facts of '
                 'all its copies.'], "turn-2 problem lines for the retry kinds only")
    check(s2c.relation_check(cs, 3)({"relations": [T("b", "contains", "a", [1]), T("a", "is part of", "b", [2])]})
          == [], "no problem line for report-only kinds (reverse, no_shared_fact, no_triple)")
    lost, added = s2c.lost_added(["XR", "Tracking", "AR"], ["extended reality", "tracking", "AR"])
    check(lost == ["XR"] and added == ["extended reality"], "lost and added (case ignored)")


# ---------------------------------------------------------------- the run
def run_stage(work: Path, cfg: Path, log: Path) -> int:
    return subprocess.run([sys.executable, "-u", "scripts/s2c_concepts.py", COURSE, "--llm", str(cfg.relative_to(work)),
                           "--only", ",".join(KEYS)], cwd=work, stdout=log.open("w"), stderr=subprocess.STDOUT,
                          timeout=600).returncode


def load_out(work: Path) -> tuple[dict, dict, dict]:
    od = work / "output" / COURSE / "stage_2c_concepts"
    cmap, rmap, checks = {}, {}, {}
    for k in KEYS:
        cmap.update(json.loads((od / "concept_maps" / f"lec_{k}.json").read_text()))
        rmap.update(json.loads((od / "relations" / f"lec_{k}.json").read_text()))
        checks.update(json.loads((od / "checks" / f"lec_{k}.json").read_text()))
    return cmap, rmap, checks


def test_run(work: Path, cfg_path: Path):
    print("run (scripted fake on a free port)", flush=True)
    facts = facts_of(work)
    first_fact = {v[0]: sid for sid, v in facts.items()}
    script = scripts_for()
    cfg = json.loads(cfg_path.read_text())
    server = ScriptedServer(cfg["port"], cfg["model"], script, first_fact).start()
    try:
        rc = run_stage(work, cfg_path, work / "2c.log")
        check(rc == 0, "2c exits cleanly" + ("" if rc == 0 else f" (see {work / '2c.log'})"))
        if rc != 0:
            return
        sent = list(server.sent)
        count = {}
        for r in sent:
            count[(r["segment"], r["turn"])] = count.get((r["segment"], r["turn"]), 0) + 1
        want = {("4/S0", "t1"): 3, ("4/S1", "t1"): 2, ("4/S1", "t2"): 2, ("4/S2", "t1"): 1, ("4/S2", "t2"): 1,
                ("16/S0", "t1"): 2, ("16/S0", "t2"): 2, ("16/S1", "t1"): 1, ("16/S1", "t2"): 1,
                ("16/S2", "t1"): 3, ("16/S2", "t2"): 1, ("16/S3", "t1"): 1, ("16/S3", "t2"): 3}
        check(count == want, "requests per segment and turn: retries on the retry kinds only, up to the config's "
                             "retries" + ("" if count == want else f" (got {count})"))

        def req(sid, turn, attempt):
            return next((r for r in sent if (r["segment"], r["turn"], r["attempt"]) == (sid, turn, attempt)), None)

        def content(sid, turn, attempt):
            a = script[sid][turn][attempt]
            return a if isinstance(a, str) else json.dumps(a)

        r = req("16/S0", "t1", 1)
        fb = FEEDBACK.format(problems="\n".join(f"- {x}" for x in [
            'The name "XR" is an acronym. A concept\'s name is always the full term in words; put "XR" in its '
            'aliases. If your list already has this concept under its full name, join the two.',
            'The alias "trackers" of "tracking" is written in none of the facts. Remove it.']))
        check(r is not None and len(r["messages"]) == 3 and r["messages"][1]["content"] == content("16/S0", "t1", 0)
              and r["messages"][2]["content"] == fb,
              "the turn-1 retry shows the earlier answer and the decided problem lines (3D space not among them)")
        r = req("4/S1", "t1", 1)
        check(r is not None and "has an empty name" in r["messages"][2]["content"]
              and "cites the fact numbers 99" in r["messages"][2]["content"],
              "the empty name and the number out of range are sent back")
        r = req("16/S0", "t2", 1)
        last = r["messages"][-1]["content"] if r else ""
        check(r is not None and len(r["messages"]) == 5 and r["messages"][3]["content"] == content("16/S0", "t2", 0)
              and "is related to" in last and "joins a concept to itself" in last and "is written 2 times" in last,
              "the turn-2 retry shows its earlier answer and the vague label, self triple and duplicate")
        kept1 = {"4/S1": 1, "4/S2": 0, "16/S0": 1, "16/S1": 0, "16/S2": 1, "16/S3": 0}
        t2 = [r for r in sent if r["turn"] == "t2"]
        cont = all(r["messages"][0]["content"] == req(r["segment"], "t1", 0)["messages"][0]["content"]
                   and r["messages"][1]["content"] == content(r["segment"], "t1", kept1[r["segment"]])
                   and r["messages"][2]["content"].startswith("Now give the relationships")
                   and len(r["messages"]) == (3 if r["attempt"] == 0 else 5) for r in t2)
        check(cont, "turn 2 continues from turn 1's prompt and its kept answer only (16/S2: the second of three)")
        check(all("5. Directed, and once." in r["messages"][2]["content"] for r in t2)
              and all("Acronyms belong here and only here." in r["messages"][0]["content"] for r in sent),
              "the prompts sent carry the new rules")

        cmap, rmap, checks = load_out(work)
        names = {}
        for cid, c in cmap.items():
            names.setdefault(cid.rsplit("/", 1)[0], []).append(c["name"])
        check(all(r["schema"]["properties"]["relations"]["items"]["properties"]["subject"]["enum"]
                  == names[r["segment"]] for r in t2), "the triple schema allows only the segment's checked concept names")
        check(names.get("16/S2") == ["VR", "augmented reality", "tracking"],
              f"16/S2: the attempt with the fewest problems kept, not the last ({names.get('16/S2')})")
        check(checks["16/S2"]["unresolved"] == {"turn 1": [
            'The name "VR" is an acronym. A concept\'s name is always the full term in words; put "VR" in its '
            'aliases. If your list already has this concept under its full name, join the two.']},
            "16/S2: marked unresolved with its remaining problem")
        triples = sorted((cmap[r["subject"]]["name"], r["label"], cmap[r["object"]]["name"])
                         for rid, r in rmap.items() if rid.startswith("16/S3/"))
        check(triples == sorted([("tracking", "is used by", "VR headset"), ("VR headset", "uses", "tracking"),
                                 ("VR headset", "is shown in", "VR headset")]),
              f"16/S3: the turn-2 answer with the fewest problems kept ({triples})")
        check(list(checks["16/S3"]["unresolved"]) == ["turn 2"] and len(checks["16/S3"]["unresolved"]["turn 2"]) == 1
              and "joins a concept to itself" in checks["16/S3"]["unresolved"]["turn 2"][0],
              "16/S3: marked unresolved in turn 2")
        f = checks["16/S3"]["flags"]
        check(f.get("acronym_in_name") and f.get("merged") == ["Tracking"] and "body-part tracking" in
              f.get("name_not_in_facts", []) and f.get("fact_without_concept") and f.get("reverse") == [0, 1]
              and f.get("self_triple") == [2], "16/S3: the report-only kinds reported (and self_triple, not reverse)")
        check(checks["4/S0"]["errors"] and not names.get("4/S0") and not any(r["segment"] == "4/S0" for r in t2),
              "4/S0: never JSON is no answer, with no concepts and no turn 2")
        check(all(not checks[s]["errors"] for s in checks if s != "4/S0"), "no other segment counted as no answer")
        check(names.get("16/S0", [None])[0] == "extended reality" and not checks["16/S0"]["unresolved"]
              and not checks["4/S1"]["unresolved"], "16/S0, 4/S1: the answers that passed after a retry are kept")
        rt = checks["16/S0"]["retries"]
        check(rt.get("turn 1", {}).get("lost") == ["XR"] and rt["turn 1"].get("added") == ["extended reality"]
              and rt["turn 1"].get("attempts") == 2 and rt["turn 1"].get("kept") == 2,
              f"16/S0 turn 1: lost XR, added extended reality ({rt.get('turn 1')})")
        check(sorted(rt.get("turn 2", {}).get("lost", [])) == sorted(["tracking | is related to | extended reality",
                                                                     "tracking | is a part of | extended reality",
                                                                     "virtual reality | is a kind of | virtual reality"])
              and len(rt["turn 2"].get("added", [])) == 3, "16/S0 turn 2: the triples lost and added")
        r2 = checks["16/S2"]["retries"].get("turn 1", {})
        check(r2.get("attempts") == 3 and r2.get("kept") == 2 and r2.get("lost") == ["AR"]
              and r2.get("added") == ["augmented reality"], f"16/S2: 3 attempts, the second kept, lost AR ({r2})")
        check(all(not checks[s]["retries"] for s in ("4/S2", "16/S1")), "4/S2, 16/S1 (the trial's answers): no retry")
        summ = json.loads((work / "output" / COURSE / "stage_2c_concepts" / "checks" / "summary.json").read_text())
        check(summ.get("retried") == {"turn 1": 4, "turn 2": 3} and summ.get("lost") == {"concepts": 3, "triples": 3}
              and summ.get("added") == {"concepts": 3, "triples": 4}
              and summ.get("unresolved") == {"turn 1": ["16/S2"], "turn 2": ["16/S3"]}
              and summ.get("no_answer") == ["4/S0"],
              f"the run summary counts retries, lost and added, unresolved and no answer ({summ.get('retried')}, "
              f"lost {summ.get('lost')}, added {summ.get('added')})")
        log = (work / "2c.log").read_text()
        check("retried: turn 1 4, turn 2 3; lost 3 concepts, 3 triples; added 3 concepts, 4 triples" in log,
              "the printed summary counts them too")
        ff = {s: checks[s]["flags"] for s in ("4/S2", "16/S1")}
        check(not any(x.get("alias_not_written") or x.get("alias_not_in_facts") for x in ff.values())
              and not ff["4/S2"].get("name_not_in_facts")
              and sorted(ff["16/S1"].get("name_not_in_facts", [])) == ["body-part tracking", "environment tracking",
                                                                       "registration", "user tracking"],
              "the trial's false alarms are gone; its 4 true name_not_in_facts remain")
        text = (work / "output" / COURSE / "stage_2c_concepts" / "text" / "lec_16.txt").read_text()
        check("unresolved turn 1:" in text and "retried turn 1:" in text, "the text view shows retries and unresolved")

        print("rerun", flush=True)
        od = work / "output" / COURSE / "stage_2c_concepts"
        before, n = tree_bytes(od), len(server.sent)
        rc = run_stage(work, cfg_path, work / "2c_rerun.log")
        check(rc == 0 and len(server.sent) == n, "a rerun is answered from the cache")
        check(tree_bytes(od) == before, "a rerun writes the same files")
    finally:
        server.stop()


def main():
    global s2c
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", help="folder for the copy (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the copy afterwards")
    ap.add_argument("--s2c", help="test this s2c_concepts.py instead of the pipeline's")
    a = ap.parse_args()
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="fake_2c_"))
    work.mkdir(parents=True, exist_ok=True)
    before = {d: snapshot(REPO / d) for d in ("pipeline/output", "analysis")}
    cfg = make_copy(work, Path(a.s2c) if a.s2c else None)
    print(f"copy in {work}", flush=True)
    sys.path.insert(0, str(work))
    for m in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[m]
    s2c = importlib.import_module("scripts.s2c_concepts")
    check(Path(s2c.__file__).resolve().parent.parent == work.resolve(), "the module under test is the copy's")
    try:
        test_unit()
    except Exception as e:   # a broken module: report and go on to the run
        check(False, f"unit tests raised {type(e).__name__}: {e}")
    test_run(work, cfg)
    print("output", flush=True)
    check(all(snapshot(REPO / d) == before[d] for d in before), "nothing under the real output/ or analysis/ changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed"
          + (f"; copy kept in {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
