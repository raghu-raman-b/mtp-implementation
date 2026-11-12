"""Plumbing test of stages 4a to 4d (definitions, goals, lecture graph, the knowledge layer) with a fake model.

    python3 tests/fake_knowledge.py [--work DIR] [--keep]

No stage 3 output exists yet, so the test writes synthetic inputs: a registry (concepts, segment concepts,
relations), the 2c concept maps and the 2b facts it is built from, over the real segment maps and sentence times of
lectures 1 to 8 (copied). Everything runs in a copy of the pipeline folder in a new temporary folder; the fake model
server (KnowledgeFake below, over scripts/llm/fake_server.py) listens on a free port (never 8094 or 8095, the SSH
forward to the EC2) through a copy of the Qwen config with that port, model_path "fake/qwen" (so no cache hash can
match a real one), no wait, and the config's retries (2: three attempts).
The embedder is a stand-in (put into sys.modules["scripts.embed"]) when scripts/embed.py is not there.

The synthetic course (N = 8 lectures). "virtual reality" (lecture 1, used in all 8) and "extended reality" (lecture
1, used in 7) are hub concepts; "head-mounted display" 2 -> 3, "tracking" 3 -> 5, "field of view" 2 -> 5 (implied by
2 -> 3 -> 5), "rendering" 4 -> 8, "display resolution" 5 -> 8, "stereoscopy" defined in 2 and 6, used in 8;
"latency" defined in 6 and used in 4 (no link backwards); "presence" never defined; "immersion" used in lectures 1 to
6 with 3 facts each and defined only in 7/S3 (2 defining facts), for the cap (the test runs 4a with --cap 6).

The fake model's 4a answers (by the concept's name) seed every retry kind of decision D12 in the first attempt and
answer well after it: rendering ("as the lecturer explains") and head-mounted display ("In this lecture") a lecture
reference, latency a fact in both lists, tracking no fact cited, stereoscopy an empty definition, display resolution
a number outside the list. presence never writes its name (unresolved: the best answer kept), extended reality never
answers JSON (no answer), field of view lists a misplaced fact; the others answer well at once.
The 4b lecture answers (by the lecture's title) leave the last segment in no objective (allowed; in lecture 2 it
defines stereoscopy) and seed in the first attempt: lecture 2 a segment in two objectives, 3 the objectives out of
order, 4 an empty "achieves", 5 a segment number out of range; lecture 6 has an objective [1, 3] with segment 2 in
another one in every attempt (unresolved); lecture 7 an objective [1, 3] with segment 2 in none (not a gap: asked
once); lecture 8 never answers JSON (no answer). The course answer first leaves lecture 7 in no goal (lecture 8, with
no answer, is not counted) and lists lectures out of order, repeated, and in one goal more than half of them; the
retry adds lecture 7.

What it looks for (each line is what a broken stage would show):
  4a  a concept without its request or definition; a definition citing a fact outside its list (seeded, and the
      numbers mapped through anything but the shown list); the cap not putting defining facts first, the shown
      facts not in lecture order, * on the wrong facts, or no "(n more facts not shown)" line when capped;
      defined_mismatch not raised where defined_in is empty (seeded both ways); misplaced facts not reported; a
      retry problem (outside the list, empty definition, no fact cited, a fact in both lists, the name absent, "the
      lecturer"/"this lecture") not caught, not retried, or retried without its problem shown; a failed answer
      thrown away instead of kept as unresolved, or an unparseable one kept; the retry log or its counts wrong
  4b  a lecture without its call, or the course call missing or not built from the lecture goals (with their
      keys in brackets and "Achieves:" lines); a segment not listed, or listed without its registry concepts;
      objective or goal IDs wrong (<n>/O1.., <n>/G, G1..); an objective naming another lecture's segment; a retry
      check (out of range, twice, out of order, an empty goal or achieves, a gap that another objective fills) not
      firing, not retried, or retried without its problem shown; a gap of segments in no objective taken for one;
      in_no_objective without the concepts the segment defines; a failed lecture answer thrown away instead of kept
      as unresolved; the course retry missing a lecture in no goal or counting one whose call gave no answer; a
      goal's lectures not put in course order, repeats not dropped, a goal over half the lectures not reported;
      the retry log or its counts wrong
  4c  links other than those worked out by hand; a link to an earlier lecture; a transitive link counted as direct;
      a hub concept making every lecture depend on lecture 1 (and, as a control, the same check failing with the
      weighting off); the rule checks missing a seeded backward or transitive link; graph.json not the graph of
      the registry; a lecture without its needed-before file, or one without the 4a definition and defining facts
  4d  the layer failing its own check; a concept missing from the name index, an acronym not indexed as one; a
      card without its facts (defining first), relationships or where it is defined; a fact without its vector,
      concepts or time; a lecture without its concepts by kind, concept map or goals; the goal tree missing a goal,
      objective or segment; a concept without its path; a broken reference not caught (seeded: a card pointing to
      a missing concept, a fact removed from the store); a malformed file passing the schema check (seeded: a
      missing field, a wrong type, a bad ID)
  rerun  any output file different when rerun from the caches, or the model called again
  output  any file under the real output/ created or changed
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
sys.path.insert(0, str(ROOT))

from scripts import course_meta, lectures as lec  # noqa: E402
from scripts import s4a_definitions as s4a, s4b_goals as s4b, s4c_lecture_graph as s4c  # noqa: E402
from scripts import s4d_assemble as s4d  # noqa: E402
from scripts.llm import LLMConfig  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402
from scripts.llm.client import FEEDBACK  # noqa: E402

COURSE = "nptel_vr"
KEYS = [str(k) for k in range(1, 9)]
FORBIDDEN = {8094, 8095}
CAP = 6
FAILURES: list[str] = []

# name, aliases, [(segment, defined, number of facts)] in course order of first appearance
SPEC = [
    ("virtual reality", ["VR"], [("1/S0", True, 2)] + [(f"{k}/S0", False, 1) for k in range(2, 9)]),
    ("extended reality", ["XR"], [("1/S1", True, 2)] + [(f"{k}/S0", False, 1) for k in range(2, 8)]),
    ("immersion", [], [(f"{k}/S2", False, 3) for k in range(1, 7)] + [("7/S3", True, 2)]),
    ("head-mounted display", ["HMD"], [("2/S0", True, 2), ("3/S1", False, 1)]),
    ("field of view", ["FOV"], [("2/S1", True, 2), ("5/S0", False, 1)]),
    ("stereoscopy", [], [("2/S2", True, 2), ("6/S0", True, 2), ("8/S3", False, 1)]),
    ("tracking", [], [("3/S0", True, 2), ("5/S1", False, 1)]),
    ("rendering", [], [("4/S0", True, 2), ("8/S1", False, 1)]),
    ("presence", [], [("4/S1", False, 1), ("7/S2", False, 1)]),
    ("latency", [], [("4/S3", False, 1), ("6/S1", True, 2)]),
    ("display resolution", [], [("5/S2", True, 2), ("8/S2", False, 1)]),
]
# subject, label, object (concept names), segment
RELS = [("head-mounted display", "is used to view", "virtual reality", "2/S0"),
        ("tracking", "is needed for", "virtual reality", "3/S0")]


FACT_LINE = re.compile(r"\[(\d+)\](\*?) \((?:lecture|tutorial) [^)]*\) (.*)")
NOT_JSON = "I would rather explain this in prose."


class KnowledgeFake(FakeServer):
    """The plain fake, except for the seeded answers of the module docstring (4a by the concept's name)."""
    base_seed = 0                  # the config's seed: the client sends seed + attempt (0, 1, 2)
    lectures: dict = {}            # a lecture's first segment sub-goal -> its key (titles repeat in titles.tsv)

    def answer(self, body: dict) -> dict:
        msgs = body["messages"]
        prompt = msgs[0]["content"]
        attempt = body.get("seed", 0) - self.base_seed
        content = None
        m = re.search(r"\nName: (.*)\n", prompt)
        t = SEG_LINE.search(prompt)
        if "THE CONCEPT" in prompt and m:
            content = self.definition(m[1], sum(1 for x in prompt.splitlines() if FACT_LINE.fullmatch(x)), attempt)
        elif "THE SEGMENTS" in prompt and t:
            content = self.lecture(self.lectures[t[2]], len(SEG_LINE.findall(prompt)), attempt)
        elif "THE LECTURES" in prompt:
            content = self.course(attempt)
        if content is None:
            return super().answer(body)
        with self.lock:
            self.requests += 1
            if self.log:
                with open(self.log, "a") as f:
                    f.write(json.dumps({"model": body.get("model"), "messages": msgs,
                                        "schema": body["response_format"]["json_schema"]["schema"]}) + "\n")
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(content) // 4}}

    @staticmethod
    def definition(name: str, n: int, attempt: int) -> str:
        a = {"facts": [1, 2] if n >= 2 else [1], "definition": f"{name.capitalize()} is a fake concept of the course.",
             "defined": True, "misplaced": []}
        if name == "extended reality":
            return NOT_JSON
        if name == "presence":
            a["definition"] = f"A feeling of being there (attempt {attempt + 1})."
        elif name == "field of view":
            a["misplaced"] = [n]
        elif attempt == 0:
            if name == "rendering":
                a["definition"] = "Rendering, as the lecturer explains, makes images."
            elif name == "head-mounted display":
                a["definition"] = "In this lecture, a head-mounted display is a display worn on the head."
            elif name == "latency":
                a["misplaced"] = [2]
            elif name == "tracking":
                a["facts"] = []
            elif name == "stereoscopy":
                a["definition"] = ""
            elif name == "display resolution":
                a["facts"] = [1, 99]
        return json.dumps(a)

    @staticmethod
    def lecture(key: str, n: int, attempt: int) -> str:
        obj = lambda nums, ach="It prepares the next step.": {  # noqa: E731
            "segments": nums, "goal": f"Explain topic {nums[0]} of lecture {key}.", "achieves": ach}
        h = n // 2
        objs = [obj(list(range(1, h + 1))), obj(list(range(h + 1, n)))]       # segment n in no objective
        if key == "8":
            return NOT_JSON
        if key == "6":
            objs = [obj([1, 3]), obj([2]), obj([4, 5])]
        elif key == "7":
            objs = [obj([1, 3]), obj([4, 5])]
        elif attempt == 0:
            if key == "2":
                objs = [obj([1, 2]), obj([2])]
            elif key == "3":
                objs = objs[::-1]
            elif key == "4":
                objs[1] = obj(objs[1]["segments"], ach="")
            elif key == "5":
                objs[1] = obj(objs[1]["segments"] + [n + 1])
        return json.dumps({"objectives": objs, "goal": f"Explain what lecture {key} teaches.",
                           "achieves": "It serves the course."})

    @staticmethod
    def course(attempt: int) -> str:
        goals = [{"lectures": ["2", "1", "1", "3", "4", "5"], "goal": "Explain the basics.", "achieves": "A start."},
                 {"lectures": ["5", "6"] + (["7"] if attempt else []), "goal": "Apply them.", "achieves": "Use."}]
        return json.dumps({"reasoning": "fake", "goals": goals})


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in FORBIDDEN:
            return port


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def tree_bytes(folder: Path, skip=("calls.jsonl",)) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and p.name not in skip}


