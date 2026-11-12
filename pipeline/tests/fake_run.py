"""Plumbing test of stages 2a, 2b and 2c with fake models, through the attach-only EC2 configs, on the local PC.

    python3 tests/fake_run.py [--lectures 1,4,16] [--work DIR] [--keep]

Runs in a copy of the pipeline folder (scripts, prompts, configs, the course's metadata, segment maps and texts) in a
new temporary folder, so nothing under output/ is written; the test checks that at the end. The fake servers
(scripts/llm/fake_server.py) listen on the configs' ports (8094 Qwen, 8095 Sage), where the SSH forward to the EC2
would be, so stop the forward first.

What it looks for (each line is what a broken stage would show):
  attach    a wrong model on the port is used (answers cached under the wrong hash); no server and no wait does not
            fail at once
  2a        a segment without its request or answer; facts lost or invented (the fake gives 2 per segment); evidence
            outside the segment; a rerun that calls the model again (the cache does not answer it)
  2b        the judge model does not do the judging, or the rewriter the rewrite; the rewrite phase does not wait for
            its server while the models are swapped; a judged fact with no verdict or no outcome; a failed fact kept;
            the rewrite conversation not rebuilt from 2a's cached answer; fact IDs not renumbered from F0;
            evidence outside the segment; outcome counts that do not add up (a fact dropped without a log line)
  2c        a segment with facts and no turn 1, or a turn 2 that does not continue turn 1's conversation; the triple
            schema not limited to the checked concept names; a concept citing a fact of another segment; a triple
            end that is not a concept of its segment; same-name concepts not merged; the word matching of the
            checks wrong (plural, hyphen, acronym in brackets); a segment without its check report; a rerun that
            calls the model again
  output    any file under the real output/ created or changed
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
sys.path.insert(0, str(ROOT))

from scripts import lectures as lec, s2c_concepts as s2c  # noqa: E402
from scripts.llm import LLM, LLMConfig  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402

COURSE = "nptel_vr"
QWEN, SAGE = "configs/qwen38_27b_vllm.json", "configs/sage_a15_vllm.json"
FAILURES: list[str] = []


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def make_copy(work: Path, keys: list[str]):
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("scripts", "prompts", "configs"):
        shutil.copytree(ROOT / d, work / d, ignore=ign)
    meta = work / "input" / COURSE / "input"
    meta.mkdir(parents=True)
    for f in ("course.json", "titles.tsv"):
        shutil.copy(ROOT / "input" / COURSE / "input" / f, meta / f)
    src, dst = ROOT / "output" / COURSE, work / "output" / COURSE
    (dst / "stage_1b_verify_segments" / "segment_maps").mkdir(parents=True)
    for k in keys:
        stem = lec.stem_of(k)
        shutil.copy(src / "stage_1b_verify_segments" / "segment_maps" / f"{stem}.json",
                    dst / "stage_1b_verify_segments" / "segment_maps" / f"{stem}.json")
        shutil.copytree(src / "stage_1c_segment_texts" / stem, dst / "stage_1c_segment_texts" / stem)


def stage(work: Path, script: str, args: list[str], log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-u", f"scripts/{script}", COURSE, *args], cwd=work,
                            stdout=log.open("w"), stderr=subprocess.STDOUT)


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def segments_of(work: Path, keys: list[str]) -> dict[str, list[str]]:
    """Segment ID -> its sentence IDs, from the copy's segment texts."""
    out = {}
    for k in keys:
        for f in sorted((work / "output" / COURSE / "stage_1c_segment_texts" / lec.stem_of(k)).glob("S*.txt")):
            out[f"{k}/{f.stem}"] = [x.split("]", 1)[0][1:] for x in f.read_text().splitlines()]
    return out


def evidence_ok(facts: dict, segs: dict) -> bool:
    return all(set(f["evidence"]) <= set(segs[fid.rsplit("/", 1)[0]]) and f["evidence"] for fid, f in facts.items())


