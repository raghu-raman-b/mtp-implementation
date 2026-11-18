"""Block 1: the fact judge (stage 2b) against the reference labels, the seeded errors, and itself.

    cd pipeline
    python3 ../analysis/fact_judge/compare.py judge  --run base                      # from the caches, no model
    python3 ../analysis/fact_judge/compare.py judge  --run seed1 --seed 1 --seeded   # (EC2) a new judge run
    python3 ../analysis/fact_judge/compare.py report --runs base,seed1,seed2         # the comparison
    python3 ../analysis/fact_judge/compare.py rejudge                                # (EC2) the rewrites judged again

A judge run is the judge's verdicts, made exactly as stage 2b makes them (scripts/s2b_verify_facts.judge_request:
one call per segment, the segment's facts, the current prompts/fact_judge.txt):
  gold     the 62 facts of 2a on lectures 1, 4, 16 (12 calls), compared with gold.json;
  seeded   with --seeded, the 34 entries of seeded.json, one call each: the segment's 2a facts with the entry's
           "replaces" taken out and its facts put in their place (at the end when nothing is replaced), renumbered.
Answers already in stage 2b's cache are taken from it (seed 0 with the same prompt is the baseline round); new
answers are cached in llm/cache.jsonl here, never in the pipeline's output. A run is saved in runs/<run>.json with
the prompt's hash, so runs with different prompts are never counted as flips.

The report (report_compare.md, compare.json) gives, per run:
  - judge vs gold: caught, missed, false alarms, per property, with and without the borderline labels; the same for
    stage 2b's verdict (the judge's, failed also by the code checks, as 2b applies them);
  - seeded errors: caught (any of the entry's facts failed), all its facts failed, caught for the right reason (the
    judge's reason names a property in "breaks"), per property; other facts of the call failed;
  - the code checks (pointing, acronym) against gold (properties 5 and 6) and against the seeded entries marked code;
  - flips between runs with the same prompt; the list of disagreements with both reasons;
  - the gate of block 1 (PLAN.md): seeded caught >= 90%, false alarms on gold-pass facts <= 10%, flips <= 5%, no
    property with zero catches.
What a broken judge would look like here: seeded errors passed, or caught for another reason; gold-pass facts failed;
verdicts that change with the seed; a property it never fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = Path(os.environ.get("PIPELINE_ROOT") or HERE.parents[1] / "pipeline")   # another copy: for tests only
sys.path.insert(0, str(PIPE))

from scripts import fact_checks, s2b_verify_facts as s2b  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

COURSE = "nptel_vr"
LECTURES = ["1", "4", "16"]
JUDGE_CONFIG = PIPE / "configs" / "sage_a15_vllm.json"
STAGE_CACHE = PIPE / "output" / COURSE / "stage_2b_verify_facts" / "llm" / "cache.jsonl"
OUT = HERE                                      # runs/, llm/ and the report go here (--out for tests)
CACHE, CALLS, RUNS = OUT / "llm" / "cache.jsonl", OUT / "llm" / "calls.jsonl", OUT / "runs"
PROPS = {1: "Significant", 2: "Whole", 3: "Established", 4: "Grounded", 5: "Self-contained", 6: "Terms in full",
         7: "On the subject", 8: "Faithful"}
NAMES = {1: r"significan", 2: r"\bwhole\b", 3: r"\bestablished\b", 4: r"\bgrounded\b", 5: r"self-contained",
         6: r"terms in full|in full words", 7: r"on the subject|on-subject", 8: r"\bfaithful"}
CODE_PROP = {"pointing": 5, "acronym": 6}       # the property each code check stands for


# ------------------------------------------------------------------------------------------------ inputs
def gold() -> dict:
    return json.loads((HERE / "gold.json").read_text())["facts"]


def seeded() -> list[dict]:
    return json.loads((HERE / "seeded.json").read_text())["errors"]


def segments() -> dict[str, dict]:
    return {s["id"]: s for k in LECTURES for s in s2b.load_segments(COURSE, k)}


def seeded_segment(seg: dict, entry: dict) -> tuple[dict, list[str]]:
    """The segment with the entry's facts in place of "replaces", renumbered; and each fact's origin (its 2a ID, or
    "<entry>#<i>" for a seeded fact)."""
    local = {sid: i for i, (sid, _) in enumerate(seg["sentences"], 1)}
    bad = [e for f in entry["facts"] for e in f["evidence"] if e not in local]
    if bad:
        raise ValueError(f"{entry['id']}: evidence not in {seg['id']}: {bad}")
    new = [{"origin": f"{entry['id']}#{i}", "text": f["text"], "evidence": [local[e] for e in f["evidence"]]}
           for i, f in enumerate(entry["facts"])]
    out, placed = [], False
    for f in seg["facts"]:
        if f["id"] in entry["replaces"]:
            if not placed:
                out += new
                placed = True
        else:
            out.append({"origin": f["id"], "text": f["text"], "evidence": f["evidence"]})
    if not placed:
        out += new
    missing = set(entry["replaces"]) - {f["id"] for f in seg["facts"]}
    if missing:
        raise ValueError(f"{entry['id']}: replaces facts that are not in {seg['id']}: {sorted(missing)}")
    facts = [{"id": f"{seg['id']}/F{j}", "text": f["text"], "evidence": f["evidence"]} for j, f in enumerate(out)]
    return dict(seg, facts=facts), [f["origin"] for f in out]


def prompt_sha() -> str:
    return hashlib.sha256((s2b.JUDGE.read_text() + s2b.JUDGE_SYSTEM.read_text()).encode()).hexdigest()[:12]


# ------------------------------------------------------------------------------------------------ judging
THINK_END = "I have thought enough"     # what vLLM writes when the thinking budget runs out (the configs' think_end)


def call_meta(key: str, n_facts: int, reasoning: str, output_tokens: int) -> dict:
    return {"key": key, "facts": n_facts, "output_tokens": output_tokens, "capped": THINK_END in (reasoning or "")}


def judge(requests: list[Request], cfg: LLMConfig, cache_only: bool) -> tuple[list[dict | None], list[dict | None]]:
    """The verdicts of each request ({fact ID: {"pass", "reason"}}), from stage 2b's cache, this folder's cache, or
    the model (unless cache_only), and per request its call (output tokens, whether the thinking hit its budget).
    None where there is no usable answer."""
    llm = LLM(cfg)
    out: list[dict | None] = [None] * len(requests)
    meta: list[dict | None] = [None] * len(requests)
    nfacts = [len(r.schema["properties"]["verdicts"]["items"]["properties"]["fact"]["enum"]) for r in requests]
    todo = []
    for i, r in enumerate(requests):
        hit = llm.lookup(r, STAGE_CACHE) or llm.lookup(r, CACHE)
        if hit is not None:
            out[i] = _verdicts(hit["content"], r)
            meta[i] = call_meta(r.key, nfacts[i], hit["reasoning"], hit["output_tokens"])
        else:
            todo.append(i)
    if todo and cache_only:
        print(f"{len(todo)} of {len(requests)} calls are in no cache: {[requests[i].key for i in todo]}")
    elif todo:
        with llm:
            for i, res in zip(todo, llm.generate_many([requests[i] for i in todo], cache_file=CACHE, log_file=CALLS)):
                out[i] = {v["fact"]: {"pass": v["pass"], "reason": v["reason"]}
                          for v in res.parsed["verdicts"]} if res.ok else None
                meta[i] = call_meta(requests[i].key, nfacts[i], res.reasoning, res.output_tokens)
    return out, meta


def _verdicts(content: str, r: Request) -> dict | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if r.check and r.check(parsed):
        return None
    return {v["fact"]: {"pass": v["pass"], "reason": v["reason"]} for v in parsed["verdicts"]}


def run_judge(label: str, seed: int | None, with_seeded: bool, cache_only: bool, cfg_path: Path):
    cfg = LLMConfig.load(cfg_path)
    segs = segments()
    judged = [s for s in segs.values() if s["facts"]]
    reqs = [s2b.judge_request(COURSE, s, seed) for s in judged]
    entries = []
    if with_seeded:
        for e in seeded():
            seg, origin = seeded_segment(segs[e["segment"]], e)
            r = s2b.judge_request(COURSE, seg, seed)
            r.key = f"seeded/{e['id']}"
            reqs.append(r)
            entries.append((e, seg, origin))
    res, meta = judge(reqs, cfg, cache_only)
    run = {"run": label, "judge": cfg.model, "seed": seed, "prompt_sha": prompt_sha(), "gold": {}, "seeded": {},
           "no_answer": [r.key for r, v in zip(reqs, res) if v is None], "calls": [m for m in meta if m]}
    for s, v in zip(judged, res[:len(judged)]):
        for f in s["facts"]:
            if v is not None:
                run["gold"][f["id"]] = v[f["id"]]
    for (e, seg, origin), v in zip(entries, res[len(judged):]):
        if v is not None:
            run["seeded"][e["id"]] = [{"id": f["id"], "origin": o, "text": f["text"], **v[f["id"]]}
                                      for f, o in zip(seg["facts"], origin)]
    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{label}.json").write_text(json.dumps(run, indent=1, ensure_ascii=False) + "\n")
    print(f"run {label}: {len(run['gold'])} gold facts, {len(run['seeded'])} seeded entries judged; "
          f"no answer: {run['no_answer'] or 'none'}")


def rejudge(cfg_path: Path, cache_only: bool):
    """Test only (2b never does this): judge again every segment of the 2b run that has a rewritten fact, with its
    final facts, as 2b's judge sees a segment; count the rewrites that still fail (judge, or the code checks as 2b
    applies them). Written to runs/rejudge.json and rejudge.md."""
    od = s2b.out_dir(COURSE)
    segs, rows, reqs, items = segments(), [], [], []
    for k in LECTURES:
        for rec in json.loads((od / "judgements" / f"lec_{k}.json").read_text()):
            if not any(o["result"] == "rewritten" for o in rec["outcome"].values()):
                continue
            seg = segs[rec["segment"]]
            facts = [{"id": f"{seg['id']}/F{j}", "text": f["text"], "evidence": f["evidence"]}
                     for j, f in enumerate(rec["final"])]
            rewritten = {f"{seg['id']}/F{j}": f["from"] for j, f in enumerate(rec["final"])
                         if rec["outcome"][f["from"]]["result"] == "rewritten"}
            s = dict(seg, facts=facts)
            r = s2b.judge_request(COURSE, s)
            r.key = f"rejudge/{seg['id']}"
            reqs.append(r)
            items.append((s, rewritten))
    res, meta = judge(reqs, LLMConfig.load(cfg_path), cache_only)
    for (s, rewritten), v in zip(items, res):
        code = {f["id"]: fact_checks.rewrite_notes(fl) for f, fl in
                zip(s["facts"], fact_checks.flags(s["facts"], [t for _, t in s["sentences"]]))}
        for f in s["facts"]:
            if v is None:
                continue
            rows.append({"fact": f["id"], "rewrite_of": rewritten.get(f["id"]), "text": f["text"],
                         "pass": v[f["id"]]["pass"], "reason": v[f["id"]]["reason"], "code": code[f["id"]]})
    rw = [x for x in rows if x["rewrite_of"]]
    still = [x for x in rw if not x["pass"] or x["code"]]
    kept_failed = [x for x in rows if not x["rewrite_of"] and (not x["pass"] or x["code"])]
    RUNS.mkdir(exist_ok=True)
    (RUNS / "rejudge.json").write_text(json.dumps({"prompt_sha": prompt_sha(), "judge": LLMConfig.load(cfg_path).model,
                                                   "calls": [m for m in meta if m], "facts": rows, "no_answer": [r.key for r, v in zip(reqs, res)
                                                                                if v is None]},
                                                  indent=1, ensure_ascii=False) + "\n")
    md = ["# The rewritten facts judged again (block 1, test only)", "",
          f"Segments with a rewrite: {len(items)}; facts judged: {len(rows)}; rewrites: {len(rw)}; rewrites that "
          f"still fail: {pct(len(still), len(rw))} (judge or code checks). Facts that were kept in 2b and fail now: "
          f"{len(kept_failed)}.", ""]
    md += [f"- **{x['fact']}** (rewrite of {x['rewrite_of']}): {'fails' if x in still else 'passes'}. {x['text']}"
           + (f" Judge: {x['reason']}" if not x["pass"] else "") + (f" Code: {' '.join(x['code'])}" if x["code"] else "")
           for x in rw]
    if kept_failed:
        md += ["", "Kept facts that fail in this call (the noise of one more judge call):", ""]
        md += [f"- **{x['fact']}**: {x['reason']}" + (f" Code: {' '.join(x['code'])}" if x["code"] else "")
               for x in kept_failed]
    (OUT / "rejudge.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:3]))


# ------------------------------------------------------------------------------------------------ measuring
def named(reason: str) -> set[int]:
    """The properties a failing reason names, by number ("property 2", "properties 4 and 8") or by name."""
    out = set()
    for m in re.finditer(r"propert(?:y|ies)\s+((?:\d(?:\s*(?:,|and|&|/)\s*)?)+)", reason, re.I):
        out |= {int(d) for d in re.findall(r"\d", m.group(1)) if d in "12345678"}
    for p, pat in NAMES.items():
        if re.search(pat, reason, re.I):
            out.add(p)
    return out


def code_flags() -> dict[str, list[str]]:
    """The code checks 2b applies (pointing, acronym), per 2a fact."""
    out = {}
    for s in segments().values():
        for f, fl in zip(s["facts"], fact_checks.flags(s["facts"], [t for _, t in s["sentences"]])):
            out[f["id"]] = [x["kind"] for x in fl if x["kind"] in fact_checks.REWRITE]
    return out


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "0/0"


def vs_gold(run: dict, g: dict, code: dict, with_code: bool, borderline: bool) -> dict:
    """Confusion of the run's verdicts (or 2b's: judge and code checks) against gold."""
    rows = {"caught": [], "missed": [], "false_alarm": [], "agree_pass": []}
    for fid, ref in g.items():
        if fid not in run["gold"] or (ref["borderline"] and not borderline):
            continue
        v = run["gold"][fid]
        fails = (not v["pass"]) or (with_code and bool(code.get(fid)))
        key = ("caught" if fails else "missed") if not ref["pass"] else ("false_alarm" if fails else "agree_pass")
        rows[key].append(fid)
    per_prop = {}
    for p in PROPS:
        refs = [fid for fid in rows["caught"] + rows["missed"] if p in g[fid]["fails"]]
        right = [fid for fid in rows["caught"] if p in g[fid]["fails"] and p in named(run["gold"][fid]["reason"])]
        alarms = [fid for fid in rows["false_alarm"] if p in named(run["gold"][fid]["reason"])]
        per_prop[p] = {"gold_fails": len(refs), "caught": sum(fid in rows["caught"] for fid in refs),
                       "right_reason": len(right), "false_alarms_naming_it": len(alarms)}
    return {k: sorted(v, key=_order) for k, v in rows.items()} | {"per_property": per_prop}


def vs_seeded(run: dict, base: dict | None) -> dict:
    entries = {e["id"]: e for e in seeded()}
    rows, per_prop, other = [], {p: [0, 0, 0] for p in PROPS}, []
    for eid, facts in run["seeded"].items():
        e = entries[eid]
        mine = [f for f in facts if f["origin"].startswith(eid + "#")]
        failed = [f for f in mine if not f["pass"]]
        right = [f for f in failed if named(f["reason"]) & set(e["breaks"])]
        rows.append({"id": eid, "kind": e["kind"], "breaks": e["breaks"], "caught": bool(failed),
                     "all_failed": len(failed) == len(mine), "right_reason": bool(right),
                     "reasons": [f["reason"] for f in mine], "passed": [f["text"] for f in mine if f["pass"]]})
        for p in e["breaks"]:
            per_prop[p][0] += 1
            per_prop[p][1] += bool(failed)
            per_prop[p][2] += bool(right)
        for f in facts:                                    # the call's other facts: failed now, passed in base?
            if not f["origin"].startswith(eid + "#") and not f["pass"]:
                was = (base or {}).get("gold", {}).get(f["origin"])
                other.append({"entry": eid, "fact": f["origin"], "failed_in_base": None if was is None else
                              not was["pass"], "reason": f["reason"]})
    return {"entries": rows, "per_property": {p: dict(zip(("entries", "caught", "right_reason"), v))
                                              for p, v in per_prop.items() if v[0]}, "other_failed": other}


def code_vs_gold(g: dict, code: dict) -> dict:
    out = {}
    for kind, p in CODE_PROP.items():
        flagged = {fid for fid, ks in code.items() if kind in ks}
        ref = {fid for fid, r in g.items() if p in r["fails"]}
        out[kind] = {"property": p, "flagged": sorted(flagged, key=_order),
                     "false_alarms": sorted(flagged - ref, key=_order), "misses": sorted(ref - flagged, key=_order),
                     "both": sorted(flagged & ref, key=_order)}
    segs = segments()
    rows = []
    for e in seeded():                                     # the seeded facts: do the checks catch them?
        seg, origin = seeded_segment(segs[e["segment"]], e)
        fl = fact_checks.flags(seg["facts"], [t for _, t in seg["sentences"]])
        kinds = sorted({x["kind"] for f, o, xs in zip(seg["facts"], origin, fl) if o.startswith(e["id"] + "#")
                        for x in xs if x["kind"] in fact_checks.REWRITE})
        if e.get("code") or kinds:
            rows.append({"id": e["id"], "kind": e["kind"], "expected": bool(e.get("code")), "flags": kinds})
    out["seeded"] = rows
    return out


def flips(runs: list[dict]) -> dict:
    """Facts whose verdict differs between runs of the same judge and prompt (gold facts and seeded facts)."""
    by_prompt: dict[str, list[dict]] = {}
    for r in runs:
        by_prompt.setdefault(f"{r['judge']}, prompt {r['prompt_sha']}", []).append(r)
    out = {}
    for sha, rs in by_prompt.items():
        if len(rs) < 2:
            continue
        keys = set.intersection(*(set(r["gold"]) for r in rs))
        changed = sorted((k for k in keys if len({r["gold"][k]["pass"] for r in rs}) > 1), key=_order)
        sk = set.intersection(*(set(r["seeded"]) for r in rs))
        seeded_changed = sorted(e for e in sk if len({tuple(f["pass"] for f in r["seeded"][e]
                                                            if f["origin"].startswith(e + "#")) for r in rs}) > 1)
        g = gold()
        clear = [k for k in keys if not g[k]["borderline"]]
        out[sha] = {"runs": [r["run"] for r in rs], "gold_facts": len(keys), "flipped": changed,
                    "clear_facts": len(clear), "flipped_clear": [k for k in changed if not g[k]["borderline"]],
                    "seeded_entries": len(sk), "seeded_flipped": seeded_changed}
    return out


# ------------------------------------------------------------------------------------------------ review 1, CHANGE 11
HISTORY_CACHE = HERE.parent / "fact_extraction" / "data" / "history" / "2b_2026-11-12_ec2" / "llm" / "cache.jsonl"


def _cache_index() -> dict:
    """(first fact ID, its reason) of every judge answer in the caches -> (capped, output tokens, facts)."""
    idx = {}
    for path in dict.fromkeys((STAGE_CACHE, CACHE, HERE / "llm" / "cache.jsonl", HISTORY_CACHE)):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            rec = json.loads(line)
            try:
                vs = json.loads(rec["content"])["verdicts"]
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            if vs:
                idx[(vs[0]["fact"], vs[0]["reason"])] = (THINK_END in rec["reasoning"], rec["output_tokens"], len(vs))
    return idx


def calls_of(run: dict, idx: dict) -> list[dict]:
    """The run's calls (recorded, or found in the caches by the first verdict of each call)."""
    if run.get("calls"):
        return run["calls"]
    out, by_seg = [], {}
    for fid, v in run["gold"].items():
        by_seg.setdefault(fid.rsplit("/", 1)[0], []).append((fid, v))
    for seg, vs in by_seg.items():
        fid, v = min(vs, key=lambda x: _order(x[0]))
        hit = idx.get((fid, v["reason"]))
        out.append({"key": seg, "facts": len(vs), "output_tokens": hit[1] if hit else None,
                    "capped": hit[0] if hit else None})
    for eid, facts in run["seeded"].items():
        f = facts[0]
        hit = idx.get((f["id"], f["reason"]))
        out.append({"key": f"seeded/{eid}", "facts": len(facts), "output_tokens": hit[1] if hit else None,
                    "capped": hit[0] if hit else None})
    return out


