"""Stage 2b: verify the facts of each segment with an LLM judge, then rewrite or remove the ones that fail.

    python scripts/s2b_verify_facts.py nptel_vr --llm configs/qwen38_27b_vllm.json [--judge configs/sage_a15_vllm.json] [--only 1-5]

--llm is the model that rewrites: it must be 2a's config, since the rewrite continues 2a's conversation (found in 2a's
cache by the request). --judge is the model that judges (default: --llm). With two configs the judge runs first and
its server is stopped before the rewriter's starts, so each can take the whole GPU.

Reads   output/<course>/stage_2a_fact_extraction/fact_maps/lec_<n>.json, llm/cache.jsonl (2a's answers, to rebuild
        the 2a conversation exactly), and what 2a reads (segment maps, segment texts, course block, titles)
Prompts prompts/fact_judge.txt (the judge) with prompts/fact_judge_system.txt as its system message (Sage-A1.5's
        verification mode needs one), prompts/fact_rewrite.txt
Writes  output/<course>/stage_2b_verify_facts/
          fact_maps/lec_<n>.json      the verified facts, renumbered: {"1/S0/F0": {"text": ..., "evidence": [...]}}
          fact_text/lec_<n>.txt       one line per fact: "[1/S0/F0] text"
          judgements/lec_<n>.json     per segment: the judge's verdicts, the rewrite answer, and for each 2a fact
                                      what became of it (kept, rewritten as, removed, unresolved)
          checks/lec_<n>.json         the code checks (scripts/fact_checks.py) on the final facts, as in 2a
          llm/cache.jsonl, calls.jsonl

Per segment, one round:
1. Judge (one call): the course block, lecture title, segment goal, the whole segment, and every 2a fact of the
   segment with its evidence numbers. For each fact: "reason", then "pass" (true/false) over eight properties.
   A fact also fails, whatever the judge says, when a code check finds a pointing word in it or an acronym the
   segment never uses (fact_checks.REWRITE); the check's note is added to the reason.
2. Rewrite (one call, only if a fact failed): the 2a conversation rebuilt (2a prompt, 2a's answer as the model gave
   it), then the failed facts with the reasons. For each: "remove", or "rewrite" as one or more facts (facts that
   are details of one point: the first rewritten as the whole point, the others removed).
3. The fact map: facts that passed, in place; each rewritten fact replaced by its rewrite; removed facts dropped;
   exact repeats collapsed. Rewrites are not judged again. Facts are renumbered F0, F1, ... per segment.
Sentence numbers in the prompts are local to the segment ([1]..[n], as in 2a); code maps them to sentence IDs.
A judge answer that misses or repeats a fact, or a rewrite answer that misses a failed fact, is retried by the LLM
API; a failed fact still without an action is "unresolved" and left out of the fact map.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, fact_checks, lectures as lec, s2a_fact_extraction as s2a  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPTS = ROOT / "prompts"
JUDGE = PROMPTS / "fact_judge.txt"
JUDGE_SYSTEM = PROMPTS / "fact_judge_system.txt"
REWRITE = PROMPTS / "fact_rewrite.txt"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_2b_verify_facts"


# ---------------------------------------------------------------- inputs
def load_segments(course: str, key: str) -> list[dict]:
    """The lecture's segments with their sentences and 2a facts (evidence as local numbers 1..n)."""
    seg_map = json.loads((s2a.maps_dir(course) / f"{lec.stem_of(key)}.json").read_text())
    facts = json.loads((s2a.out_dir(course) / "fact_maps" / f"{lec.stem_of(key)}.json").read_text())
    segs = []
    for seg_id, seg in seg_map.items():
        sents = s2a.load_segment(course, seg_id)
        local = {sid: i for i, (sid, _) in enumerate(sents, 1)}
        segs.append({"id": seg_id, "key": key, "subgoal": seg["subgoal"], "sentences": sents,
                     "facts": [{"id": fid, "text": f["text"], "evidence": [local[e] for e in f["evidence"]]}
                               for fid, f in facts.items() if fid.rsplit("/", 1)[0] == seg_id]})
    return segs


