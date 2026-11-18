"""Stage 4e: a short title (3 to 6 words) for each part (segment) of each lecture.

    python scripts/s4e_part_titles.py nptel_vr --llm configs/gemma4_12b_llamacpp.json [--lectures 1,4] [--seed 1]
                                                [--out DIR]

Reads   output/<course>/knowledge/lectures/lec_<n>.json   (title; segments: "subgoal", "facts", "start", "end")
        output/<course>/knowledge/facts.json              (fact texts)
Prompt  prompts/part_title.txt: {lecture_title}, {goal} (the segment's sub-goal), {facts}, {taken}
Writes  output/<course>/stage_4e_part_titles/ (or --out)
          titles.json   {"run": {model, prompt hash, time, counts...},
                         "segments": {"1/S0": {"title": "..." | null, "ok": true|false, "problems": [..]}, ...}}
                        A segment whose attempts all fail the code check has title null, ok false and the problems of
                        its best attempt; nothing fills it in afterwards.
          titles.txt    readable: lecture, segment, time range, title, goal
          llm/cache.jsonl, calls.jsonl

One call per segment (parallel up to the config's slots), input = the lecture title, the segment's goal and its facts.
Thinking stays on with a small budget (1024 tokens; the script overrides the config's budget, so a server it starts
is launched with it). Code check (a failing answer is retried with the problems shown to the model, up to the
config's retries): 3 to 6 words; no punctuation at the end; no quotes, brackets, colon, IDs or digits; Title Case;
no filler at the start; not the first 4 words of the goal copied; not equal to another title of the same lecture
(case aside); at least one content word that appears in the facts or the goal.
Parallel calls cannot see each other, so after the first pass a title repeated inside a lecture is asked again for
the later part, with the lecture's other titles listed as taken (up to 3 rounds).
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

PROMPT = ROOT / "prompts" / "part_title.txt"
THINK_BUDGET = 1024
MAX_TOKENS = 4096
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"],
          "additionalProperties": False}
SMALL = {"a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
         "vs", "via", "is", "per", "into", "over", "its", "not", "nor"}
FILLER = ("lecture", "part", "introduction to", "intro to", "overview of", "understanding", "basics of")
STOP = SMALL | {"how", "what", "why", "this", "that", "are", "be", "it", "their", "these", "those", "can", "using"}
ID = re.compile(r"\d+/S?\d*|\bS\d+\b|\bF\d+\b")


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_4e_part_titles"


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text)


def stem(w: str) -> str:
    w = w.lower()
    for suf in ("ing", "ies", "es", "s", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def check_title(title: str, goal: str, facts: str, others: set[str]) -> list[str]:
    """The problems of a title ([] = fine). others: lower-cased titles already taken in the lecture."""
    t, probs = title.strip(), []
    w = words(t)
    if not 3 <= len(w) <= 6:
        probs.append(f"the title has {len(w)} words; it must have 3 to 6")
    if re.search(r"[.!?,;:\-]$", t):
        probs.append("the title ends with punctuation; end it with a word")
    if re.search(r"[\"“”‘’`()\[\]{}:]", t) or t[:1] == "'" or t[-1:] == "'":
        probs.append("the title has quotes, brackets or a colon; use plain words only")
    if ID.search(t) or re.search(r"\d", t):
        probs.append("the title has an ID or a number; use words only")
    bad = [x for x in w if x.lower() not in SMALL and not (x[0].isupper() or x[0].isdigit())]
    if bad:
        probs.append("the title is not in Title Case (capitalise " + ", ".join(bad) + ")")
    low = t.lower()
    for f in FILLER:
        if low == f or low.startswith(f + " "):
            probs.append(f'the title starts with the filler "{f}"; name the subject directly')
    gw = [x.lower() for x in words(goal)]
    if len(w) >= 4 and [x.lower() for x in w[:4]] == gw[:4]:
        probs.append("the title copies the start of the goal; word it as a noun phrase")
    if low in others:
        probs.append("another part of this lecture already has this title; name what is different about this part")
    pool = {stem(x) for x in words(goal + " " + facts)}
    if w and not any(stem(x) in pool for x in w if x.lower() not in STOP):
        probs.append("no word of the title appears in the goal or the facts; use words from the course content")
    return probs


def make_request(template: str, lecture: str, title: str, sid: str, seg: dict, facts: dict, taken: set[str],
                 sampling: dict, key: str) -> Request:
    ftxt = "\n".join(f"- {facts[f]['text']}" for f in seg["facts"])
    note = ("\nThese titles are already used by other parts of this lecture: " + "; ".join(sorted(taken))
            + ". Your title must differ from all of them.\n") if taken else ""
    prompt = template.format(lecture_title=title, goal=seg["subgoal"], facts=ftxt, taken=note)
    lowtaken = {x.lower() for x in taken}
    return Request(prompt=prompt, key=key, schema=SCHEMA, feedback=True, sampling=sampling, max_tokens=MAX_TOKENS,
                   think_budget=THINK_BUDGET, meta={"lecture": lecture, "segment": sid},
                   check=lambda a: check_title(a.get("title", "") if isinstance(a, dict) else "",
                                               seg["subgoal"], ftxt, lowtaken))


def outcome(res) -> dict:
    t = res.parsed.get("title", "").strip() if isinstance(res.parsed, dict) else ""
    if res.ok and t:
        return {"title": t, "ok": True, "problems": []}
    return {"title": None, "ok": False, "problems": list(res.errors) or ["no answer"]}


def run(course: str, llm: LLM, lectures: list | None = None, seed: int | None = None,
        out: Path | None = None) -> dict:
    base = ROOT / "output" / course / "knowledge"
    keys = lec.normalize(lectures) or lec.keys(base / "lectures")
    od = Path(out) if out else out_dir(course)
    (od / "llm").mkdir(parents=True, exist_ok=True)
    cache, log = od / "llm" / "cache.jsonl", od / "llm" / "calls.jsonl"
    sampling = {} if seed is None else {"seed": seed}
    template = PROMPT.read_text(encoding="utf-8")
    facts = json.loads((base / "facts.json").read_text(encoding="utf-8"))
    lects = {k: json.loads((base / "lectures" / f"{lec.stem_of(k)}.json").read_text(encoding="utf-8")) for k in keys}
    t0 = time.time()
    items = [(k, sid, seg) for k in keys for sid, seg in lects[k]["segments"].items()]
    print(f"4e: titles of {len(items)} parts in {len(keys)} lectures with {llm.model}", flush=True)
    reqs = [make_request(template, k, lects[k]["title"], sid, seg, facts, set(), sampling, sid) for k, sid, seg in items]
    segments, retried = {}, 0
    for (k, sid, seg), res in zip(items, llm.generate_many(reqs, cache_file=cache, log_file=log)):
        retried += res.attempts > 1
        segments[sid] = outcome(res)
    for rnd in range(1, 4):   # a title repeated inside a lecture: the later part is asked again
        again, seen = [], {}
        for k, sid, seg in items:
            s = segments[sid]
            if not s["ok"]:
                continue
            if s["title"].lower() in seen.setdefault(k, set()):
                again.append((k, sid, seg))
            else:
                seen[k].add(s["title"].lower())
        if not again:
            break
        print(f"4e: {len(again)} repeated titles, asking again (round {rnd})", flush=True)
        rr = [make_request(template, k, lects[k]["title"], sid, seg, facts,
                           {segments[o]["title"] for o in lects[k]["segments"] if o != sid and segments[o]["ok"]},
                           sampling, f"{sid} again {rnd}") for k, sid, seg in again]
        for (k, sid, seg), res in zip(again, llm.generate_many(rr, cache_file=cache, log_file=log)):
            retried += res.attempts > 1
            segments[sid] = outcome(res)
    n_ok = sum(s["ok"] for s in segments.values())
    run_info = {"stage": "4e_part_titles", "model": llm.model,
                "prompt_sha256": hashlib.sha256(template.encode()).hexdigest()[:16], "think_budget": THINK_BUDGET,
                "lectures": keys, "segments": len(segments), "ok": n_ok, "failed": len(segments) - n_ok,
                "retried": retried, "seconds": round(time.time() - t0, 1),
                "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
    (od / "titles.json").write_text(json.dumps({"run": run_info, "segments": segments}, indent=1,
                                               ensure_ascii=False) + "\n", encoding="utf-8")
    lines = []
    for k in keys:
        lines.append(f"Lecture {k}: {lects[k]['title']}")
        for sid, seg in lects[k]["segments"].items():
            s = segments[sid]
            lines.append(f"  {sid}  {seg['start']:.0f}-{seg['end']:.0f} s  "
                         f"{s['title'] or 'NO TITLE ' + str(s['problems'])}")
            lines.append(f"      goal: {seg['subgoal']}")
        lines.append("")
    (od / "titles.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"4e: {n_ok} ok, {len(segments) - n_ok} failed, {retried} retried, {run_info['seconds']} s", flush=True)
    return run_info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--lectures", help="lectures, e.g. 1,4 (default: all)")
    ap.add_argument("--seed", type=int, help="sampling seed (default: the config's)")
    ap.add_argument("--out", help="output folder (default: output/<course>/stage_4e_part_titles)")
    a = ap.parse_args()
    cfg = LLMConfig.load(a.llm).with_(think_budget=THINK_BUDGET)
    with LLM(cfg) as llm:
        run(a.course, llm, lec.parse_only(a.lectures) if a.lectures else None, a.seed, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