def test_attach():
    print("attach", flush=True)
    cfg = LLMConfig.load(ROOT / QWEN)
    check(not cfg.launch, "the Qwen config attaches only")
    try:
        LLM(cfg.with_(attach_wait_s=0), log=lambda *_: None).start()
        check(False, "no server and no wait: start fails")
    except RuntimeError:
        check(True, "no server and no wait: start fails")
    wrong = FakeServer(cfg.port, "some-other-model").start()
    try:
        LLM(cfg, log=lambda *_: None).start()
        check(False, "a wrong model on the port is refused")
    except RuntimeError as e:
        check("another model" in str(e), "a wrong model on the port is refused")
    finally:
        wrong.stop()


def test_2a(work: Path, keys: list[str], qwen_log: Path) -> dict:
    print("2a (fake Qwen on 8094)", flush=True)
    qwen = FakeServer(8094, LLMConfig.load(ROOT / QWEN).model, str(qwen_log)).start()
    only = ",".join(keys)
    p = stage(work, "s2a_fact_extraction.py", ["--llm", QWEN, "--only", only], work / "2a.log")
    check(p.wait() == 0, "2a exits cleanly")
    segs = segments_of(work, keys)
    od = work / "output" / COURSE / "stage_2a_fact_extraction"
    facts = {}
    for k in keys:
        facts.update(json.loads((od / "fact_maps" / f"{lec.stem_of(k)}.json").read_text()))
    sent = lines(qwen_log)
    check(len(sent) == len(segs), f"one request per segment ({len(sent)} for {len(segs)})")
    check(len(facts) == 2 * len(segs), f"every fake fact kept ({len(facts)} for {2 * len(segs)})")
    check({fid.rsplit("/", 1)[0] for fid in facts} == set(segs), "every segment has facts")
    check(evidence_ok(facts, segs), "evidence within each fact's segment")
    p = stage(work, "s2a_fact_extraction.py", ["--llm", QWEN, "--only", only], work / "2a_rerun.log")
    check(p.wait() == 0 and len(lines(qwen_log)) == len(segs), "a rerun is answered from the cache")
    qwen.stop()
    return facts


def test_2b(work: Path, keys: list[str], facts_2a: dict, qwen_log: Path, sage_log: Path):
    print("2b (fake Sage judges on 8095, then the swap to fake Qwen for the rewrite)", flush=True)
    segs = segments_of(work, keys)
    sage = FakeServer(8095, LLMConfig.load(ROOT / SAGE).model, str(sage_log)).start()
    log = work / "2b.log"
    p = stage(work, "s2b_verify_facts.py", ["--llm", QWEN, "--judge", SAGE, "--only", ",".join(keys)], log)
    t0 = time.time()
    while len(lines(sage_log)) < len(segs) and p.poll() is None and time.time() - t0 < 120:
        time.sleep(0.5)
    sage.stop()                                       # the swap: the judge's server goes, the writer's comes later
    time.sleep(8)
    check(p.poll() is None and "waiting for" in log.read_text(), "the rewrite waits for its server during the swap")
    n_2a_calls = len(lines(qwen_log))
    qwen = FakeServer(8094, LLMConfig.load(ROOT / QWEN).model, str(qwen_log)).start()
    check(p.wait(timeout=300) == 0, "2b exits cleanly")
    qwen.stop()

    judged, rewrites = lines(sage_log), lines(qwen_log)[n_2a_calls:]
    check(len(judged) == len(segs), f"the judge model judged every segment ({len(judged)} of {len(segs)})")
    check(all(r["messages"][0]["role"] == "system" for r in judged), "judge requests carry the system message")
    od = work / "output" / COURSE / "stage_2b_verify_facts"
    recs = [r for k in keys for r in json.loads((od / "judgements" / f"{lec.stem_of(k)}.json").read_text())]
    final = {}
    for k in keys:
        final.update(json.loads((od / "fact_maps" / f"{lec.stem_of(k)}.json").read_text()))
    outcomes = {fid: o["result"] for r in recs for fid, o in r["outcome"].items()}
    check(set(outcomes) == set(facts_2a), "every 2a fact has an outcome")
    check(all(v is not None for r in recs for v in r["verdicts"]), "every 2a fact has a verdict")
    failed = {v["fact"] for r in recs for v in r["verdicts"] if not v["pass"]}
    check(failed and all(outcomes[f] != "kept" for f in failed), f"no failed fact kept ({len(failed)} failed)")
    check(len(rewrites) == sum(1 for r in recs if any(not v["pass"] for v in r["verdicts"])),
          f"one rewrite request per segment with a failed fact ({len(rewrites)})")
    cache = {}
    for rec in lines(work / "output" / COURSE / "stage_2a_fact_extraction" / "llm" / "cache.jsonl"):
        cache.setdefault(rec["key"], rec["content"])
    check(all(len(r["messages"]) == 3 and r["messages"][1]["role"] == "assistant"
              and r["messages"][1]["content"] == cache[_seg_of(r)]
              for r in rewrites), "each rewrite continues 2a's conversation with 2a's cached answer")
    n_kept = sum(o == "kept" for o in outcomes.values())
    n_new = sum(len(o.get("as", [])) for r in recs for o in r["outcome"].values())
    n_collapsed = sum(len(r["collapsed"]) for r in recs)   # exact repeats merged, each with a log entry
    check(len(final) == n_kept + n_new - n_collapsed,
          f"final facts = kept + rewrites - logged repeats ({len(final)} = {n_kept} + {n_new} - {n_collapsed})")
    by_seg = {}
    for fid in final:
        by_seg.setdefault(fid.rsplit("/", 1)[0], []).append(int(fid.rsplit("/F", 1)[1]))
    check(all(sorted(v) == list(range(len(v))) for v in by_seg.values()), "final facts renumbered from F0")
    check(evidence_ok(final, segs), "evidence within each final fact's segment")