def pooled(runs: list[dict], g: dict) -> dict:
    """Per gold fact, its verdicts over every call of the runs: the gold calls and the seeded calls where the fact is
    unchanged. For gold failures also how many fail it for a property gold names."""
    out = {fid: {"verdicts": 0, "fails": 0, "right": 0} for fid in g}
    for r in runs:
        seen = [(fid, v) for fid, v in r["gold"].items()]
        seen += [(f["origin"], f) for facts in r["seeded"].values() for f in facts if f["origin"] in g]
        for fid, v in seen:
            o = out[fid]
            o["verdicts"] += 1
            if not v["pass"]:
                o["fails"] += 1
                o["right"] += bool(named(v["reason"]) & set(g[fid]["fails"]))
    return out


def outcome_2b(g: dict) -> dict:
    """2b's outcome per 2a fact (the current stage_2b_verify_facts) against gold."""
    od = s2b.out_dir(COURSE)
    rows = {}
    for k in LECTURES:
        p = od / "judgements" / f"lec_{k}.json"
        if p.exists():
            for rec in json.loads(p.read_text()):
                rows.update({fid: o["result"] for fid, o in rec["outcome"].items()})
    table = {}
    for fid, res in rows.items():
        lab = "pass" if g.get(fid, {}).get("pass", True) else "fail"
        table.setdefault(res, {"pass": [], "fail": []})[lab].append(fid)
    return table


