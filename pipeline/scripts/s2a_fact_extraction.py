"""Stage 2a: extract the facts of each segment with the LLM (prompt: prompts/fact_extraction.txt).

    python scripts/s2a_fact_extraction.py nptel_vr --llm configs/gemma4_12b_llamacpp.json [--only 1-5] [--sequential]

Reads   output/<course>/stage_1b_verify_segments/segment_maps/lec_<n>.json   (segment IDs and sub-goals)
        output/<course>/stage_1c_segment_texts/<stem>/S<k>.txt               ("[<key>/<i>] text" per sentence)
        input/<course>/input/course.json, titles.tsv                          (course title, course block, lecture title)
Prompt  prompts/fact_extraction.txt; {course_title}, {course} (the course block, scripts/course_meta.py, as in 1a),
        {lecture_title}, {subgoal}, {segment} (the segment's sentences numbered from [1])
Writes  output/<course>/stage_2a_fact_extraction/
          fact_maps/lec_<n>.json        {"1/S0/F0": {"text": "...", "evidence": ["1/3", "1/4"]}, ...}
          fact_text/lec_<n>.txt         one line per fact: "[1/S0/F0] text"
          checks/lec_<n>.json           per segment: coverage, exact repeats collapsed, flags per fact (fact_checks.py)
          llm/cache.jsonl, calls.jsonl  answer cache and one line per call

One request per segment. The model cites sentence numbers local to the segment ([1]..[n], fewer tokens than IDs);
code maps them back to sentence IDs. Fact IDs are "<segment ID>/F<j>", j from 0 in the model's order.
Code checks (scripts/fact_checks.py, no LLM): an exact repeat of an earlier fact is merged into it (its ID is then
missing from the map, so the other IDs still give the fact's place in the model's answer); coverage and flags
(pointing words, acronyms the segment never uses, facts that share evidence or read alike) go to checks/.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, fact_checks, lectures as lec  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPT = ROOT / "prompts" / "fact_extraction.txt"
LINE = re.compile(r"\[(?P<id>[^\]]+)\] (?P<text>.*)")


def maps_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_1b_verify_segments" / "segment_maps"


def texts_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_1c_segment_texts"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_2a_fact_extraction"


def schema(n: int) -> dict:
    """The answer: facts, each with evidence (sentence numbers 1..n of the segment) and text."""
    return {"type": "object", "additionalProperties": False, "required": ["facts"],
            "properties": {"facts": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["evidence", "text"],
                "properties": {"evidence": {"type": "array", "minItems": 1,
                                            "items": {"type": "integer", "minimum": 1, "maximum": n}},
                               "text": {"type": "string"}}}}}}


def load_segment(course: str, seg_id: str) -> list[tuple[str, str]]:
    """The segment's (sentence ID, text) pairs, from its 1c text file."""
    key, s = seg_id.split("/")
    lines = (texts_dir(course) / lec.stem_of(key) / f"{s}.txt").read_text().splitlines()
    return [(m["id"], m["text"]) for m in map(LINE.fullmatch, lines)]


def build_prompt(course: str, key: str, subgoal: str, sentences: list[tuple[str, str]]) -> str:
    numbered = "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(sentences, 1))
    block, template = course_meta.course_prompt(course), PROMPT.read_text()
    if not block:                                      # no outline or syllabus: no course block
        template = template.replace("{course}\n", "")
    head, sep, tail = template.rpartition("### Your segment")   # fill only the input part, not the example
    tail = (tail.replace("{course_title}", course_meta.load(course)["title"])
            .replace("{course}", block)
            .replace("{lecture_title}", course_meta.lecture_title(course, key))
            .replace("{subgoal}", subgoal)
            .replace("{segment}", numbered))           # last, so text in the transcript is never replaced
    return head + sep + tail