# ---------------------------------------------------------------- the copy and the synthetic inputs
def make_copy(work: Path) -> Path:
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("scripts", "prompts", "configs", "schemas"):
        if (ROOT / d).exists():
            shutil.copytree(ROOT / d, work / d, ignore=ign)
    meta = work / "input" / COURSE / "input"
    meta.mkdir(parents=True)
    for f in ("course.json", "titles.tsv"):
        shutil.copy(ROOT / "input" / COURSE / "input" / f, meta / f)
    src, dst = ROOT / "output" / COURSE, work / "output" / COURSE
    for sub in ("stage_1b_verify_segments/segment_maps", "stage_0a_preprocess/times"):
        (dst / sub).mkdir(parents=True)
        for k in KEYS:
            shutil.copy(src / sub / f"{lec.stem_of(k)}.json", dst / sub / f"{lec.stem_of(k)}.json")
    cfg = json.loads((ROOT / "configs" / "qwen38_27b_vllm.json").read_text())
    cfg.update(port=free_port(), model_path="fake/qwen", attach_wait_s=0, server_log="fake_server.log")
    path = work / "configs" / "fake_qwen.json"
    path.write_text(json.dumps(cfg, indent=1))
    (work / "run_stage.py").write_text(RUN_STAGE)
    return path