def test_2c(work: Path, keys: list[str], qwen_log: Path):
    print("2c (fake Qwen on 8094)", flush=True)
    merged, fl = s2c.check_concepts([{"name": "Head-mounted display", "aliases": ["HMD"], "facts": [1], "defined": False},
                                     {"name": "head-mounted  display", "aliases": ["headset"], "facts": [2, 9],
                                      "defined": True}], 3)
    check(len(merged) == 1 and merged[0]["aliases"] == ["HMD", "headset"] and merged[0]["facts"] == [1, 2]
          and merged[0]["defined"] and fl["merged"] and fl["out_of_range"], "same names merged, numbers out of range dropped")
    check(s2c.appears("head-mounted display", "Head mounted displays block vision.")
          and s2c.appears("XR", "Extended reality (XR) is ...") and not s2c.appears("AR", "Art is not a term.")
          and not s2c.appears("display", "displayed"), "word matching: plural, hyphen, acronym, no part words")
    flags = s2c.check_all([{"name": "a", "aliases": [], "facts": [1], "defined": True},
                           {"name": "b", "aliases": ["B1"], "facts": [2], "defined": False},
                           {"name": "c", "aliases": [], "facts": [1], "defined": False}],
                          [{"facts": [1], "subject": "a", "label": "is related to", "object": "b"},
                           {"facts": [1], "subject": "b", "label": "contains", "object": "a"}],
                          ["a and c", "b", "nothing"], {"out_of_range": [], "merged": []})
    check(flags["no_shared_fact"] == [0, 1] and flags["reverse"] == [0, 1] and flags["vague_label"] == [0]
          and flags["no_triple"] == ["c"] and flags["fact_without_concept"] == [3]
          and flags["alias_not_written"] == [{"concept": "b", "alias": "B1"}], "each code check fires on its case")
    n_before = len(lines(qwen_log))
    qwen = FakeServer(8094, LLMConfig.load(ROOT / QWEN).model, str(qwen_log)).start()
    p = stage(work, "s2c_concepts.py", ["--llm", QWEN, "--only", ",".join(keys)], work / "2c.log")
    check(p.wait() == 0, "2c exits cleanly")
    sent = lines(qwen_log)[n_before:]
    od2b = work / "output" / COURSE / "stage_2b_verify_facts" / "fact_maps"
    facts = {}
    for k in keys:
        facts.update(json.loads((od2b / f"{lec.stem_of(k)}.json").read_text()))
    with_facts = sorted({fid.rsplit("/", 1)[0] for fid in facts})
    first = [r for r in sent if len(r["messages"]) == 1]
    second = [r for r in sent if len(r["messages"]) == 3]
    check(len(first) == len(with_facts) and len(second) == len(with_facts),
          f"turn 1 and turn 2 for each segment with facts ({len(first)}, {len(second)} for {len(with_facts)})")
    by_prompt = {r["messages"][0]["content"]: r for r in first}
    ok_conv = all(r["messages"][0]["content"] in by_prompt and r["messages"][1]["role"] == "assistant" for r in second)
    check(ok_conv, "turn 2 continues turn 1's conversation")
    od = work / "output" / COURSE / "stage_2c_concepts"
    cmap, rmap, checks = {}, {}, {}
    for k in keys:
        stem = lec.stem_of(k)
        cmap.update(json.loads((od / "concept_maps" / f"{stem}.json").read_text()))
        rmap.update(json.loads((od / "relations" / f"{stem}.json").read_text()))
        checks.update(json.loads((od / "checks" / f"{stem}.json").read_text()))
    names_by_seg = {}
    for cid, c in cmap.items():
        names_by_seg.setdefault(cid.rsplit("/", 1)[0], []).append(c["name"])
    check(all(r["schema"]["properties"]["relations"]["items"]["properties"]["subject"]["enum"]
              == names_by_seg[_seg2c(r)] for r in second), "the triple schema allows only the segment's concept names")
    check(all(f in facts and f.rsplit("/", 1)[0] == cid.rsplit("/", 1)[0] for cid, c in cmap.items() for f in c["facts"]),
          "every concept cites verified facts of its own segment")
    check(all(r[e] in cmap and r[e].rsplit("/", 1)[0] == rid.rsplit("/", 1)[0] for rid, r in rmap.items()
              for e in ("subject", "object")), "every triple joins concepts of its own segment")
    check(set(checks) == set(with_facts), "a check report for each segment with facts")
    p = stage(work, "s2c_concepts.py", ["--llm", QWEN, "--only", ",".join(keys)], work / "2c_rerun.log")
    check(p.wait() == 0 and len(lines(qwen_log)) == n_before + len(sent), "a rerun is answered from the cache")
    qwen.stop()