def votes(runs: list[dict], g: dict) -> dict | None:
    """Majority of three and any of three over the first three runs of the first run's judge and prompt."""
    same = [r for r in runs if r["judge"] == runs[0]["judge"] and r["prompt_sha"] == runs[0]["prompt_sha"]][:3]
    if len(same) < 3:
        return None
    keys = set.intersection(*(set(r["gold"]) for r in same))
    out = {}
    for rule, need in (("majority of three", 2), ("any of three", 1)):
        fails = {k for k in keys if sum(not r["gold"][k]["pass"] for r in same) >= need}
        gf = {k for k in keys if not g[k]["pass"]}
        out[rule] = {"runs": [r["run"] for r in same], "caught": len(fails & gf), "gold_fails": len(gf),
                     "false_alarms": len(fails - gf), "gold_pass": len(keys - gf)}
    return out


def derived_md(runs: list[dict], g: dict) -> tuple[list[str], dict]:
    idx = _cache_index()
    md = ["## Pooled and derived numbers (review 1, CHANGE 11)", "",
          f"Current prompt hash: {prompt_sha()}. Runs: " + ", ".join(f"`{r['run']}` {r['prompt_sha']}" for r in runs) + ".", ""]
    data = {"current_prompt_sha": prompt_sha(), "calls": {}}
    md += ["Calls whose thinking reached the budget (the config's `think_end` in the thinking):", "",
           "| Run | Calls | At the budget | Of them with 10+ facts | Facts in the capped calls |", "|---|--:|--:|--:|---|"]
    for r in runs:
        cs = calls_of(r, idx)
        known = [c for c in cs if c["capped"] is not None]
        capped = [c for c in known if c["capped"]]
        data["calls"][r["run"]] = cs
        md.append(f"| `{r['run']}` | {len(known)} of {len(cs)} found | {len(capped)} | "
                  f"{sum(c['facts'] >= 10 for c in capped)} of {sum(c['facts'] >= 10 for c in known)} | "
                  f"{', '.join(str(c['facts']) for c in capped) or '-'} |")
    po = pooled(runs, g)
    data["pooled"] = po
    gf = [fid for fid in g if not g[fid]["pass"]]
    md += ["", "Gold failures over every call of these runs (gold calls and seeded calls where the fact is unchanged):", "",
           "| Fact | Gold fails | Borderline | Verdicts | Failed | For a gold property |", "|---|---|---|--:|--:|--:|"]
    for fid in sorted(gf, key=_order):
        o = po[fid]
        md.append(f"| {fid} | {g[fid]['fails']} | {'yes' if g[fid]['borderline'] else ''} | {o['verdicts']} | "
                  f"{o['fails']} | {o['right']} |")
    tot = sum(po[f]["verdicts"] for f in gf)
    md.append(f"| all | | | {tot} | {sum(po[f]['fails'] for f in gf)} | {sum(po[f]['right'] for f in gf)} |")
    gp = [fid for fid in g if g[fid]["pass"]]
    md += ["", f"Gold-pass facts failed in some call: {sum(po[f]['fails'] > 0 for f in gp)} of {len(gp)}; "
           f"verdicts failing a gold-pass fact: {sum(po[f]['fails'] for f in gp)} of {sum(po[f]['verdicts'] for f in gp)}.", ""]
    oc = outcome_2b(g)
    data["outcome_2b"] = oc
    md += ["2b's outcome (the current `stage_2b_verify_facts/`) against gold:", "",
           "| Outcome | Gold pass | Gold fail |", "|---|---|---|"]
    for res, t in sorted(oc.items()):
        fmt = lambda xs: (f"{len(xs)}" + (f" ({', '.join(sorted(xs, key=_order))})" if xs and res != "kept" else ""))
        md.append(f"| {res} | {fmt(t['pass'])} | {fmt(t['fail'])} |")
    md.append(f"\nGold-pass facts removed: {', '.join(oc.get('removed', {}).get('pass', [])) or 'none'}.")
    vo = votes(runs, g)
    data["votes"] = vo
    if vo:
        md += ["", "Verdicts combined over three runs (no new calls):", "",
               "| Rule | Runs | Gold failures caught | False alarms on gold-pass facts |", "|---|---|--:|--:|"]
        md += [f"| {rule} | {', '.join(v['runs'])} | {v['caught']}/{v['gold_fails']} | "
               f"{pct(v['false_alarms'], v['gold_pass'])} |" for rule, v in vo.items()]
    return md, data