def synthesize(work: Path) -> dict:
    """Write the 2b facts, 2c concept maps and the stage 3 registry of the synthetic course. Returns what the test
    needs to know about it: {"facts": {fid: text}, "defining": {cid: [fids]}, "concepts": registry}."""
    out = work / "output" / COURSE
    segmaps = {k: json.loads((out / "stage_1b_verify_segments/segment_maps" / f"{lec.stem_of(k)}.json").read_text())
               for k in KEYS}
    facts, cmaps, seg_concepts, concepts, defining = {}, {}, {}, {}, {}
    nfact, nconc = {}, {}
    for i, (name, aliases, apps) in enumerate(SPEC, 1):
        cid = f"C{i:04d}"
        c = {"name": name, "aliases": aliases, "facts": [], "lectures": [], "segments": [], "defined_in": [],
             "merged": []}
        defining[cid] = []
        for sid, defined, n in apps:
            first = int(segmaps[s4a.lecture_of(sid)][sid]["first"].split("/")[1])
            fids = []
            for j in range(n):
                fid = f"{sid}/F{nfact.get(sid, 0)}"
                nfact[sid] = nfact.get(sid, 0) + 1
                facts[fid] = {"text": f"Fact {fid}: {name} ({'defines' if defined else 'uses'}) point {j}.",
                              "evidence": [f"{s4a.lecture_of(sid)}/{first + j}"]}
                fids.append(fid)
            scid = f"{sid}/C{nconc.get(sid, 0)}"
            nconc[sid] = nconc.get(sid, 0) + 1
            cmaps[scid] = {"name": name, "aliases": aliases, "facts": fids, "defined": defined}
            seg_concepts[scid] = cid
            c["facts"] += fids
            c["lectures"] = list(dict.fromkeys(c["lectures"] + [s4a.lecture_of(sid)]))
            c["segments"].append(sid)
            if defined:
                c["defined_in"].append(sid)
                defining[cid] += fids
            c["merged"].append({"segment_concept": scid, "name": name, "how": "first" if not c["merged"] else "exact",
                                "reason": ""})
        concepts[cid] = c
    by_name = {c["name"]: cid for cid, c in concepts.items()}
    relations = {}
    for i, (s, label, o, sid) in enumerate(RELS, 1):
        sc = next(k for k, v in cmaps.items() if v["name"] == s and s4a.segment_of(k) == sid)
        oc = next(k for k, v in cmaps.items() if v["name"] == o and s4a.segment_of(k) == sid)
        rfacts = cmaps[sc]["facts"][:1]
        relations[f"R{i:04d}"] = {"subject": by_name[s], "label": label, "object": by_name[o], "facts": rfacts,
                                  "segments": [sid], "from": [f"{sid}/R0"]}
        cmaps[oc]["facts"] = list(dict.fromkeys(cmaps[oc]["facts"] + rfacts))
    for k in KEYS:
        stem = lec.stem_of(k)
        for stage, data in (("stage_2b_verify_facts/fact_maps", facts), ("stage_2c_concepts/concept_maps", cmaps)):
            (out / stage).mkdir(parents=True, exist_ok=True)
            part = {i: v for i, v in data.items() if s4a.lecture_of(i) == k}
            (out / stage / f"{stem}.json").write_text(json.dumps(part, indent=1))
    reg = out / "stage_3_registry"
    reg.mkdir(parents=True)
    for name, data in (("concepts", concepts), ("segment_concepts", seg_concepts), ("relations", relations)):
        (reg / f"{name}.json").write_text(json.dumps(data, indent=1))
    return {"facts": {f: v["text"] for f, v in facts.items()}, "defining": defining, "concepts": concepts}


RUNS: list[tuple[str, list[str], str]] = []   # the stages run so far: script, arguments, output folder


def stage(work: Path, script: str, args: list[str], log: Path, out: str | None = None, record: bool = True) -> int:
    """Run a stage script in the copy (through run_stage.py, which puts in the stand-in embedder if needed)."""
    if record:
        RUNS.append((script, args, out or ""))
    with log.open("w") as f:
        return subprocess.run([sys.executable, "-u", "run_stage.py", f"scripts/{script}", COURSE, *args], cwd=work,
                              stdout=f, stderr=subprocess.STDOUT).returncode


RUN_STAGE = '''"""Run a stage script; when scripts/embed.py is missing, a stand-in Embedder goes into sys.modules first."""
import hashlib, importlib.util, math, runpy, sys, types
sys.path.insert(0, ".")
if importlib.util.find_spec("scripts.embed") is None:
    class Embedder:
        def __init__(self, model="Qwen/Qwen3-Embedding-0.6B", cache=None):
            if model != "fake":
                raise RuntimeError("the stand-in embedder only knows the model 'fake'")
            self.model, self.cache = model, cache
        def embed(self, texts):
            out = []
            for t in texts:
                h = hashlib.sha256(t.encode()).digest()
                v = [b / 255 - 0.5 for b in h[:16]]
                n = math.sqrt(sum(x * x for x in v)) or 1.0
                out.append([x / n for x in v])
            return out
    mod = types.ModuleType("scripts.embed")
    mod.Embedder = Embedder
    sys.modules["scripts.embed"] = mod
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
'''


def test_rerun(work: Path, log: Path):
    print("rerun from the caches", flush=True)
    outs = [work / "output" / COURSE / o for _, _, os_ in RUNS for o in os_.split(",") if o]
    before = {str(o): tree_bytes(o) for o in outs}
    n0 = len(lines(log))
    ok = all(stage(work, s, a, work / f"rerun_{Path(s).stem}.log", record=False) == 0 for s, a, _ in list(RUNS))
    check(ok, "every stage reruns cleanly")
    check(len(lines(log)) == n0, f"the reruns are answered from the caches ({len(lines(log)) - n0} new requests)")
    after = {str(o): tree_bytes(o) for o in outs}
    diff = [f"{Path(o).name}/{f}" for o in before for f in set(before[o]) | set(after[o])
            if before[o].get(f) != after[o].get(f)]
    check(not diff, f"every output file the same after the rerun ({', '.join(diff[:5]) or 'none differ'})")


# ---------------------------------------------------------------- 4a
def shown_facts(prompt: str, text_to_id: dict) -> list[tuple[str, bool]]:
    """The facts a 4a prompt shows, in order: (fact ID, marked *)."""
    out = []
    for line in prompt.splitlines():
        m = FACT_LINE.fullmatch(line)
        if m:
            out.append((text_to_id[m[3]], bool(m[2])))
    return out