def _seg2c(turn2: dict) -> str:
    """The segment of a 2c turn-2 request: the fact IDs are not in the prompt, so match its lecture and goal."""
    prompt = turn2["messages"][0]["content"]
    tail = prompt[prompt.rindex("### Your segment"):]
    for k in tail.split("SEGMENT GOAL: ", 1)[1:]:
        goal = k.split("\n", 1)[0]
        for seg in _SEGS:
            if seg["subgoal"] == goal and f"LECTURE: {seg['title']}" in tail:
                return seg["id"]
    raise KeyError("segment not found")


_SEGS: list[dict] = []


def _seg_of(rewrite_request: dict) -> str:
    """The segment ID a rewrite request is for: the failed fact IDs in its last message start with it."""
    text = rewrite_request["messages"][2]["content"]
    fid = text[text.index("[") + 1:text.index("]")]
    return fid.rsplit("/", 1)[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lectures", default="1,4,16")
    ap.add_argument("--work", help="folder for the copy (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the copy afterwards")
    a = ap.parse_args()
    keys = lec.parse_only(a.lectures)
    busy = [p for p in (8094, 8095) if not port_free(p)]
    if busy:
        sys.exit(f"ports {busy} are in use (an SSH forward to the EC2?): stop it first")
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="fake_run_"))
    work.mkdir(parents=True, exist_ok=True)
    before = snapshot(ROOT / "output")
    make_copy(work, keys)
    print(f"copy in {work}", flush=True)
    test_attach()
    qwen_log, sage_log = work / "fake_qwen.jsonl", work / "fake_sage.jsonl"
    facts = test_2a(work, keys, qwen_log)
    test_2b(work, keys, facts, qwen_log, sage_log)
    from scripts import course_meta
    for k in keys:
        maps = json.loads((ROOT / "output" / COURSE / "stage_1b_verify_segments" / "segment_maps"
                           / f"{lec.stem_of(k)}.json").read_text())
        _SEGS.extend({"id": sid, "subgoal": m["subgoal"], "title": course_meta.lecture_title(COURSE, k)}
                     for sid, m in maps.items())
    test_2c(work, keys, qwen_log)
    print("output", flush=True)
    check(snapshot(ROOT / "output") == before, "nothing under the real output/ created or changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed" + (f"; copy kept in {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