def extraction_request(course: str, seg: dict) -> Request:
    """2a's request for this segment, exactly as 2a built it (its answer is found in 2a's cache by this request)."""
    return Request(prompt=s2a.build_prompt(course, seg["key"], seg["subgoal"], seg["sentences"]), key=seg["id"],
                   schema=s2a.schema(len(seg["sentences"])), meta={"lecture": seg["key"]})


# ---------------------------------------------------------------- judge
def facts_block(seg: dict) -> str:
    return "\n\n".join(f"[{f['id']}] (evidence: {', '.join(map(str, f['evidence']))}) {f['text']}"
                       for f in seg["facts"])


def judge_prompt(course: str, seg: dict) -> str:
    block, template = course_meta.course_prompt(course), JUDGE.read_text()
    if not block:
        template = template.replace("{course}\n\n", "")
    numbered = "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(seg["sentences"], 1))
    out = (template.replace("{course}", block)
           .replace("{lecture_title}", course_meta.lecture_title(course, seg["key"]))
           .replace("{subgoal}", seg["subgoal"])
           .replace("{segment}", numbered))
    return out.replace("{facts}", facts_block(seg))     # last: fact and sentence text is never replaced


def judge_schema(fact_ids: list[str]) -> dict:
    n = len(fact_ids)
    return {"type": "object", "additionalProperties": False, "required": ["verdicts"],
            "properties": {"verdicts": {"type": "array", "minItems": n, "maxItems": n, "items": {
                "type": "object", "additionalProperties": False, "required": ["fact", "reason", "pass"],
                "properties": {"fact": {"type": "string", "enum": fact_ids}, "reason": {"type": "string"},
                               "pass": {"type": "boolean"}}}}}}


def covers(ids: list[str], field: str, key: str):
    """A check: the answer's list `field` has exactly one entry for each of `ids`."""
    def check(parsed) -> list[str]:
        got = [x["fact"] for x in parsed[field]]
        missing = [i for i in ids if i not in got]
        repeated = sorted({i for i in got if got.count(i) > 1})
        return ([f"no {key} for {', '.join(missing)}"] if missing else []) + \
               ([f"more than one {key} for {', '.join(repeated)}"] if repeated else [])
    return check


def judge_request(course: str, seg: dict, seed: int | None = None) -> Request:
    ids = [f["id"] for f in seg["facts"]]
    return Request(prompt=judge_prompt(course, seg), system=JUDGE_SYSTEM.read_text().strip(), key=seg["id"],
                   schema=judge_schema(ids),
                   check=covers(ids, "verdicts", "verdict"), sampling={} if seed is None else {"seed": seed},
                   meta={"lecture": seg["key"]})


# ---------------------------------------------------------------- rewrite
def rewrite_schema(failed_ids: list[str], n: int) -> dict:
    fact = {"type": "object", "additionalProperties": False, "required": ["evidence", "text"],
            "properties": {"evidence": {"type": "array", "minItems": 1,
                                        "items": {"type": "integer", "minimum": 1, "maximum": n}},
                           "text": {"type": "string"}}}
    entry = lambda action, lo, hi: {  # noqa: E731
        "type": "object", "additionalProperties": False, "required": ["fact", "action", "rewrite"],
        "properties": {"fact": {"type": "string", "enum": failed_ids}, "action": {"const": action},
                       "rewrite": {"type": "array", "items": fact, "minItems": lo, **({"maxItems": hi} if hi is not None else {})}}}
    return {"type": "object", "additionalProperties": False, "required": ["facts"],
            "properties": {"facts": {"type": "array", "items": {"anyOf": [entry("rewrite", 1, None),
                                                                           entry("remove", 0, 0)]}}}}