def test_4a(work: Path, cfg: Path, syn: dict, log: Path) -> int:
    print("4a definitions", flush=True)
    shown = ["F1", "F2", "F3"]
    _, fl = s4a.check_answer({"facts": [1, 4], "definition": "x", "defined": True, "misplaced": [0]}, shown, ["1/S0"])
    check(fl.get("outside_list") == [4, 0], "seeded: a cited and a misplaced number outside the list are flagged")
    _, fl = s4a.check_answer({"facts": [1], "definition": "  ", "defined": True, "misplaced": []}, shown, [])
    check(fl.get("empty_definition") and "defined_mismatch" in fl, "seeded: empty definition; defined without defined_in")
    _, fl = s4a.check_answer({"facts": [1], "definition": "x", "defined": False, "misplaced": [2]}, shown, ["1/S0"])
    check("defined_mismatch" in fl and fl.get("misplaced") == ["F2"], "seeded: not defined despite defined_in; misplaced mapped")
    sel = s4a.select_facts(["1/S0/F0", "1/S0/F1", "2/S0/F0", "10/S0/F0", "3/S1/F0"], ["10/S0/F0", "3/S1/F0"], 3)
    check(sel == ["1/S0/F0", "3/S1/F0", "10/S0/F0"], "cap: defining facts kept first, shown in lecture order (10 after 3)")
    good = {"facts": [1, 2], "definition": "Head-mounted displays (HMDs) are worn on the head.", "defined": True,
            "misplaced": []}
    seeded = {"outside_list": {**good, "misplaced": [5]}, "empty_definition": {**good, "definition": " "},
              "empty_facts": {**good, "facts": []}, "in_both": {**good, "misplaced": [2]},
              "name_absent": {**good, "definition": "A display worn on the head."},
              "lecture_reference": {**good, "definition": "A head-mounted display, says the lecturer, is worn."}}
    got = {k: [kind for kind, _ in s4a.problems(a, 3, "head-mounted display")] for k, a in seeded.items()}
    check(s4a.problems(good, 3, "head-mounted display") == [] and all(got[k] == [k] for k in seeded)
          and [k for k, _ in s4a.problems({**good, "definition": "In this lecture: head mounted display."}, 3,
                                          "head-mounted display")] == ["lecture_reference"],
          f"seeded: each retry problem found alone; the name matched across case, hyphen and plural ({got})")
    _, fl = s4a.check_answer({**good, "misplaced": [2]}, ["F1", "F2", "F3"], ["1/S0"], "head-mounted display")
    check("in_both" in fl and fl.get("misplaced") == ["F2"], "check_answer with the name reports the retry problems too")

    n0 = len(lines(log))
    check(stage(work, "s4a_definitions.py", ["--llm", "configs/fake_qwen.json", "--cap", str(CAP)],
                work / "4a.log", "stage_4a_definitions") == 0, "4a exits cleanly")
    every = lines(log)[n0:]
    sent = [r for r in every if len(r["messages"]) == 1]          # first attempts
    od = work / "output" / COURSE / "stage_4a_definitions"
    defs = json.loads((od / "definitions.json").read_text())
    concepts = syn["concepts"]
    cn = {v["name"]: k for k, v in concepts.items()}
    check(len(sent) == len(concepts), f"one first request per concept ({len(sent)} for {len(concepts)})")
    check(set(defs) == set(concepts) and all(d["definition"] for c, d in defs.items() if c != cn["extended reality"]),
          "every concept that got an answer has a definition")
    text_to_id = {v: k for k, v in syn["facts"].items()}
    ok_sub = ok_order = ok_mark = ok_cap = ok_map = True
    for r in sent:
        prompt = r["messages"][0]["content"]
        cid = next(c for c, v in concepts.items() if f"Name: {v['name']}\n" in prompt)
        got = shown_facts(prompt, text_to_id)
        ids = [f for f, _ in got]
        dset = set(syn["defining"][cid])
        ok_sub &= set(ids) <= set(concepts[cid]["facts"]) and ids == defs[cid]["shown"]
        ok_order &= ids == sorted(ids, key=s4a.fact_order)
        ok_mark &= all(star == (f in dset) for f, star in got)
        total = len(concepts[cid]["facts"])
        ok_cap &= len(ids) == min(CAP, total) and (dset <= set(ids) if len(dset) <= CAP else set(ids) <= dset)
        others = sorted((f for f in concepts[cid]["facts"] if f not in dset), key=s4a.fact_order)
        ok_cap &= [f for f in ids if f not in dset] == others[:len(ids) - len(dset & set(ids))]
        n = len(ids)
        if not defs[cid]["errors"]:                                   # the fake's final answers cite [1, 2]
            ok_map &= defs[cid]["facts"] == list(dict.fromkeys(ids[min(i, n) - 1] for i in (1, 2)))
    check(ok_sub, "each prompt shows only the concept's own facts (and definitions.json records them)")
    check(ok_order, "the shown facts are in lecture order")
    check(ok_mark, "* marks exactly the defining facts")
    check(ok_cap, f"cap {CAP}: defining facts first, then the others in lecture order")
    imm = cn["immersion"]
    check(defs[imm]["capped"] and set(syn["defining"][imm]) <= set(defs[imm]["shown"]),
          "immersion (20 facts, defined only in lecture 7) is capped and keeps both defining facts")
    prompt_of = {c: next(r["messages"][0]["content"] for r in sent if f"Name: {v['name']}\n" in r["messages"][0]["content"])
                 for c, v in concepts.items()}
    tail = lambda c: prompt_of[c].split("\nTHE DEFINITION\n")[0].rstrip().splitlines()[-1]  # noqa: E731
    check(tail(imm) == f"({20 - CAP} more facts not shown)" and FACT_LINE.fullmatch(tail(cn["rendering"]))
          and "Begin with the name exactly as given above" in prompt_of[imm]
          and "a last line says how many are left out" in prompt_of[imm],
          f"capped: the last line says how many facts are not shown ({tail(imm)!r}); none when all are shown; the "
          f"prompt's new THE FACTS paragraph and first bullet")
    check(ok_map, "cited numbers mapped to fact IDs through the shown list")
    chk = json.loads((od / "checks.json").read_text())
    want = {c for c, v in concepts.items() if not v["defined_in"]}
    got = {c for c, f in chk["concepts"].items() if "defined_mismatch" in f}
    check(got == want, f"defined_mismatch where the fake says defined and defined_in is empty ({sorted(got)})")
    check(chk["totals"]["misplaced"] == [cn["field of view"]], "misplaced facts reported (field of view, seeded)")

    # retries (decision D12)
    attempts = {c: sum(1 for r in every if f"Name: {v['name']}\n" in r["messages"][0]["content"])
                for c, v in concepts.items()}
    retried = {"rendering": "the lecturer", "head-mounted display": "this lecture", "latency": "in both",
               "tracking": '"facts" is empty', "stereoscopy": "The definition is empty",
               "display resolution": "[99] are not in the list"}
    want_n = {c: 3 if v["name"] in ("presence", "extended reality") else 2 if v["name"] in retried else 1
              for c, v in concepts.items()}
    check(attempts == want_n, f"each seeded problem retried until it is fixed, the others asked once ({attempts})")
    ok_fb = True
    for name, phrase in retried.items():
        second = next(r for r in every if f"Name: {name}\n" in r["messages"][0]["content"] and len(r["messages"]) == 3)
        ok_fb &= second["messages"][1]["role"] == "assistant" and phrase in second["messages"][2]["content"] \
            and second["messages"][2]["content"].startswith(FEEDBACK.split("{")[0])
    check(ok_fb, "each retry shows the model its answer and the problem found")
    ok_fixed = all(not defs[cn[n]]["unresolved"] and not defs[cn[n]]["errors"]
                   and defs[cn[n]]["definition"] == f"{n.capitalize()} is a fake concept of the course." for n in retried)
    check(ok_fixed, "the retried answers are the fixed ones, nothing left unresolved")
    pres, er = defs[cn["presence"]], defs[cn["extended reality"]]
    check(pres["definition"] == "A feeling of being there (attempt 3)." and pres["unresolved"]
          and "does not contain the name" in pres["unresolved"][0] and "name_absent" in chk["concepts"][cn["presence"]]
          and pres["facts"],
          "presence never writes its name: the best answer (the latest of equals) kept, its problem listed as unresolved")
    check(er["definition"] == "" and er["errors"] and not er["unresolved"] and cn["extended reality"] in
          chk["totals"]["no_answer"], "extended reality never answers JSON: no answer, nothing kept")
    rlog = chk["retries"]
    r0 = rlog.get(cn["rendering"], {})
    lat = rlog.get(cn["latency"], {})
    check(r0.get("lost") == ["definition: Rendering, as the lecturer explains, makes images."]
          and r0.get("added") == ["definition: Rendering is a fake concept of the course."]
          and lat.get("lost") == [f"misplaced {defs[cn['latency']]['shown'][1]}"] and lat.get("added") == [],
          "the retry log: what was lost and added between the first and the final attempt")
    t = chk["totals"]
    check((t["retried"], t["changed_by_retry"], t["unresolved"], t["no_answer"]) ==
          (8, 7, [cn["presence"]], [cn["extended reality"]]) and (t["lost"], t["added"]) == (5, 7)
          and set(rlog) == {c for c, k in want_n.items() if k > 1},
          f"the counts: 8 retried, 7 changed (extended reality: nothing parsed), 5 lost and 7 added (two retries "
          f"only add facts); presence "
          f"unresolved; extended reality no answer ({t['retried']}, {t['changed_by_retry']}, {t['lost']}, "
          f"{t['added']})")
    return len(every)