def run(course: str, llm: LLM, lectures: list | None = None, parallel: bool = True) -> dict:
    """Extract the facts of every segment of the lectures (all with a segment map by default)."""
    keys = lec.normalize(lectures) or lec.keys(maps_dir(course))
    od = out_dir(course)
    for sub in ("fact_maps", "fact_text", "checks", "llm"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    segs = []                                          # (lecture key, segment ID, sub-goal, sentences)
    for key in keys:
        for seg_id, seg in json.loads((maps_dir(course) / f"{lec.stem_of(key)}.json").read_text()).items():
            segs.append((key, seg_id, seg["subgoal"], load_segment(course, seg_id)))
    reqs = [Request(prompt=build_prompt(course, key, sg, sents), key=seg_id, schema=schema(len(sents)),
                    meta={"lecture": key}) for key, seg_id, sg, sents in segs]
    t0 = time.time()
    print(f"2a: extracting facts from {len(reqs)} segments with {llm.model}", flush=True)
    results = llm.generate_many(reqs, parallel=parallel, cache_file=od / "llm" / "cache.jsonl",
                                log_file=od / "llm" / "calls.jsonl")
    facts: dict[str, dict] = {k: {} for k in keys}
    checks: dict[str, dict] = {k: {} for k in keys}
    no_answer = []
    for (key, seg_id, _, sents), res in zip(segs, results):
        if not res.ok:
            no_answer.append(seg_id)
            continue
        kept, dropped = fact_checks.collapse([{"evidence": sorted(set(f["evidence"])), "text": f["text"]}
                                              for f in res.parsed["facts"]])
        ids = [f"{seg_id}/F{f['index']}" for f in kept]     # the place in the model's answer, so repeats leave gaps
        for fid, f in zip(ids, kept):
            facts[key][fid] = {"text": f["text"], "evidence": [sents[i - 1][0] for i in f["evidence"]]}
        checks[key][seg_id] = fact_checks.report(kept, [t for _, t in sents], ids,
                                                 [[f"{seg_id}/F{a}", f"{seg_id}/F{b}"] for a, b in dropped])
    for key in keys:
        stem = lec.stem_of(key)
        (od / "fact_maps" / f"{stem}.json").write_text(json.dumps(facts[key], indent=1, ensure_ascii=False) + "\n")
        (od / "fact_text" / f"{stem}.txt").write_text("".join(f"[{i}] {f['text']}\n" for i, f in facts[key].items()))
        (od / "checks" / f"{stem}.json").write_text(json.dumps(checks[key], indent=1, ensure_ascii=False) + "\n")
    n_facts = sum(map(len, facts.values()))
    summary = {"lectures": len(keys), "segments": len(segs), "facts": n_facts, "no_answer": no_answer,
               **check_totals(checks), "wall_s": round(time.time() - t0, 1), "out": str(od)}
    print(f"{len(segs)} segments, {n_facts} facts, {summary['wall_s']} s"
          + (f"; no JSON answer: {no_answer}" if no_answer else ""))
    print(f"checks: coverage {summary['coverage']:.0%} of sentences, {summary['collapsed']} exact repeats collapsed, "
          f"flags {summary['flags'] or 'none'}")
    return summary


def check_totals(checks: dict[str, dict]) -> dict:
    """Totals over the per-segment check reports: overall coverage, repeats collapsed, flags by kind."""
    reports = [r for by_seg in checks.values() for r in by_seg.values()]
    sentences = sum(r["sentences"] for r in reports)
    flags: dict[str, int] = {}
    for r in reports:
        for kind, n in r["flag_counts"].items():
            flags[kind] = flags.get(kind, 0) + n
    return {"coverage": round(sum(r["coverage"] * r["sentences"] for r in reports) / sentences, 3) if sentences else 0.0,
            "collapsed": sum(len(r["collapsed"]) for r in reports), "flags": flags}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8,24b,tut_1")
    ap.add_argument("--sequential", action="store_true", help="one segment at a time instead of all at once")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, lec.parse_only(a.only) if a.only else None, parallel=not a.sequential)


if __name__ == "__main__":
    main()