def rewrite_request(course: str, seg: dict, failed: list[dict], extraction: dict,
                    seed: int | None = None) -> Request:
    """The 2a conversation rebuilt, then the failed facts with the judge's reasons."""
    block = "\n\n".join(f"[{f['id']}] (evidence: {', '.join(map(str, f['evidence']))}) {f['text']}\n"
                        f"Problem: {f['reason']}" for f in failed)
    ex = extraction_request(course, seg)
    ids = [f["id"] for f in failed]
    return Request(prompt=ex.prompt, key=seg["id"], schema=rewrite_schema(ids, len(seg["sentences"])),
                   followup=[{"role": "assistant", "content": extraction["content"]},
                             {"role": "user", "content": REWRITE.read_text().replace("{failed}", block)}],
                   check=covers(ids, "facts", "action"), sampling={} if seed is None else {"seed": seed},
                   meta={"lecture": seg["key"]})


# ---------------------------------------------------------------- one segment, one round
@contextmanager
def started(llm: LLM | LLMConfig):
    """An LLM as it is, or one made from a config for the block: its server starts at the first request not in the
    cache (none if all are) and is stopped at the end of the block."""
    if isinstance(llm, LLMConfig):
        with LLM(llm) as x:
            yield x
    else:
        yield llm


def verify_segments(course: str, llm: LLM | LLMConfig, segs: list[dict], od: Path, seed: int | None = None,
                    rewrite: bool = True, judge: LLM | LLMConfig | None = None) -> list[dict]:
    """Judge every segment (all at once), then rewrite the failed facts (all at once). Returns one record per
    segment: verdicts, rewrite answer, outcome per 2a fact, and the final facts (local evidence numbers).
    llm rewrites (2a's model) and judges unless judge is given. Each is an LLM (started) or an LLMConfig (its server
    runs only for its phase: the judge's is stopped before the rewriter's starts)."""
    cache, log = od / "llm" / "cache.jsonl", od / "llm" / "calls.jsonl"
    todo = [s for s in segs if s["facts"]]
    with started(judge if judge is not None else llm) as j:
        print(f"2b judge: {sum(len(s['facts']) for s in todo)} facts in {len(todo)} segments, judged by {j.model}",
              flush=True)
        judged = dict(zip([s["id"] for s in todo], j.generate_many(
            [judge_request(course, s, seed) for s in todo], cache_file=cache, log_file=log)))
    records, failed_of = {}, {}
    for s in segs:
        res = judged.get(s["id"])
        verdicts = {v["fact"]: v for v in res.parsed["verdicts"]} if res is not None and res.ok else {}
        rec = {"segment": s["id"], "seed": seed, "facts_2a": len(s["facts"]),
               "judge_ok": res is None or res.ok, "judge_errors": [] if res is None else res.errors,
               "judge_thinking": "" if res is None else res.reasoning,
               "verdicts": [verdicts.get(f["id"]) for f in s["facts"]], "rewrite": None, "outcome": {}}
        records[s["id"]] = rec
        # code checks that fail a fact whatever the judge says (a pointing word, an acronym the segment never uses)
        notes = {f["id"]: fact_checks.rewrite_notes(fl) for f, fl in
                 zip(s["facts"], fact_checks.flags(s["facts"], [t for _, t in s["sentences"]]))}
        rec["code_failed"] = {fid: n for fid, n in notes.items() if n}
        failed = []
        for f in s["facts"]:
            v = verdicts.get(f["id"])
            if v is None:                                  # no usable verdict: kept unjudged below
                continue
            reasons = ([] if v["pass"] else [v["reason"]]) + notes[f["id"]]
            if reasons:
                failed.append(dict(f, reason=" ".join(reasons)))
        if failed and rewrite:
            failed_of[s["id"]] = failed
    if failed_of:
        rw = llm if isinstance(llm, LLM) else LLM(llm)     # lookup needs no server: find 2a's answers first
        rewrites = []
        for s in segs:
            if s["id"] in failed_of:
                extraction = rw.lookup(extraction_request(course, s), s2a.out_dir(course) / "llm" / "cache.jsonl")
                if extraction is None:
                    raise RuntimeError(f"{s['id']}: 2a's answer is not in 2a's cache (was 2a run with this config?)")
                rewrites.append((s, rewrite_request(course, s, failed_of[s["id"]], extraction, seed)))
        n_failed = sum(len(f) for f in failed_of.values())
        print(f"2b rewrite: {n_failed} failed facts in {len(failed_of)} segments, rewritten by {rw.model}", flush=True)
        # an LLM passed in started is used as it is; one made here from the config starts its server at the first
        # request not in the cache and stops it at the end of the block
        with nullcontext(rw) if rw is llm else rw:
            for (s, _), res in zip(rewrites, rw.generate_many([r for _, r in rewrites], cache_file=cache,
                                                              log_file=log)):
                records[s["id"]]["rewrite"] = {"ok": res.ok, "errors": res.errors,
                                               "answer": res.parsed if res.ok else None,
                                               "content": res.content, "thinking": res.reasoning}
    for s in segs:
        rec = records[s["id"]]
        actions = {a["fact"]: a for a in ((rec["rewrite"] or {}).get("answer") or {"facts": []})["facts"]}
        final = []
        for f, v in zip(s["facts"], rec["verdicts"]):
            if v is None:                                  # the judge gave no usable answer: keep, unverified
                rec["outcome"][f["id"]] = {"result": "unjudged"}
                final.append({"from": f["id"], "evidence": f["evidence"], "text": f["text"]})
            elif v["pass"] and not (rewrite and f["id"] in rec["code_failed"]):
                rec["outcome"][f["id"]] = {"result": "kept"}
                final.append({"from": f["id"], "evidence": f["evidence"], "text": f["text"]})
            elif not rewrite:
                rec["outcome"][f["id"]] = {"result": "failed"}
            elif f["id"] not in actions:
                rec["outcome"][f["id"]] = {"result": "unresolved"}
            elif actions[f["id"]]["action"] == "remove":
                rec["outcome"][f["id"]] = {"result": "removed"}
            else:
                new = [{"from": f["id"], "evidence": sorted(set(r["evidence"])), "text": r["text"]}
                       for r in actions[f["id"]]["rewrite"]]
                rec["outcome"][f["id"]] = {"result": "rewritten", "as": [r["text"] for r in new]}
                final += new
        kept, dropped = fact_checks.collapse(final)        # a rewrite can repeat a fact that was kept
        rec["collapsed"] = [[final[a]["text"], final[b]["from"]] for a, b in dropped]
        rec["final"] = [{k: v for k, v in f.items() if k != "index"} for f in kept]
    return [records[s["id"]] for s in segs]