def _order(fid: str):
    lec_, seg, f = fid.split("/")
    return int(lec_), int(seg[1:]), int(f[1:])


# ------------------------------------------------------------------------------------------------ report
def report(labels: list[str]):
    g, code = gold(), code_flags()
    runs = [json.loads((RUNS / f"{x}.json").read_text()) for x in labels]
    base = runs[0]
    out = {"runs": {}, "code_checks": code_vs_gold(g, code), "flips": flips(runs)}
    md = ["# The fact judge against the reference (block 1)", "",
          "Made by `analysis/fact_judge/compare.py`. Gold: `gold.json` (62 facts, 55 pass, 7 fail, 7 borderline). "
          "Seeded: `seeded.json` (34 entries). Property numbers: " +
          ", ".join(f"{p} {n}" for p, n in PROPS.items()) + ".", ""]
    for r in runs:
        res = {"gold": {}, "seeded": vs_seeded(r, base) if r["seeded"] else None}
        seed = "the config's seed (as in 2b)" if r["seed"] is None else f"seed {r['seed']}"
        md += [f"## Run `{r['run']}`: {r['judge']}, {seed}, prompt {r['prompt_sha']}", ""]
        md += ["| Verdict | Labels | Gold fails caught | Missed | False alarms on gold-pass facts |",
               "|---|---|--:|--:|--:|"]
        for with_code in (False, True):
            for bl in (True, False):
                c = vs_gold(r, g, code, with_code, bl)
                res["gold"][f"{'2b' if with_code else 'judge'}_{'all' if bl else 'no_borderline'}"] = c
                n_fail, n_pass = len(c["caught"]) + len(c["missed"]), len(c["false_alarm"]) + len(c["agree_pass"])
                md.append(f"| {'2b (judge + code checks)' if with_code else 'judge'} | "
                          f"{'all' if bl else 'without borderline'} | {pct(len(c['caught']), n_fail)} | "
                          f"{', '.join(c['missed']) or '-'} | {pct(len(c['false_alarm']), n_pass)} |")
        c = res["gold"]["judge_all"]
        md += ["", "Per property (judge, all labels): gold failures caught, of them with the property named in the "
               "reason; false alarms whose reason names the property.", "",
               "| Property | Gold fails | Caught | Right reason | False alarms naming it |", "|---|--:|--:|--:|--:|"]
        md += [f"| {p} {PROPS[p]} | {v['gold_fails']} | {v['caught']} | {v['right_reason']} | "
               f"{v['false_alarms_naming_it']} |" for p, v in c["per_property"].items()]
        md += ["", "Disagreements (judge, all labels):", ""]
        for fid in c["missed"] + c["false_alarm"]:
            ref, v = g[fid], r["gold"][fid]
            md.append(f"- **{fid}** gold {'pass' if ref['pass'] else 'fail ' + str(ref['fails'])}"
                      f"{' (borderline)' if ref['borderline'] else ''}, judge {'pass' if v['pass'] else 'fail'}. "
                      f"Gold: {ref['note']} Judge: {v['reason']}")
        if res["seeded"]:
            s = res["seeded"]
            rows = s["entries"]
            md += ["", f"Seeded errors: caught {pct(sum(x['caught'] for x in rows), len(rows))}, all facts of the "
                   f"entry failed {pct(sum(x['all_failed'] for x in rows), len(rows))}, caught for the right reason "
                   f"{pct(sum(x['right_reason'] for x in rows), len(rows))}.", "",
                   "| Property broken | Entries | Caught | Right reason |", "|---|--:|--:|--:|"]
            md += [f"| {p} {PROPS[p]} | {v['entries']} | {v['caught']} | {v['right_reason']} |"
                   for p, v in s["per_property"].items()]
            md += ["", "Seeded entries not caught, or caught for another reason:", ""]
            md += [f"- **{x['id']}** ({x['kind']}; breaks {x['breaks']}): {'caught, other reason' if x['caught'] else 'passed'}."
                   f" Judge: {' / '.join(x['reasons'])}" for x in rows if not x["right_reason"]]
            new = [o for o in s["other_failed"] if o["failed_in_base"] is False]
            md += ["", f"Other facts of the seeded calls failed: {len(s['other_failed'])}, of them passed in "
                   f"`{base['run']}`: {len(new)}" + (" (" + ", ".join(f"{o['fact']} in {o['entry']}" for o in new) + ")"
                                                      if new else "") + "."]
        out["runs"][r["run"]] = res
        md.append("")
    cc = out["code_checks"]
    md += ["## The code checks against gold", "",
           "`pointing` stands for property 5, `acronym` for property 6; 2b fails a flagged fact whatever the judge says.",
           "", "| Check | Flagged | Gold fails the property too | False alarms | Gold failures not flagged |",
           "|---|--:|---|---|---|"]
    for kind in CODE_PROP:
        x = cc[kind]
        md.append(f"| `{kind}` | {len(x['flagged'])} | {', '.join(x['both']) or '-'} | "
                  f"{', '.join(x['false_alarms']) or '-'} | {', '.join(x['misses']) or '-'} |")
    md += ["", "False alarms with gold's note:", ""]
    for kind in CODE_PROP:
        for fid in cc[kind]["false_alarms"]:
            md.append(f"- `{kind}` **{fid}**: gold {'pass' if g[fid]['pass'] else 'fail ' + str(g[fid]['fails'])}. "
                      f"{g[fid]['note']}")
    md += ["", "Seeded entries and the code checks (expected: marked `code` in seeded.json):", ""]
    md += [f"- {x['id']} ({x['kind']}): expected {'yes' if x['expected'] else 'no'}, flags {x['flags'] or 'none'}"
           for x in cc["seeded"]]
    if out["flips"]:
        md += ["", "## Flips between runs of the same judge and prompt", ""]
        for sha, f in out["flips"].items():
            md.append(f"- {sha}, runs {', '.join(f['runs'])}: {pct(len(f['flipped']), f['gold_facts'])} gold "
                      f"facts flipped ({', '.join(f['flipped']) or 'none'}); without borderline facts "
                      f"{pct(len(f['flipped_clear']), f['clear_facts'])}; seeded entries with a changed verdict: "
                      f"{pct(len(f['seeded_flipped']), f['seeded_entries'])}")
    dmd, out["derived"] = derived_md(runs, gold())
    md += [""] + dmd
    md += ["", "## Gate (block 1, PLAN.md)", ""] + gate(out, runs)
    (OUT / "compare.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    (OUT / "report_compare.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[-12:]))


