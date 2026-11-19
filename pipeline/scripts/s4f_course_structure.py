"""Stage 4f: the sentences in which the lecturer talks about the course itself (its structure and logistics).

    python scripts/s4f_course_structure.py nptel_vr --llm configs/gemma4_12b_llamacpp.json [--lectures 1,4] [--seed 1]
                                                    [--out DIR]

Reads   output/<course>/stage_1b_verify_segments/segment_maps/lec_<n>.json   (segment IDs, start, end)
        output/<course>/stage_1c_segment_texts/<stem>/S<k>.txt               ("[<id>] text" per sentence)
        output/<course>/stage_0a_preprocess/times/<stem>.json                 (sentence start/end seconds)
Prompt  prompts/course_structure.txt: {segment} (the segment's sentences, "[<sentence ID>] text")
Writes  output/<course>/stage_4f_course_structure/ (or --out)
          course_structure.json  {"run": {model, prompt hash, date, segments, calls, retries, ...},
                                  "statements": [{"id": "CS0001", "lecture", "segment", "sentence_ids", "start", "end",
                                                  "text"}]}
          course_structure.md    every statement (lecture, time, text), for review
          llm/cache.jsonl, calls.jsonl

One call per segment (parallel up to the config's slots). The model answers {"sentence_ids": [...]}, usually empty.
The text of a statement is copied verbatim from the transcript by code: consecutive chosen sentences of a segment
(neighbours in the segment) merge into one statement. Code check (a failing answer is retried with the problems shown
to the model, up to the config's retries): every ID is a sentence of this segment; no duplicates.
A segment whose attempts all fail the check gets no statement and is listed under run.failed.
Sentence times come from stage 0a; a boundary that is null there (inside a cue) falls back to the segment's own start
(first sentence) or end (last sentence).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import lectures as lec  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPT = ROOT / "prompts" / "course_structure.txt"
THINK_BUDGET = 1024
MAX_TOKENS = 4096
LINE = re.compile(r"\[(?P<id>[^\]]+)\] (?P<text>.*)")
SCHEMA = {"type": "object", "properties": {"sentence_ids": {"type": "array", "items": {"type": "string"}}},
          "required": ["sentence_ids"], "additionalProperties": False}


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_4f_course_structure"


def check_ids(answer, valid: list[str]) -> list[str]:
    """The problems of an answer ([] = fine)."""
    ids = answer.get("sentence_ids") if isinstance(answer, dict) else None
    if not isinstance(ids, list):
        return ["the answer has no sentence_ids list"]
    probs = []
    bad = [x for x in ids if x not in valid]
    if bad:
        probs.append("these IDs are not sentences of this text: " + ", ".join(map(str, bad))
                     + "; use only the IDs shown in brackets")
    dup = sorted({x for x in ids if ids.count(x) > 1}, key=str)
    if dup:
        probs.append("these IDs are listed more than once: " + ", ".join(map(str, dup)))
    return probs


def make_request(template: str, lecture: str, sid: str, sents: list[tuple[str, str]], sampling: dict) -> Request:
    prompt = template.format(segment="\n".join(f"[{i}] {t}" for i, t in sents))
    valid = [i for i, _ in sents]
    return Request(prompt=prompt, key=sid, schema=SCHEMA, feedback=True, sampling=sampling, max_tokens=MAX_TOKENS,
                   think_budget=THINK_BUDGET, meta={"lecture": lecture, "segment": sid},
                   check=lambda a: check_ids(a, valid))


def groups(ids: list[str], order: list[str]) -> list[list[str]]:
    """The chosen IDs in transcript order, split where they are not neighbours in the segment."""
    out: list[list[int]] = []
    for p in sorted(order.index(i) for i in ids):
        if out and p == out[-1][-1] + 1:
            out[-1].append(p)
        else:
            out.append([p])
    return [[order[p] for p in g] for g in out]


def run(course: str, llm: LLM, lectures: list | None = None, seed: int | None = None,
        out: Path | None = None) -> dict:
    base = ROOT / "output" / course
    maps = base / "stage_1b_verify_segments" / "segment_maps"
    keys = lec.normalize(lectures) or lec.keys(maps)
    od = Path(out) if out else out_dir(course)
    (od / "llm").mkdir(parents=True, exist_ok=True)
    cache, log = od / "llm" / "cache.jsonl", od / "llm" / "calls.jsonl"
    sampling = {} if seed is None else {"seed": seed}
    template = PROMPT.read_text(encoding="utf-8")
    t0 = time.time()
    items, texts, times = [], {}, {}
    for k in keys:
        segs = json.loads((maps / f"{lec.stem_of(k)}.json").read_text(encoding="utf-8"))
        times[k] = json.loads((base / "stage_0a_preprocess" / "times" / f"{lec.stem_of(k)}.json").read_text())
        for sid, seg in segs.items():
            f = base / "stage_1c_segment_texts" / lec.stem_of(k) / f"{sid.split('/')[1]}.txt"
            sents = [(m["id"], m["text"]) for m in map(LINE.fullmatch, f.read_text(encoding="utf-8").splitlines()) if m]
            texts[sid] = dict(sents)
            items.append((k, sid, seg, sents))
    print(f"4f: course structure over {len(items)} segments in {len(keys)} lectures with {llm.model}", flush=True)
    reqs = [make_request(template, k, sid, sents, sampling) for k, sid, seg, sents in items]
    results = llm.generate_many(reqs, cache_file=cache, log_file=log)
    statements, failed, calls, retries = [], [], 0, 0
    for (k, sid, seg, sents), res in zip(items, results):
        calls += res.attempts
        retries += res.attempts - 1
        if not res.ok:
            failed.append({"segment": sid, "problems": list(res.errors) or ["no answer"]})
            continue
        for g in groups(res.parsed["sentence_ids"], [i for i, _ in sents]):
            start = (times[k].get(g[0]) or {}).get("start")
            end = (times[k].get(g[-1]) or {}).get("end")
            statements.append({"id": "", "lecture": k, "segment": sid, "sentence_ids": g,
                               "start": seg["start"] if start is None else start,
                               "end": seg["end"] if end is None else end,
                               "text": " ".join(texts[sid][i] for i in g)})
    for n, s in enumerate(statements, 1):
        s["id"] = f"CS{n:04d}"
    run_info = {"stage": "4f_course_structure", "model": llm.model,
                "prompt_sha256": hashlib.sha256(template.encode()).hexdigest()[:16], "think_budget": THINK_BUDGET,
                "date": time.strftime("%Y-%m-%d"), "lectures": keys, "segments": len(items), "calls": calls,
                "retries": retries, "statements": len(statements), "failed": failed,
                "seconds": round(time.time() - t0, 1), "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
    (od / "course_structure.json").write_text(json.dumps({"run": run_info, "statements": statements}, indent=1,
                                                         ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# Course structure statements ({len(statements)})", ""]
    for k in keys:
        mine = [s for s in statements if s["lecture"] == k]
        if mine:
            lines.append(f"## Lecture {k}")
            lines += [f"- {s['id']}  {s['segment']}  {s['start']:.0f}-{s['end']:.0f} s: {s['text']}" for s in mine]
            lines.append("")
    (od / "course_structure.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"4f: {len(statements)} statements, {len(failed)} failed segments, {retries} retries, "
          f"{run_info['seconds']} s", flush=True)
    return run_info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--lectures", help="lectures, e.g. 1,4 (default: all)")
    ap.add_argument("--seed", type=int, help="sampling seed (default: the config's)")
    ap.add_argument("--out", help="output folder (default: output/<course>/stage_4f_course_structure)")
    a = ap.parse_args()
    cfg = LLMConfig.load(a.llm).with_(think_budget=THINK_BUDGET)
    with LLM(cfg) as llm:
        run(a.course, llm, lec.parse_only(a.lectures) if a.lectures else None, a.seed, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