# ---------------------------------------------------------------- 4b
SEG_LINE = re.compile(r"\[(\d+)\] Sub-goal: (.*)\n    Defines: (.*)\n    Uses: (.*)")


def test_4b(work: Path, cfg: Path, log: Path):
    print("4b goals", flush=True)
    segs = [{"id": f"9/S{i}", "subgoal": f"sub {i}"} for i in range(4)]
    segs[3]["defines"] = ["latency"]
    o = lambda nums, g="g", a="a": {"segments": nums, "goal": g, "achieves": a}  # noqa: E731
    _, fl, pr = s4b.check_lecture({"objectives": [o([1, 3]), o([3, 9])], "goal": "g", "achieves": "a"}, segs, "9")
    check(fl.get("out_of_range") == [{"objective": "9/O2", "segments": [9]}] and fl.get("segment_twice") == ["9/S2"]
          and "not_consecutive" not in fl and "out_of_order" not in fl
          and fl.get("in_no_objective") == [{"segment": "9/S1", "subgoal": "sub 1", "defines": []},
                                            {"segment": "9/S3", "subgoal": "sub 3", "defines": ["latency"]}]
          and len(pr) == 2 and "do not exist: [9]" in pr[0] and "Segment 3 is in more than one" in pr[1],
          "seeded: out of range, in two objectives, left out (with what it defines); [1, 3] with segment 2 in no "
          "objective is not a gap")
    _, fl, pr = s4b.check_lecture({"objectives": [o([1, 3]), o([2])], "goal": "g", "achieves": "a"}, segs, "9")
    check(fl.get("not_consecutive") == ["9/O1"] and len(pr) == 1 and "segment 2 between them belongs to another" in pr[0],
          "seeded: a gap that another objective fills is not consecutive")
    _, fl, pr = s4b.check_lecture({"objectives": [o([3, 4]), o([1, 2])], "goal": "g", "achieves": "a"}, segs, "9")
    check(fl == {"out_of_order": True} and len(pr) == 1, "seeded: objectives out of lecture order, nothing else")
    _, fl, pr = s4b.check_lecture({"objectives": [o([1, 2, 3, 4], a=" ")], "goal": "", "achieves": "a"}, segs, "9")
    check(fl == {"empty_goal": ["9/O1 achieves", "9/G goal"]} and len(pr) == 2,
          "seeded: an empty achieves of an objective and an empty lecture goal")
    cgoal = lambda ls: {"lectures": ls, "goal": "g", "achieves": "a"}  # noqa: E731
    cg, fl, pr = s4b.check_course({"reasoning": "r", "goals": [cgoal(["4", "1", "4"])]}, ["1", "4", "16"])
    check(cg["goals"]["G1"]["lectures"] == ["1", "4"] and fl == {"repeats_removed": ["G1"], "reordered": ["G1"],
          "goal_over_half": [{"goal": "G1", "lectures": 2, "of": 3}], "lecture_in_no_goal": ["16"]}
          and len(pr) == 1 and "[16]" in pr[0],
          "seeded course: order and repeats fixed in code and reported, a goal over half the lectures, a lecture in "
          "no goal (a problem)")
    _, fl, pr = s4b.check_course({"reasoning": "r", "goals": [cgoal(["1", "4"])]}, ["1", "4", "16"],
                                 no_answer=["16"])
    check("lecture_in_no_goal" not in fl and pr == [], "a lecture whose call gave no answer is not counted")

    n0 = len(lines(log))
    check(stage(work, "s4b_goals.py", ["--llm", "configs/fake_qwen.json"], work / "4b.log", "stage_4b_goals") == 0,
          "4b exits cleanly")
    every = lines(log)[n0:]
    sent = [r for r in every if len(r["messages"]) == 1]          # first attempts
    od = work / "output" / COURSE / "stage_4b_goals"
    segmaps = {k: json.loads((work / "output" / COURSE / "stage_1b_verify_segments/segment_maps"
                              / f"{lec.stem_of(k)}.json").read_text()) for k in KEYS}
    lecture_reqs = [r for r in sent if "THE SEGMENTS" in r["messages"][0]["content"]]
    cg = json.loads((od / "course_goals.json").read_text())
    course_reqs = [r for r in sent if "THE LECTURES" in r["messages"][0]["content"]]
    check(len(lecture_reqs) == len(KEYS) and len(course_reqs) == 1,
          f"one call per lecture and one for the course ({len(lecture_reqs)} + {len(course_reqs)} for {len(KEYS)})")
    ok_segs = True
    for r in lecture_reqs:
        p = r["messages"][0]["content"]
        got = SEG_LINE.findall(p)
        k = next(k for k in KEYS if [g[1] for g in got] == [s["subgoal"] for s in segmaps[k].values()])
        ok_segs &= [int(g[0]) for g in got] == list(range(1, len(segmaps[k]) + 1))
        if k == "2":
            ok_segs &= got[0][2:] == ("head-mounted display", "virtual reality, extended reality")
    check(ok_segs, "every segment of each lecture listed, numbered from 1, with registry names (defines / uses)")
    p0 = lecture_reqs[0]["messages"][0]["content"]
    check("teaches nothing of the subject" in p0, "the lecture prompt has the new OBJECTIVES bullet")
    ok_ids = ok_seg_ids = True
    goals = {}
    check(json.loads((od / "lecture_goals" / "lec_8.json").read_text()) == {}, "lecture 8 (no answer): no goals")
    for k in KEYS[:-1]:
        g = json.loads((od / "lecture_goals" / f"{lec.stem_of(k)}.json").read_text())
        goals[k] = g
        objs = [i for i in g if i != f"{k}/G"]
        ok_ids &= f"{k}/G" in g and objs == [f"{k}/O{j}" for j in range(1, len(objs) + 1)] \
            and g[f"{k}/G"]["objectives"] == objs
        ok_seg_ids &= all(s in segmaps[k] for o in objs for s in g[o]["segments"])
    check(ok_ids, "lecture goal <n>/G and objectives <n>/O1.. in order, for every lecture")
    check(ok_seg_ids, "every objective names segments of its own lecture")
    cg = json.loads((od / "course_goals.json").read_text())
    ids = list(cg["goals"])
    check(ids and ids == [f"G{j}" for j in range(1, len(ids) + 1)]
          and all(set(g["lectures"]) <= set(KEYS) for g in cg["goals"].values()), "course goals G1.. with real lectures")
    cp = course_reqs[0]["messages"][0]["content"]
    g4 = goals["4"]
    block4 = (f"[4] Lecture 4: {course_meta.lecture_title(COURSE, '4')}\nGoal: {g4['4/G']['goal']}\n"
              f"Achieves: {g4['4/G']['achieves']}\nObjectives:\n- {g4['4/O1']['goal']}\n")
    check(all(goals[k][f"{k}/G"]["goal"] in cp for k in KEYS[:-1]) and block4 in cp
          and f"[8] Lecture 8: {course_meta.lecture_title(COURSE, '8')}\nGoal: (none: the lecture call gave no answer)"
          in cp and "its key in square brackets" in cp and "written exactly as in the square brackets" in cp,
          "the course call: every lecture as [key] Lecture n: title, its goal, achieves and objectives (lecture 8: "
          "none); the prompt's new THE LECTURES paragraph and lectures bullet")
    chk = json.loads((od / "checks.json").read_text())
    L = chk["lectures"]

    # retries (decision D12)
    of = lambda r, k: ("THE SEGMENTS" in r["messages"][0]["content"]  # noqa: E731
                       and f"[1] Sub-goal: {next(iter(segmaps[k].values()))['subgoal']}\n" in r["messages"][0]["content"])
    attempts = {k: sum(1 for r in every if of(r, k)) for k in KEYS}
    check(attempts == {"1": 1, "2": 2, "3": 2, "4": 2, "5": 2, "6": 3, "7": 1, "8": 3}
          and len(course_reqs) == 1 and len([r for r in every if "THE LECTURES" in r["messages"][0]["content"]]) == 2,
          f"lecture retries as seeded (a gap of segments in no objective asked once), the course retried once "
          f"({attempts})")
    phrase = {"2": "Segment 2 is in more than one objective", "3": "not in lecture order", "4": 'empty "achieves"',
              "5": "do not exist: [5]"}
    ok_fb = True
    for k, ph in phrase.items():
        second = next(r for r in every if of(r, k) and len(r["messages"]) == 3)
        ok_fb &= second["messages"][1]["role"] == "assistant" and ph in second["messages"][2]["content"]
    cr = next(r for r in every if "THE LECTURES" in r["messages"][0]["content"] and len(r["messages"]) == 3)
    check(ok_fb and "[7]" in cr["messages"][2]["content"] and "[8]" not in cr["messages"][2]["content"],
          "each retry shows its problem; the course retry names lecture 7 and not lecture 8 (no answer)")
    check(not any("unresolved" in L.get(k, {}) for k in ("2", "3", "4", "5")) and goals["2"]["2/O1"]["segments"] == ["2/S0"]
          and [goals["3"][o]["segments"][0] for o in ("3/O1", "3/O2")] == ["3/S0", "3/S2"],
          "the retried lectures keep their fixed answers")
    check(L["6"].get("not_consecutive") == ["6/O1"] and L["6"].get("unresolved")
          and "segment 2 between them belongs to another" in L["6"]["unresolved"][0]
          and goals["6"]["6/O1"]["segments"] == ["6/S0", "6/S2"],
          "lecture 6: the gap filled by another objective stays: unresolved, the best answer kept")
    check(set(L["7"]) == {"in_no_objective"} and [x["segment"] for x in L["7"]["in_no_objective"]] == ["7/S1", "7/S5"]
          and L["2"]["in_no_objective"] == [{"segment": "2/S2", "subgoal": segmaps["2"]["2/S2"]["subgoal"],
                                             "defines": ["stereoscopy"]}]
          and chk["totals"]["in_no_objective_defining"] == 1,
          "in_no_objective reported with what the segment defines (2/S2: stereoscopy); [1, 3] with 2 in none passes")
    check(L["8"].get("errors") and chk["totals"]["no_answer"] == ["lecture 8"], "lecture 8: no answer")
    C = chk["course"]
    check(cg["goals"]["G1"]["lectures"] == ["1", "2", "3", "4", "5"] and cg["goals"]["G2"]["lectures"] == ["5", "6", "7"]
          and C.get("reordered") == ["G1"] and C.get("repeats_removed") == ["G1"]
          and C.get("goal_over_half") == [{"goal": "G1", "lectures": 5, "of": 8}] and "lecture_in_no_goal" not in C
          and C.get("not_counted") == ["8"] and "unresolved" not in C,
          "course: order and repeats fixed, a goal over half the lectures reported, lecture 8 not counted")
    t, rl = chk["totals"], chk["retries"]
    check(rl["course"]["lost"] == ["[5, 6] Apply them.", "[5, 6] achieves: Use."]
          and rl["course"]["added"] == ["[5, 6, 7] Apply them.", "[5, 6, 7] achieves: Use."]
          and rl["lectures"]["2"]["lost"][0].startswith("objective [2/S0, 2/S1]:")
          and rl["lectures"]["4"]["lost"] == ["objective [4/S2] achieves: "]
          and set(rl["lectures"]) == {"2", "3", "4", "5", "6", "8"},
          "the retry log: what each retried answer lost and added")
    check((t["retried"], t["changed_by_retry"], t["unresolved"], t["lost"], t["added"]) == (7, 3, ["lecture 6"], 5, 5),
          f"the counts: 7 retried (6 lectures, the course), 3 changed (reordering or a dropped number changes no "
          f"item), lecture 6 unresolved ({t['retried']}, {t['changed_by_retry']}, {t['unresolved']}, {t['lost']}, "
          f"{t['added']})")


