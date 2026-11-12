"""Plumbing test of stages 4a to 4d (definitions, goals, lecture graph, the knowledge layer) with a fake model.

    python3 tests/fake_knowledge.py [--work DIR] [--keep]

No stage 3 output exists yet, so the test writes synthetic inputs: a registry (concepts, segment concepts,
relations), the 2c concept maps and the 2b facts it is built from, over the real segment maps and sentence times of
lectures 1 to 8 (copied). Everything runs in a copy of the pipeline folder in a new temporary folder; the fake model
server (scripts/llm/fake_server.py) listens on a free port (never 8094 or 8095, the SSH forward to the EC2) through a
copy of the Qwen config with that port, model_path "fake/qwen" (so no cache hash can match a real one) and no wait.
The embedder is a stand-in (put into sys.modules["scripts.embed"]) when scripts/embed.py is not there.

The synthetic course (N = 8 lectures). "virtual reality" (lecture 1, used in all 8) and "extended reality" (lecture
1, used in 7) are hub concepts; "head-mounted display" 2 -> 3, "tracking" 3 -> 5, "field of view" 2 -> 5 (implied by
2 -> 3 -> 5), "rendering" 4 -> 8, "display resolution" 5 -> 8, "stereoscopy" defined in 2 and 6, used in 8;
"latency" defined in 6 and used in 4 (no link backwards); "presence" never defined; "immersion" used in lectures 1 to
6 with 3 facts each and defined only in 7/S3 (2 defining facts), for the cap (the test runs 4a with --cap 6).

What it looks for (each line is what a broken stage would show):
  4a  a concept without its request or definition; a definition citing a fact outside its list (seeded, and the
      numbers mapped through anything but the shown list); the cap not putting defining facts first, the shown
      facts not in lecture order, or * on the wrong facts; defined_mismatch not raised where defined_in is empty
      (seeded both ways); misplaced facts not reported
  4b  a lecture without its call, or the course call missing or not built from the lecture goals; a segment not
      listed, or listed without its registry concepts; objective or goal IDs wrong (<n>/O1.., <n>/G, G1..); an
      objective naming another lecture's segment; the segment checks (seeded: out of range, twice, a gap, left
      out, out of order) or the course checks (a lecture in no goal, out of order) not firing
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

from scripts import lectures as lec  # noqa: E402
from scripts import s4a_definitions as s4a, s4b_goals as s4b  # noqa: E402
from scripts.llm import LLMConfig  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402

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
    outs = [work / "output" / COURSE / o for _, _, o in RUNS if o]
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
FACT_LINE = re.compile(r"\[(\d+)\](\*?) \((?:lecture|tutorial) [^)]*\) (.*)")


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

    n0 = len(lines(log))
    check(stage(work, "s4a_definitions.py", ["--llm", "configs/fake_qwen.json", "--cap", str(CAP)],
                work / "4a.log", "stage_4a_definitions") == 0, "4a exits cleanly")
    sent = lines(log)[n0:]
    od = work / "output" / COURSE / "stage_4a_definitions"
    defs = json.loads((od / "definitions.json").read_text())
    concepts = syn["concepts"]
    check(len(sent) == len(concepts), f"one request per concept ({len(sent)} for {len(concepts)})")
    check(set(defs) == set(concepts) and all(d["definition"] for d in defs.values()), "every concept has a definition")
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
        ok_map &= defs[cid]["facts"] == list(dict.fromkeys(ids[min(i, n) - 1] for i in (1, 2)))  # the fake cites [1, 2]
    check(ok_sub, "each prompt shows only the concept's own facts (and definitions.json records them)")
    check(ok_order, "the shown facts are in lecture order")
    check(ok_mark, "* marks exactly the defining facts")
    check(ok_cap, f"cap {CAP}: defining facts first, then the others in lecture order")
    imm = next(c for c, v in concepts.items() if v["name"] == "immersion")
    check(defs[imm]["capped"] and set(syn["defining"][imm]) <= set(defs[imm]["shown"]),
          "immersion (20 facts, defined only in lecture 7) is capped and keeps both defining facts")
    check(ok_map, "cited numbers mapped to fact IDs through the shown list")
    chk = json.loads((od / "checks.json").read_text())
    want = {c for c, v in concepts.items() if not v["defined_in"]}
    got = {c for c, f in chk["concepts"].items() if "defined_mismatch" in f}
    check(got == want, f"defined_mismatch where the fake says defined and defined_in is empty ({sorted(got)})")
    check(set(chk["totals"]["misplaced"]) == set(concepts), "misplaced facts reported for every concept (the fake lists some)")
    return len(sent)


# ---------------------------------------------------------------- 4b
SEG_LINE = re.compile(r"\[(\d+)\] Sub-goal: (.*)\n    Defines: (.*)\n    Uses: (.*)")


def test_4b(work: Path, cfg: Path, log: Path):
    print("4b goals", flush=True)
    segs = [{"id": f"9/S{i}", "subgoal": f"sub {i}"} for i in range(4)]
    _, fl = s4b.check_lecture({"objectives": [{"segments": [1, 3], "goal": "g", "achieves": "a"},
                                              {"segments": [3, 9], "goal": "g", "achieves": "a"}],
                               "goal": "g", "achieves": "a"}, segs, "9")
    check(fl.get("out_of_range") and fl.get("segment_twice") == ["9/S2"] and fl.get("not_consecutive") == ["9/O1"]
          and [x["segment"] for x in fl.get("in_no_objective", [])] == ["9/S1", "9/S3"] and "out_of_order" not in fl,
          "seeded: segment out of range, in two objectives, a gap, left out")
    _, fl = s4b.check_lecture({"objectives": [{"segments": [3, 4], "goal": "g", "achieves": "a"},
                                              {"segments": [1, 2], "goal": "g", "achieves": "a"}],
                               "goal": "g", "achieves": "a"}, segs, "9")
    check(fl == {"out_of_order": True}, "seeded: objectives out of lecture order, nothing else")
    _, fl = s4b.check_course({"reasoning": "r", "goals": [{"lectures": ["4", "1"], "goal": "g", "achieves": "a"}]},
                             ["1", "4", "16"])
    check(fl == {"not_in_course_order": ["G1"], "lecture_in_no_goal": ["16"]},
          "seeded: a goal's lectures out of order; a lecture in no course goal")

    n0 = len(lines(log))
    check(stage(work, "s4b_goals.py", ["--llm", "configs/fake_qwen.json"], work / "4b.log", "stage_4b_goals") == 0,
          "4b exits cleanly")
    sent = lines(log)[n0:]
    od = work / "output" / COURSE / "stage_4b_goals"
    segmaps = {k: json.loads((work / "output" / COURSE / "stage_1b_verify_segments/segment_maps"
                              / f"{lec.stem_of(k)}.json").read_text()) for k in KEYS}
    lecture_reqs = [r for r in sent if "THE SEGMENTS" in r["messages"][0]["content"]]
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
    ok_ids = ok_seg_ids = True
    goals = {}
    for k in KEYS:
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
    check(all(goals[k][f"{k}/G"]["goal"] in cp for k in KEYS), "the course call is built from every lecture's goal")
    chk = json.loads((od / "checks.json").read_text())
    check(set(chk["lectures"]) == set(KEYS) and all("segment_twice" in chk["lectures"][k] for k in KEYS),
          "a check report for each lecture (the fake puts segments 1, 2 in both objectives)")
    check(chk["course"].get("lecture_in_no_goal") == KEYS[2:], "lectures in no course goal reported (the fake uses two)")


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
    server = FakeServer(c["port"], c["model"], str(log)).start()
    try:
        test_4a(work, cfg, syn, log)
        test_4b(work, cfg, log)
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
