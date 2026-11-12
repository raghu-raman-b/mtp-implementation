"""Plumbing test of stage 3 (s3a, s3b, s3c) with the fake embedder and a fake model, on synthetic 2c outputs.

    python3 tests/fake_registry.py [--work DIR] [--keep]

Runs in a copy of the pipeline folder (scripts, prompts, configs, the course's metadata) in a new temporary folder,
with synthetic 2c concept maps, relationships and 2b facts for lectures 1, 4 and 16 written there; nothing under
output/ is written, and the test checks that at the end. The fake model listens on a free port (never 8094 or 8095,
where the SSH forward to the EC2 may be) through a copy of the Qwen config with that port, model_path "fake/qwen" (so
its cache hashes never match a real run's) and attach_wait_s 0. The fake model answers a concept_same prompt with a
grouping read from the entries' names and facts (TRUTH below), as a careful model would, except for the cluster
holding "refresh rate", which gets the plain schema-built answer of scripts/llm/fake_server.py (invalid: entries in
several groups), so the retries and the fallback run.

The synthetic data seeds: one concept under three spellings (case, hyphen, plural) and "lens"/"lenses"/"Lenses"
(exact merges); "HMD" as a segment concept's name in two segments (an acronym alone: not exact) and as an alias of
the head-mounted display; "AR" meaning augmented reality in lecture 1 and aspect ratio in lecture 16 (a trap that
shares a name); "field of view" and "visual field extent" (a split: different names, same facts, no shared name);
"display resolution" and "tracking resolution" (a trap with close names); a relationship that becomes a self-loop
once HMD is merged; the same triple in lectures 1 and 16 with the label in another case.

What it looks for (each line is what a broken stage would show):
  embed     vectors not unit length or not deterministic; a rerun that embeds again instead of reading the cache;
            the Qwen instruction format wrong, or an instruction given to a model without the convention
  units     same-term rule: a missed case/hyphen/plural/space variant, or a merge of a part word ("display" in
            "head-mounted display", "displayed"); acronyms not recognised; the cap not respected, the wrong link
            cut, or the cap changing clusters below it; the answer check passing a missing, repeated or out-of-range
            entry or a name from another entry; the fact cap or the defining-first order not kept in the prompt
  3a        exact variants left in separate entries; an acronym merged by name alone; the acronym entries not
            reaching the head-mounted display's cluster (shared-alias rule broken); the split not reaching one
            cluster (embedding text or similarity broken); a cluster over the cap; cut pairs not listed
  3b        a cluster without its request, or a request for an entry outside every cluster; entries missing from
            or misnumbered in the prompt; the name enum not the cluster's names; an invalid answer accepted, or
            not retried, or its cluster not kept apart
  3c        a segment concept without a concept, or in two; "merged" not matching segment_concepts.json; IDs not
            contiguous or not in course order; facts, lectures, segments or defined_in not the union of the merged
            segment concepts; the model's name not used, or a losing name not kept as an alias; a merge without a
            decisions line; traps merged; a relationship end that is not a concept; a segment relationship lost
            without a log line (counts do not add up); the self-loop kept or not logged; the identical triple not
            joined, or its facts not joined
  rerun     s3a, s3b, s3c run again with the fake model stopped: any call to the model, any text embedded again,
            any output not byte-identical
  output    any file under the real output/ created or changed
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

from scripts import s3a_candidates as s3a, s3b_same as s3b  # noqa: E402
from scripts.embed import Embedder  # noqa: E402
from scripts.llm import LLMConfig  # noqa: E402
from scripts.llm.fake_server import FakeServer, fake  # noqa: E402

COURSE = "nptel_vr"
QWEN = "configs/qwen38_27b_vllm.json"
THRESHOLD = 0.6       # for the fake embedder's bag of words on the synthetic texts below
FAILURES: list[str] = []

# segment -> facts, concepts (name, aliases, fact numbers, defined), relationships (subject, label, object, facts)
DATA = {
    "1/S0": {"facts": ["A head-mounted display (HMD) is a display device worn on the head that places screens in "
                       "front of the eyes.",
                       "A head-mounted display (HMD) contains lenses that focus the screen images for the eyes.",
                       "The field of view is the angular extent of the visible scene, measured in degrees, that a "
                       "viewer sees at once.",
                       "Display resolution is the number of pixels per degree that a screen shows to the eye."],
             "concepts": [("Head-mounted display", ["HMD"], [0, 1], True), ("lens", [], [1], False),
                          ("field of view", ["FOV"], [2], True), ("display resolution", [], [3], True)],
             "relations": [(0, "contains", 1, [1]), (0, "has", 2, [0, 2])]},
    "1/S1": {"facts": ["AR overlays virtual objects on the real world seen through glasses.",
                       "Frame rate is the number of images a display renders each second.",
                       "Virtual reality (VR) replaces the real world with a computer generated world."],
             "concepts": [("AR", [], [0], True), ("frame rate", [], [1], True),
                          ("virtual reality", ["VR"], [2], True)],
             "relations": [(0, "is contrasted with", 2, [0, 2])]},
    "4/S0": {"facts": ["An HMD tracks the rotation of the head to update the view.",
                       "Head tracking measures the orientation of the head many times per second."],
             "concepts": [("HMD", [], [0], False), ("head tracking", [], [0, 1], True)],
             "relations": [(0, "uses", 1, [0])]},
    "4/S1": {"facts": ["Head mounted displays block the view of the real world in virtual reality (VR).",
                       "The HMD weight causes neck strain in long sessions.",
                       "Fresnel lenses are thin lenses used in head mounted displays."],
             "concepts": [("head mounted displays", ["headset"], [0], True), ("HMD", [], [1], False),
                          ("virtual reality", ["VR"], [0], False), ("lenses", [], [2], False)],
             "relations": [(1, "is short for", 0, [1]), (0, "contain", 3, [2]), (0, "is used in", 2, [0])]},
    "16/S0": {"facts": ["A Head-Mounted Display contains lenses and two screens.",
                        "The visual field extent is the angular extent of the visible scene, measured in degrees, "
                        "that a viewer sees at once through the headset optics."],
              "concepts": [("Head-Mounted Display", [], [0], False), ("Lenses", [], [0], False),
                           ("visual field extent", [], [1], True)],
              "relations": [(0, "Contains", 1, [0]), (2, "is limited by", 0, [1])]},
    "16/S1": {"facts": ["AR is the ratio of the width of a display image to its height.",
                        "Tracking resolution is the smallest head movement that the tracker can detect.",
                        "Refresh rate is the number of images a display shows each second."],
              "concepts": [("AR", [], [0], True), ("tracking resolution", [], [1], True),
                           ("refresh rate", [], [2], True), ("tracker", [], [1], False)],
              "relations": [(1, "is a property of", 3, [1])]},
}
KEYS = ["1", "4", "16"]


def truth(name: str, facts: str) -> str:
    """The seeded truth: which concept an entry is (what a careful model would read from its names and facts)."""
    n = name.lower()
    if n in ("head-mounted display", "hmd"):
        return "hmd"
    if n in ("field of view", "visual field extent"):
        return "fov"
    if n == "ar":
        return "ar ratio" if "ratio" in facts else "ar augmented"
    return n


class GroupingFake(FakeServer):
    """Answers a concept_same prompt with the TRUTH grouping; anything else as the plain fake."""

    def answer(self, body: dict) -> dict:
        prompt = body["messages"][0]["content"]
        fmt = (body.get("response_format") or {}).get("json_schema", {})
        if "THE ENTRIES" not in prompt or "refresh rate" in prompt:
            return super().answer(body)
        with self.lock:
            self.requests += 1
            with open(self.log, "a") as f:
                f.write(json.dumps({"messages": body["messages"], "schema": fmt.get("schema")}) + "\n")
        part = prompt.split("THE ENTRIES", 1)[1].split("\nANSWER\n", 1)[0]
        blocks = re.split(r"\n(?=\[\d+\] )", part)
        groups: dict[str, list] = {}
        for b in blocks:
            m = re.match(r"\[(\d+)\] (.*)", b)
            if m:
                groups.setdefault(truth(m[2], b), []).append((int(m[1]), m[2]))
        answer = {"groups": [{"entries": [k for k, _ in g], "reason": f"fake: both are {label}",
                              "name": g[0][1]} for label, g in groups.items()]}
        return {"choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(prompt) // 4, "completion_tokens": 50}}


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()} if folder.exists() else {}


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in (8094, 8095):
            return port


def make_copy(work: Path, port: int) -> Path:
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("scripts", "prompts", "configs"):
        shutil.copytree(ROOT / d, work / d, ignore=ign)
    meta = work / "input" / COURSE / "input"
    meta.mkdir(parents=True)
    for f in ("course.json", "titles.tsv"):
        shutil.copy(ROOT / "input" / COURSE / "input" / f, meta / f)
    cfg = LLMConfig.load(ROOT / QWEN).with_(port=port, model_path="fake/qwen", attach_wait_s=0, launch=False,
                                            retries=1)
    cfg.save(work / "configs" / "fake_qwen.json")
    out = work / "output" / COURSE
    for sub in ("stage_2c_concepts/concept_maps", "stage_2c_concepts/relations", "stage_2b_verify_facts/fact_maps"):
        (out / sub).mkdir(parents=True)
    for k in KEYS:
        cmap, rmap, fmap = {}, {}, {}
        for sid, seg in DATA.items():
            if not sid.startswith(k + "/"):
                continue
            for j, t in enumerate(seg["facts"]):
                fmap[f"{sid}/F{j}"] = {"text": t, "evidence": [f"{k}/{j}"]}
            for j, (name, aliases, facts, defined) in enumerate(seg["concepts"]):
                cmap[f"{sid}/C{j}"] = {"name": name, "aliases": aliases, "facts": [f"{sid}/F{i}" for i in facts],
                                       "defined": defined}
            for j, (s, label, o, facts) in enumerate(seg["relations"]):
                rmap[f"{sid}/R{j}"] = {"subject": f"{sid}/C{s}", "label": label, "object": f"{sid}/C{o}",
                                       "facts": [f"{sid}/F{i}" for i in facts]}
        stem = f"lec_{k}.json"
        (out / "stage_2c_concepts/concept_maps" / stem).write_text(json.dumps(cmap, indent=1))
        (out / "stage_2c_concepts/relations" / stem).write_text(json.dumps(rmap, indent=1))
        (out / "stage_2b_verify_facts/fact_maps" / stem).write_text(json.dumps(fmap, indent=1))
    return out / "stage_3_registry"


def stage(work: Path, script: str, args: list[str], log: str) -> int:
    with (work / log).open("w") as f:
        return subprocess.run([sys.executable, "-u", f"scripts/{script}", COURSE, *args], cwd=work, stdout=f,
                              stderr=subprocess.STDOUT).returncode


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def files_of(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*")
            if p.is_file() and p.name != "calls.jsonl"}


# ---------------------------------------------------------------- tests
def test_embed(work: Path):
    print("embed (fake model)", flush=True)
    cache = work / "embed_test.jsonl"
    e1 = Embedder("fake", cache=cache)
    v = e1.embed(["head mounted display", "lens", "head mounted display"])
    check(all(abs(sum(x * x for x in u) - 1) < 1e-6 for u in v) and v[0] == v[2] and v[0] != v[1]
          and e1.computed == 2, "unit vectors, the same text gives the same vector, each text embedded once")
    e2 = Embedder("fake", cache=cache)
    check(e2.embed(["lens", "head mounted display"]) == [v[1], v[0]] and e2.computed == 0,
          "a new embedder answers from the cache with the same numbers, embedding nothing")
    check(Embedder("Qwen/Qwen3-Embedding-0.6B").prefix("Find X") == "Instruct: Find X\nQuery:"
          and Embedder("sentence-transformers/all-mpnet-base-v2").prefix("Find X") == ""
          and Embedder("fake").prefix(None) == "", "instruction format for Qwen3-Embedding; none for the others")


def test_units():
    print("units", flush=True)
    same = [("Head-mounted display", "head mounted displays"), ("lens", "Lenses"), ("degree of freedom",
            "degrees of freedom"), ("head set", "headsets"), ("frequency", "frequencies"), ("Fitts's law", "Fitts law")]
    diff = [("display", "head-mounted display"), ("display", "displayed"), ("display resolution",
            "tracking resolution"), ("tracker", "tracking")]
    check(all(s3a.same_term(a, b) for a, b in same) and not any(s3a.same_term(a, b) for a, b in diff),
          "same term: case, hyphen, plural, space variants match; part words and other words do not")
    check([s3a.is_acronym(x) for x in ("HMD", "FoV", "3D", "Head-mounted display", "lens", "Unity")]
          == [True, True, True, False, False, False], "acronyms recognised")
    chain = [(0.9, 0, 1), (0.8, 1, 2), (0.5, 2, 3), (0.7, 3, 4), (0.95, 5, 6)]
    cl, cut = s3a.make_clusters(7, chain, 3)
    check(cl == [[0, 1, 2], [3, 4], [5, 6]] and cut == [2], "the cap splits a chain at its weakest link")
    cl, cut = s3a.make_clusters(7, chain, 10)
    check(cl == [[0, 1, 2, 3, 4], [5, 6]] and cut == [], "below the cap, clusters are the connected candidates")
    ents = [{"names": ["head-mounted display", "HMD"]}, {"names": ["HMD"]}, {"names": ["lens"]}]
    ok = {"groups": [{"entries": [1, 2], "reason": "r", "name": "HMD"}, {"entries": [3], "reason": "r", "name": "lens"}]}
    bad = [{"groups": [{"entries": [1, 2], "reason": "r", "name": "HMD"}]},
           {"groups": [{"entries": [1, 2], "reason": "r", "name": "HMD"}, {"entries": [2, 3], "reason": "r",
                                                                            "name": "lens"}]},
           {"groups": [{"entries": [1, 2, 3, 4], "reason": "r", "name": "HMD"}]},
           {"groups": [{"entries": [1, 2], "reason": "r", "name": "lens"}, {"entries": [3], "reason": "r",
                                                                             "name": "lens"}]}]
    check(s3b.problems(ok, ents) == [] and all(s3b.problems(b, ents) for b in bad),
          "the answer check: a missing, repeated or out-of-range entry, or another entry's name, is a problem")
    facts = {f"9/S0/F{i}": f"fact {i}" for i in range(12)}
    entry = {"name": "x", "names": ["x"], "lectures": ["9"], "facts": list(facts),
             "defining_facts": ["9/S0/F10", "9/S0/F11"]}
    block = s3b.entry_block(1, entry, facts).splitlines()
    shown = [x for x in block if x[:2] in ("* ", "- ")]
    check(len(shown) == s3b.FACT_CAP and shown[:2] == ["* fact 10", "* fact 11"] and shown[2] == "- fact 0"
          and block[-1] == f"({12 - s3b.FACT_CAP} more facts not shown)", "prompt entry: defining facts first, capped")


def test_3a(work: Path, od: Path) -> dict:
    print("3a (fake embedder)", flush=True)
    rc = stage(work, "s3a_candidates.py", ["--embed-model", "fake", "--threshold", str(THRESHOLD)], "3a.log")
    check(rc == 0, "3a exits cleanly")
    data = json.loads((od / "clusters.json").read_text())
    E = data["entries"]
    entry_of = {m: eid for eid, e in E.items() for m in e["members"]}
    cluster_of = {e: kid for kid, k in data["clusters"].items() for e in k["entries"]}
    check(len({entry_of[x] for x in ("1/S0/C0", "4/S1/C0", "16/S0/C0")}) == 1
          and len({entry_of[x] for x in ("1/S0/C1", "4/S1/C3", "16/S0/C1")}) == 1
          and entry_of["1/S1/C2"] == entry_of["4/S1/C2"], "exact merges: case, hyphen, plural")
    check(entry_of["4/S0/C0"] != entry_of["4/S1/C1"] and entry_of["1/S1/C0"] != entry_of["16/S1/C0"],
          "an acronym alone (HMD, AR) is not an exact merge")
    hmd = {cluster_of.get(entry_of[x]) for x in ("1/S0/C0", "4/S0/C0", "4/S1/C1")}
    check(len(hmd) == 1 and None not in hmd, "the HMD entries reach the head-mounted display's cluster (shared name)")
    check(cluster_of.get(entry_of["1/S1/C0"]) is not None
          and cluster_of.get(entry_of["1/S1/C0"]) == cluster_of.get(entry_of["16/S1/C0"]),
          "the two AR entries (a trap) reach one cluster")
    fov = (entry_of["1/S0/C2"], entry_of["16/S0/C2"])
    pair = next((c for c in data["candidates"] if (c["a"], c["b"]) == fov), None)
    check(pair is not None and not pair["alias"] and cluster_of.get(fov[0]) == cluster_of.get(fov[1]) is not None,
          f"the seeded split (field of view / visual field extent) reaches one cluster by similarity "
          f"({pair['sim'] if pair else 'no pair'})")
    check(all(len(set(e["members"])) == len(e["members"]) for e in E.values())
          and sorted(entry_of) == sorted(m for sid, s in DATA.items() for m in
                                         (f"{sid}/C{j}" for j in range(len(s["concepts"])))),
          "every segment concept in exactly one entry")
    rc = stage(work, "s3a_candidates.py", ["--embed-model", "fake", "--threshold", str(THRESHOLD), "--cap", "2",
                                           "--out", str(work / "capped")], "3a_cap.log")
    capped = json.loads((work / "capped" / "clusters.json").read_text())
    check(rc == 0 and all(len(k["entries"]) <= 2 for k in capped["clusters"].values()) and capped["cut"]
          and all(cluster_of_k(capped, c["a"]) != cluster_of_k(capped, c["b"]) for c in capped["cut"]),
          f"--cap 2: no cluster over the cap, the cut pairs listed ({len(capped['cut'])}) and really apart")
    return data


def cluster_of_k(data: dict, eid: str):
    return next((kid for kid, k in data["clusters"].items() if eid in k["entries"]), eid)


def test_3b(work: Path, od: Path, data: dict, log: Path, port: int):
    print(f"3b (fake model on port {port})", flush=True)
    server = GroupingFake(port, LLMConfig.load(ROOT / QWEN).model, str(log)).start()
    rc = stage(work, "s3b_same.py", ["--llm", "configs/fake_qwen.json"], "3b.log")
    server.stop()
    check(rc == 0, "3b exits cleanly")
    sent = lines(log)
    E = data["entries"]
    n_refresh = sum(1 for r in sent if "refresh rate" in r["messages"][0]["content"])
    n_clusters = len(data["clusters"])
    check(len({r["messages"][0]["content"] for r in sent}) == n_clusters,
          f"one prompt per cluster ({len({r['messages'][0]['content'] for r in sent})} for {n_clusters})")
    by_prompt = {}
    for r in sent:
        by_prompt.setdefault(r["messages"][0]["content"], r)
    ok_prompt = ok_enum = True
    for kid, k in data["clusters"].items():
        es = [E[e] for e in k["entries"]]
        r = next((r for p, r in by_prompt.items() if all(f"] {e['name']}\n" in p for e in es)
                  and len(re.findall(r"^\[\d+\] ", p.split("THE ENTRIES", 1)[1], re.M)) == len(es)), None)
        if r is None:
            ok_prompt = False
            continue
        p = r["messages"][0]["content"]
        ok_prompt &= all(f"[{i}] {e['name']}\n" in p for i, e in enumerate(es, 1)) and "{entries}" not in p \
            and "{course}" not in p
        ok_enum &= r["schema"]["properties"]["groups"]["items"]["properties"]["name"]["enum"] \
            == list(dict.fromkeys(n for e in es for n in e["names"]))
    check(ok_prompt, "each cluster's prompt lists exactly its entries, numbered [1]..[n] in course order")
    check(ok_enum, "the name enum is the cluster's names")
    new = json.loads((od / "clusters.json").read_text())
    bad = [kid for kid, k in new["clusters"].items() if any("refresh rate" == E[e]["name"] for e in k["entries"])]
    check(bad and n_refresh == 2 and all(not new["clusters"][b]["ok"] and new["clusters"][b]["errors"]
                                         and all(len(g["entries"]) == 1 for g in new["clusters"][b]["groups"])
                                         for b in bad),
          f"an invalid answer is retried ({n_refresh} attempts) and its cluster kept apart")
    check(all(sorted(e for g in k["groups"] for e in g["entries"]) == sorted(k["entries"])
              for k in new["clusters"].values()), "every entry of every cluster in exactly one group")


def test_3c(work: Path, od: Path):
    print("3c", flush=True)
    check(stage(work, "s3c_registry.py", [], "3c.log") == 0, "3c exits cleanly")
    C = json.loads((od / "concepts.json").read_text())
    S = json.loads((od / "segment_concepts.json").read_text())
    R = json.loads((od / "relations.json").read_text())
    D = lines(od / "decisions.jsonl")
    sc = {f"{sid}/C{j}": {"name": c[0], "aliases": c[1], "facts": [f"{sid}/F{i}" for i in c[2]], "defined": c[3]}
          for sid, s in DATA.items() for j, c in enumerate(s["concepts"])}
    rel = {f"{sid}/R{j}": {"subject": f"{sid}/C{r[0]}", "label": r[1], "object": f"{sid}/C{r[2]}",
                           "facts": [f"{sid}/F{i}" for i in r[3]]} for sid, s in DATA.items()
           for j, r in enumerate(s["relations"])}
    check(sorted(S) == sorted(sc) and all(S[m] in C for m in S), "every segment concept maps to an existing concept")
    check(all(sorted(m["segment_concept"] for m in c["merged"]) == sorted(m for m in S if S[m] == cid)
              for cid, c in C.items()), "each concept's merged list is exactly the segment concepts mapped to it")
    firsts = [s3a.sc_order(c["merged"][0]["segment_concept"]) for c in C.values()]
    check(list(C) == [f"C{i:04d}" for i in range(1, len(C) + 1)] and firsts == sorted(firsts)
          and all([s3a.sc_order(m["segment_concept"]) for m in c["merged"]]
                  == sorted(s3a.sc_order(m["segment_concept"]) for m in c["merged"]) for c in C.values()),
          "concept IDs contiguous, in course order")
    ok = True
    for cid, c in C.items():
        ms = [m["segment_concept"] for m in c["merged"]]
        ok &= c["facts"] == sorted({f for m in ms for f in sc[m]["facts"]}, key=s3a.sc_order)
        ok &= c["segments"] == sorted({s3a.segment_of(m) for m in ms}, key=s3a.seg_order)
        ok &= c["lectures"] == sorted({m.split("/")[0] for m in ms}, key=int)
        ok &= c["defined_in"] == sorted({s3a.segment_of(m) for m in ms if sc[m]["defined"]}, key=s3a.seg_order)
        ok &= c["merged"][0]["how"] == "first" and all(m["how"] in ("exact", "model") for m in c["merged"][1:])
    check(ok, "facts, segments, lectures, defined_in are the unions of the merged segment concepts")
    hmd = C[S["1/S0/C0"]]
    check(len({S[x] for x in ("1/S0/C0", "4/S0/C0", "4/S1/C0", "4/S1/C1", "16/S0/C0")}) == 1
          and hmd["name"] == "Head-mounted display"
          and [a.lower() for a in hmd["aliases"]] == ["hmd", "head mounted displays", "headset"],
          "HMD merged by the model into the head-mounted display; losing names are aliases (case repeats dropped)")
    check(S["1/S0/C2"] == S["16/S0/C2"] and "visual field extent" in C[S["1/S0/C2"]]["aliases"],
          "the seeded split comes back together, the losing name an alias")
    check(S["1/S1/C0"] != S["16/S1/C0"] and S["1/S0/C3"] != S["16/S1/C1"] and S["1/S1/C1"] != S["16/S1/C2"],
          "traps stay apart (AR/AR, display/tracking resolution) and the unanswered cluster is kept apart")
    n_joined = sum(1 for c in C.values() for m in c["merged"] if m["how"] != "first")
    logged = [d for d in D if d["kind"] in ("exact", "model")]
    check(len(logged) == n_joined and all(d["reason"] for d in logged)
          and {d["segment_concept"] for d in logged} == {m["segment_concept"] for c in C.values()
                                                         for m in c["merged"] if m["how"] != "first"},
          f"every merge has a decisions line with a reason ({len(logged)})")
    check(any(d["kind"] == "no_answer" for d in D) and any(d["kind"] == "separate" for d in D),
          "clusters kept apart (no answer) and groups of one (model) are logged")
    check(all(r["subject"] in C and r["object"] in C and r["subject"] != r["object"] for r in R.values()),
          "every relationship joins two different existing concepts")
    from_ids = [x for r in R.values() for x in r["from"]]
    dropped = [d["relation"] for d in D if d["kind"] in ("self_loop", "missing_end")]
    check(sorted(from_ids + dropped) == sorted(rel) and len(from_ids) + len(dropped) == len(rel),
          f"segment relationships add up: {len(from_ids)} in relationships + {len(dropped)} dropped = {len(rel)}")
    check("4/S1/R0" in [d["relation"] for d in D if d["kind"] == "self_loop"] and "4/S1/R0" not in from_ids,
          "the seeded self-loop (HMD is short for head mounted displays) is dropped and logged")
    joined = next((r for r in R.values() if "1/S0/R0" in r["from"]), {})
    other = next((r for r in R.values() if "4/S1/R1" in r["from"]), {})
    check(joined.get("from") == ["1/S0/R0", "16/S0/R0"] and joined.get("facts") == ["1/S0/F1", "16/S0/F0"]
          and sum(d["kind"] == "joined" for d in D) == 1 and other.get("from") == ["4/S1/R1"]
          and (other.get("subject"), other.get("object")) == (joined.get("subject"), joined.get("object")),
          "identical triples joined with their facts (label case ignored); another wording ('contain') kept apart")
    ok = all(r["facts"] == sorted({f for x in r["from"] for f in rel[x]["facts"]}, key=s3a.sc_order)
             and r["segments"] == sorted({s3a.segment_of(x) for x in r["from"]}, key=s3a.seg_order)
             and all(S[rel[x]["subject"]] == r["subject"] and S[rel[x]["object"]] == r["object"] for x in r["from"])
             for r in R.values())
    firsts = [s3a.sc_order(r["from"][0]) for r in R.values()]
    check(ok and list(R) == [f"R{i:04d}" for i in range(1, len(R) + 1)] and firsts == sorted(firsts),
          "relationship ends renamed through the map, facts and segments joined, IDs in order of first appearance")


def test_rerun(work: Path, od: Path, log: Path):
    print("rerun (fake model stopped)", flush=True)
    before, n_sent = files_of(od), len(lines(log))
    rcs = [stage(work, "s3a_candidates.py", ["--embed-model", "fake", "--threshold", str(THRESHOLD)], "3a_re.log"),
           stage(work, "s3b_same.py", ["--llm", "configs/fake_qwen.json"], "3b_re.log"),
           stage(work, "s3c_registry.py", [], "3c_re.log")]
    check(rcs == [0, 0, 0] and len(lines(log)) == n_sent, f"the rerun calls no model (exit codes {rcs})")
    check("0 texts embedded" in (work / "3a_re.log").read_text(), "the rerun embeds nothing")
    after = files_of(od)
    diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    check(not diff, f"the rerun gives byte-identical outputs{(': ' + ', '.join(diff)) if diff else ''}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", help="folder for the copy (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the copy afterwards")
    a = ap.parse_args()
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="fake_registry_"))
    work.mkdir(parents=True, exist_ok=True)
    before = snapshot(ROOT / "output")
    port = free_port()
    od = make_copy(work, port)
    print(f"copy in {work}", flush=True)
    log = work / "fake_qwen.jsonl"
    test_embed(work)
    test_units()
    data = test_3a(work, od)
    test_3b(work, od, data, log, port)
    test_3c(work, od)
    test_rerun(work, od, log)
    print("output", flush=True)
    check(snapshot(ROOT / "output") == before, "nothing under the real output/ created or changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed"
          + (f"; copy kept in {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