# ---------------------------------------------------------------- 4c
def links_of(graph: dict, kind: str) -> set:
    return {f"{ln['from']}->{ln['to']}" for ln in graph["links"] if ln["kind"] == kind}


def first_lecture_needed_by(graph: dict) -> list[str]:
    """The lectures that have lecture 1 among their prerequisites."""
    return [L for L in graph["lectures"] if "1" in graph["prerequisites"][L]["all"]]


def test_4c(work: Path, syn: dict):
    print("4c lecture graph", flush=True)
    concepts = syn["concepts"]
    cid = {c["name"]: k for k, c in concepts.items()}
    g = s4c.build(concepts, KEYS)
    direct, indirect, weak = links_of(g, "direct"), links_of(g, "indirect"), links_of(g, "weak")
    check(direct == {"2->3", "2->6", "3->5", "4->8", "5->8", "6->8"}, f"direct links as worked out by hand ({sorted(direct)})")
    check(indirect == {"2->5", "2->8"}, f"2->5 (via 3) and 2->8 (via 6) are indirect, not direct ({sorted(indirect)})")
    check(weak == {f"1->{k}" for k in KEYS[1:]}, "lecture 1's links carry only the two hub concepts: all weak")
    check(all(int(ln["from"]) < int(ln["to"]) for ln in g["links"]) and "6->4" not in direct | indirect | weak,
          "no link to an earlier lecture (latency: defined in 6, used in 4)")
    check(g["prerequisites"]["8"] == {"direct": ["4", "5", "6"], "all": ["2", "3", "4", "5", "6"]},
          "lecture 8: direct 4, 5, 6; all 2 to 6")
    k4 = {kind: sorted(concepts[c]["name"] for c in cs) for kind, cs in g["concept_kinds"]["4"].items()}
    check(k4 == {"introduced": ["rendering"], "met_again": ["extended reality", "virtual reality"],
                 "defined_later": ["immersion", "latency"], "assumed": ["presence"]}, f"lecture 4's concepts by kind ({k4})")
    check(g["concept_paths"][cid["display resolution"]]["path"] == ["2", "3", "5"]
          and g["concept_paths"][cid["presence"]]["path"] == [], "concept paths (display resolution 2, 3, 5; presence none)")
    check(s4c.verify(g, concepts) == {}, "the graph passes its own rules")
    check(first_lecture_needed_by(g) == [], "hub weighting on: no lecture needs lecture 1")
    off = s4c.build(concepts, KEYS, {"hub_floor": 1.0})
    check(first_lecture_needed_by(off) == KEYS[1:], "control, hub weighting off: every lecture needs lecture 1 (the check can fail)")
    bad = json.loads(json.dumps(g))
    bad["links"].append({"from": "6", "to": "4", "concepts": [cid["latency"]], "redefined": [], "weight": 0.5,
                         "kind": "weak"})                    # weak, so it makes no path 6 -> 4 -> 8
    bad["links"].append({"from": "3", "to": "4", "concepts": [cid["tracking"]], "redefined": [], "weight": 0.5,
                         "kind": "weak"})
    next(ln for ln in bad["links"] if ln["from"] == "2" and ln["to"] == "5")["kind"] = "direct"
    p = s4c.verify(bad, concepts)
    check(p == {"backward_link": ["6 -> 4"], "direct_implied": ["2 -> 5"], "wrong_concepts": ["3 -> 4"]},
          f"seeded: a backward link, a transitive link marked direct, a concept lecture 4 never uses ({p})")

    check(stage(work, "s4c_lecture_graph.py", [], work / "4c.log", "stage_4c_lecture_graph") == 0, "4c exits cleanly")
    od = work / "output" / COURSE / "stage_4c_lecture_graph"
    written = json.loads((od / "graph.json").read_text())
    check(written == json.loads(json.dumps(g)), "graph.json is the graph built from the registry")
    check(all((od / "needed" / f"{lec.stem_of(k)}.json").exists() for k in KEYS), "a needed-before file for every lecture")
    n8 = json.loads((od / "needed" / "lec_8.json").read_text())
    defs = json.loads((work / "output" / COURSE / "stage_4a_definitions" / "definitions.json").read_text())
    rend = next(c for c in n8["concepts"] if c["name"] == "rendering")
    check([d["lecture"] for d in n8["direct"]] == ["4", "5", "6"]
          and rend["definition"] == defs[cid["rendering"]]["definition"]
          and [f["fact"] for f in rend["defining_facts"]] == syn["defining"][cid["rendering"]],
          "before lecture 8: lectures 4, 5, 6; rendering with its 4a definition and defining facts")
    n7 = json.loads((od / "needed" / "lec_7.json").read_text())
    check([c["name"] for c in n7["never_defined"]] == ["presence"], "before lecture 7: presence is never defined")
    check(json.loads((od / "checks.json").read_text())["problems"] == {}, "checks.json reports no problem")