def fact_map(seg: dict, final: list[dict]) -> dict:
    """The segment's final facts, renumbered, with sentence IDs."""
    return {f"{seg['id']}/F{j}": {"text": f["text"], "evidence": [seg["sentences"][i - 1][0] for i in f["evidence"]]}
            for j, f in enumerate(final)}


def run(course: str, llm: LLM | LLMConfig, lectures: list | None = None,
        judge: LLM | LLMConfig | None = None) -> dict:
    """llm: 2a's model, which rewrites (and judges unless judge is given); an LLM (started) or an LLMConfig."""
    keys = lec.normalize(lectures) or lec.keys(s2a.out_dir(course) / "fact_maps")
    od = out_dir(course)
    for sub in ("fact_maps", "fact_text", "judgements", "checks", "llm"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    t0, counts, checks = time.time(), {}, {}
    segs = {k: load_segments(course, k) for k in keys}
    records = verify_segments(course, llm, [s for k in keys for s in segs[k]], od, judge=judge)
    by_seg = {r["segment"]: r for r in records}
    for k in keys:
        stem, facts, checks[k] = lec.stem_of(k), {}, {}
        for s in segs[k]:
            final = by_seg[s["id"]]["final"]
            facts.update(fact_map(s, final))
            checks[k][s["id"]] = fact_checks.report(final, [t for _, t in s["sentences"]],
                                                    [f"{s['id']}/F{j}" for j in range(len(final))])
        (od / "checks" / f"{stem}.json").write_text(json.dumps(checks[k], indent=1, ensure_ascii=False) + "\n")
        (od / "fact_maps" / f"{stem}.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n")
        (od / "fact_text" / f"{stem}.txt").write_text("".join(f"[{i}] {f['text']}\n" for i, f in facts.items()))
        (od / "judgements" / f"{stem}.json").write_text(
            json.dumps([by_seg[s["id"]] for s in segs[k]], indent=1, ensure_ascii=False) + "\n")
    for r in records:
        for o in r["outcome"].values():
            counts[o["result"]] = counts.get(o["result"], 0) + 1
    summary = {"segments": len(records), "facts_2a": sum(r["facts_2a"] for r in records),
               "facts": sum(len(r["final"]) for r in records), **counts,
               "code_failed": sum(len(r["code_failed"]) for r in records), **s2a.check_totals(checks),
               "wall_s": round(time.time() - t0, 1)}
    print(", ".join(f"{k} {v}" for k, v in summary.items()))
    return summary


def run_unjudged(course: str, lectures: list | None = None) -> dict:
    """MVP pass-through (2026-11-13, the user skipped the judge after block 1's review found it did more harm than
    good): the 2a facts become the stage's facts unchanged, with their 2a IDs (no renumbering), so the later stages
    read them from here as usual. judgements/ records every fact as kept, not judged."""
    keys = lec.normalize(lectures) or lec.keys(s2a.out_dir(course) / "fact_maps")
    od, src = out_dir(course), s2a.out_dir(course)
    for sub in ("fact_maps", "fact_text", "judgements", "checks"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    n = 0
    for k in keys:
        stem = lec.stem_of(k)
        facts = json.loads((src / "fact_maps" / f"{stem}.json").read_text())
        (od / "fact_maps" / f"{stem}.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n")
        (od / "fact_text" / f"{stem}.txt").write_text((src / "fact_text" / f"{stem}.txt").read_text())
        (od / "checks" / f"{stem}.json").write_text((src / "checks" / f"{stem}.json").read_text())
        by_seg: dict[str, list] = {}
        for fid in facts:
            by_seg.setdefault(fid.rsplit("/", 1)[0], []).append(fid)
        recs = [{"segment": sid, "judged": False, "facts_2a": len(ids),
                 "outcome": {fid: {"result": "kept", "judged": False} for fid in ids}} for sid, ids in by_seg.items()]
        (od / "judgements" / f"{stem}.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False) + "\n")
        n += len(facts)
    print(f"2b without the judge (pass-through): {len(keys)} lectures, {n} facts taken from 2a unchanged")
    return {"lectures": len(keys), "facts": n, "judged": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file of 2a's model: it rewrites (and judges without --judge)")
    ap.add_argument("--judge", help="LLMConfig file of the judge (default: --llm)")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8,24b,tut_1")
    ap.add_argument("--no-judge", action="store_true",
                    help="no model: the 2a facts pass through unchanged (MVP; --llm is then not used)")
    a = ap.parse_args()
    only = lec.parse_only(a.only) if a.only else None
    if a.no_judge:
        run_unjudged(a.course, only)
        return
    if a.judge:     # two models: each server runs only for its phase
        run(a.course, LLMConfig.load(a.llm), only, judge=LLMConfig.load(a.judge))
    else:
        with LLM(LLMConfig.load(a.llm)) as llm:
            run(a.course, llm, only)


if __name__ == "__main__":
    main()