def gate(out: dict, runs: list[dict]) -> list[str]:
    """The gate on the first run (the baseline), with the other runs of the report alongside."""
    last = runs[0]
    res = out["runs"][last["run"]]
    c = res["gold"]["judge_all"]
    n_pass = len(c["false_alarm"]) + len(c["agree_pass"])
    others = []
    for r in runs[1:]:
        o = out["runs"][r["run"]]
        oc = o["gold"]["judge_all"]
        seeded_part = ""
        if o["seeded"]:
            rows = o["seeded"]["entries"]
            seeded_part = f", seeded caught {pct(sum(x['caught'] for x in rows), len(rows))}"
        others.append(f"`{r['run']}`: false alarms {pct(len(oc['false_alarm']), len(oc['false_alarm']) + len(oc['agree_pass']))}"
                      + seeded_part)
    lines = [f"For run `{last['run']}` (the baseline)" + (f"; the other runs: {'; '.join(others)}" if others else "") + ":", "",
             f"- False alarms on gold-pass facts <= 10%: {pct(len(c['false_alarm']), n_pass)}"]
    if res["seeded"]:
        rows = res["seeded"]["entries"]
        lines.append(f"- Seeded errors caught >= 90%: {pct(sum(x['caught'] for x in rows), len(rows))}")
        zero = [f"{p} {PROPS[p]}" for p, v in res["seeded"]["per_property"].items() if v["caught"] == 0]
        lines.append(f"- No property with zero catches (seeded): {'met' if not zero else 'not met: ' + ', '.join(zero)}")
    else:
        lines.append("- Seeded errors caught >= 90%: not measured in this run")
    f = [x for x in out["flips"].values() if last["run"] in x["runs"]]
    lines.append(f"- Flips <= 5%: {pct(len(f[0]['flipped']), f[0]['gold_facts']) if f else 'not measured (one run of this prompt)'}")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge", help="make a judge run")
    j.add_argument("--run", required=True, help="label, e.g. base, seed1, v2")
    j.add_argument("--seed", type=int, help="judge seed (default: the config's, as in 2b)")
    j.add_argument("--seeded", action="store_true", help="also judge the 34 seeded entries")
    j.add_argument("--cache-only", action="store_true", help="never call the model")
    j.add_argument("--judge", default=str(JUDGE_CONFIG), help="judge LLMConfig")
    r = sub.add_parser("report", help="compare runs (the first is the baseline)")
    r.add_argument("--runs", required=True, help="labels, e.g. base,seed1,seed2")
    rj = sub.add_parser("rejudge", help="judge the 2b run's rewritten facts once more (test only)")
    rj.add_argument("--cache-only", action="store_true", help="never call the model")
    rj.add_argument("--judge", default=str(JUDGE_CONFIG), help="judge LLMConfig")
    for x in (j, r, rj):
        x.add_argument("--out", help="folder for runs/, llm/ and the report (default: this folder; tests use another)")
    a = ap.parse_args()
    if a.out:
        global CACHE, CALLS, RUNS, OUT
        OUT = Path(a.out).resolve()
        CACHE, CALLS, RUNS = OUT / "llm" / "cache.jsonl", OUT / "llm" / "calls.jsonl", OUT / "runs"
    if a.cmd == "judge":
        run_judge(a.run, a.seed, a.seeded, a.cache_only, Path(a.judge))
    elif a.cmd == "rejudge":
        rejudge(Path(a.judge), a.cache_only)
    else:
        report(a.runs.split(","))


if __name__ == "__main__":
    main()