# ---------------------------------------------------------------- 4d
def test_4d(work: Path, syn: dict):
    print("4d knowledge layer", flush=True)
    check(stage(work, "s4d_assemble.py", ["--embed-model", "fake"], work / "4d.log",
                "knowledge,stage_4d_assemble") == 0, "4d exits cleanly, and its own check finds nothing")
    out = work / "output" / COURSE
    kd = out / "knowledge"
    load = lambda name: json.loads((kd / name).read_text())  # noqa: E731
    concepts = syn["concepts"]
    cid = {c["name"]: k for k, c in concepts.items()}
    report = json.loads((out / "stage_4d_assemble" / "checks.json").read_text())
    check(report["ok"] and report["files"] == 9 + len(KEYS) and report["references"] > 0,
          f"checks.json: {report['files']} files, {report['references']} references, nothing wrong")
    names = load("names.json")
    check(names.get("hmd") == [{"concept": cid["head-mounted display"], "as": "acronym", "text": "HMD"}]
          and names.get("head mounted display", [{}])[0].get("concept") == cid["head-mounted display"]
          and all(any(e["concept"] == c for es in names.values() for e in es) for c in concepts),
          "name index: every concept; 'HMD' as an acronym; 'head-mounted display' keyed without the hyphen")
    cards = load("concepts.json")
    ok_cards = set(cards) == set(concepts)
    for c, card in cards.items():
        d = syn["defining"][c]
        ok_cards &= card["facts"][:len(d)] == d and sorted(card["facts"]) == sorted(concepts[c]["facts"])
    check(ok_cards, "a card per concept, its facts with the defining ones first")
    vr, hmd = cards[cid["virtual reality"]], cards[cid["head-mounted display"]]
    check([r["relation"] for r in vr["relations"]["in"]] == ["R0001", "R0002"]
          and [r["relation"] for r in hmd["relations"]["out"]] == ["R0001"],
          "relationships on the cards in both directions")
    times = {}
    for k in KEYS:
        times.update(json.loads((out / "stage_0a_preprocess/times" / f"{lec.stem_of(k)}.json").read_text()))
    s0 = vr["defined_in"][0]
    check(s0["segment"] == "1/S0" and s0["start"] == times["1/0"]["start"] and s0["end"] == times["1/1"]["end"],
          "where a concept is defined: segment and the time of its defining facts' sentences")
    facts, emb = load("facts.json"), load("fact_embeddings.json")
    check(set(facts) == set(syn["facts"]) and set(emb["vectors"]) == set(facts)
          and all(len(v) == emb["dim"] for v in emb["vectors"].values()),
          f"every fact in the store with a vector of length {emb['dim']}")
    f0 = facts["4/S0/F3"]                                   # rendering's second fact, evidence 4/1
    check(f0["concepts"] == [cid["rendering"]] and (f0["start"], f0["end"]) == (times["4/1"]["start"], times["4/1"]["end"]),
          "a fact's concepts and time")
    l4, l2 = load("lectures/lec_4.json"), load("lectures/lec_2.json")
    k4 = {kind: sorted(concepts[c]["name"] for c in cs) for kind, cs in l4["concepts"].items()}
    check(k4["introduced"] == ["rendering"] and k4["assumed"] == ["presence"] and l2["concept_map"]["relations"] == ["R0001"]
          and l4["goal"]["id"] == "4/G" and l4["objectives"][0]["id"] == "4/O1",
          "per lecture: concepts by kind, its own concept map, its goals")
    goals = load("goals.json")
    segs = {sid for k in KEYS for sid in json.loads((out / "stage_1b_verify_segments/segment_maps"
                                                     / f"{lec.stem_of(k)}.json").read_text())}
    check(set(goals["segments"]) == segs and set(goals["lecture_goals"]) == {f"{k}/G" for k in KEYS[:-1]}
          and all(o in goals["objectives"] for g in goals["lecture_goals"].values() for o in g["objectives"]),
          "goal tree: every lecture goal, its objectives, every segment")
    graph = load("lecture_graph.json")
    check(graph["concept_paths"][cid["display resolution"]]["path"] == ["2", "3", "5"],
          "lecture graph with the path of lectures to each concept")
    check([a["concept"] for a in load("assumed.json")["concepts"]] == [cid["presence"]], "assumed knowledge: presence")

    # seeded damage, in a copy of the layer
    seeded = work / "seeded_knowledge"
    shutil.copytree(kd, seeded)
    good = s4d.check_layer(seeded)
    check(good["ok"], "the untouched copy passes")
    p = seeded / "concepts.json"
    d = json.loads(p.read_text())
    d[cid["head-mounted display"]]["relations"]["out"][0]["concept"] = "C9999"
    p.write_text(json.dumps(d))
    r = s4d.check_layer(seeded)
    check([b["id"] for b in r["broken_references"]] == ["C9999"] and not r["schema"],
          "seeded: a card pointing to a concept that does not exist is caught (and only that)")
    p = seeded / "facts.json"
    d = json.loads(p.read_text())
    del d["2/S0/F0"]
    p.write_text(json.dumps(d))
    r = s4d.check_layer(seeded)
    check({b["id"] for b in r["broken_references"]} == {"C9999", "2/S0/F0"}
          and any(b["at"].startswith("goals.json") for b in r["broken_references"]),
          "seeded: a fact removed from the store: every reference to it is caught (cards, goals, vectors)")
    shutil.rmtree(seeded)
    shutil.copytree(kd, seeded)
    p = seeded / "lectures" / "lec_3.json"
    d = json.loads(p.read_text())
    del d["title"]
    d["segments"]["3/S0"]["start"] = "zero"
    d["objectives"][0]["id"] = "3/X1"
    p.write_text(json.dumps(d))
    r = s4d.check_layer(seeded)
    errs = " | ".join(r["schema"])
    check(len(r["schema"]) == 3 and "missing 'title'" in errs and "expected number" in errs and "3/X1" in errs,
          f"seeded: a malformed lecture file fails the schema check ({len(r['schema'])} errors)")
    shutil.rmtree(seeded)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", help="folder for the copy (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the copy afterwards")
    a = ap.parse_args()
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="fake_knowledge_"))
    work.mkdir(parents=True, exist_ok=True)
    before = snapshot(ROOT / "output")
    cfg = make_copy(work)
    syn = synthesize(work)
    print(f"copy in {work}; fake model on port {json.loads(cfg.read_text())['port']}", flush=True)
    log = work / "fake_qwen.jsonl"
    c = json.loads(cfg.read_text())
    server = KnowledgeFake(c["port"], c["model"], str(log))
    server.base_seed = c.get("seed", 0)
    server.lectures = {next(iter(json.loads((work / "output" / COURSE / "stage_1b_verify_segments/segment_maps"
                                             / f"{lec.stem_of(k)}.json").read_text()).values()))["subgoal"]: k
                       for k in KEYS}
    check(len(server.lectures) == len(KEYS), "the fake tells the lectures apart by their first sub-goal")
    server.start()
    try:
        test_4a(work, cfg, syn, log)
        test_4b(work, cfg, log)
        test_4c(work, syn)
        test_4d(work, syn)
        test_rerun(work, log)
    finally:
        server.stop()
    print("output", flush=True)
    check(snapshot(ROOT / "output") == before, "nothing under the real output/ created or changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed"
          + (f"; copy kept in {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
