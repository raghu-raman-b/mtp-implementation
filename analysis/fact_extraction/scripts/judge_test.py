"""Test of the 2b judge on lecture 1's 2a facts: both materials (evidence only, whole segment), judge seeds 0-2,
one rewrite round on seed 0 of each. Writes data/judge_test/: <material>_seed<k>.json (2b's segment records),
llm/ (cache, calls), report.md (verdicts side by side, stability, rewrites).

    cd pipeline && python ../analysis/fact_extraction/scripts/judge_test.py [--report-only]

Record only (2026-11-11): the "evidence" material and its prompt were removed from 2b after this test, so run_all()
no longer runs against the current 2b; --report-only still rebuilds report.md from the saved data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[3] / "pipeline"
sys.path.insert(0, str(PIPE))

from scripts import s2b_verify_facts as b  # noqa: E402
from scripts.llm import LLM, LLMConfig  # noqa: E402

COURSE, LECTURE = "nptel_vr", "1"
CONFIG = PIPE / "configs" / "gemma4_12b_llamacpp.json"
OUT = Path(__file__).resolve().parents[1] / "data" / "judge_test"
MATERIALS, SEEDS = ("evidence", "segment"), (0, 1, 2)


def run_all():
    segs = b.load_segments(COURSE, LECTURE)
    with LLM(LLMConfig.load(CONFIG)) as llm:
        for seed in SEEDS:
            for m in MATERIALS:
                recs = b.verify_segments(COURSE, llm, segs, m, OUT, seed=seed, rewrite=(seed == 0))
                (OUT / f"{m}_seed{seed}.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False) + "\n")
                print(f"{m} seed {seed}: failed "
                      f"{sum(1 for r in recs for v in r['verdicts'] if v and not v['pass'])} of "
                      f"{sum(r['facts_2a'] for r in recs)}")
        print(llm.totals)


def report():
    segs = b.load_segments(COURSE, LECTURE)
    runs = {(m, k): json.loads((OUT / f"{m}_seed{k}.json").read_text()) for m in MATERIALS for k in SEEDS}
    verdict = {key: {f["id"]: v for r, s in zip(recs, segs) for f, v in zip(s["facts"], r["verdicts"])}
               for key, recs in runs.items()}
    facts = [f for s in segs for f in s["facts"]]
    mark = lambda v: "–" if v is None else ("✓" if v["pass"] else "✗")  # noqa: E731
    L = ["# 2b judge test: lecture 1 (Gemma 4 12B)", "",
         f"{len(facts)} facts from 2a, {len(segs)} segments. Judge seeds {list(SEEDS)}; rewrite on seed 0 only. "
         "✓ pass, ✗ fail, – no verdict.", "", "## Failures per run", "",
         "| Material | " + " | ".join(f"seed {k}" for k in SEEDS) + " | failed in all seeds | flips between seeds |",
         "|---|" + "--:|" * (len(SEEDS) + 2)]
    for m in MATERIALS:
        fails = [sum(not v["pass"] for v in verdict[(m, k)].values() if v) for k in SEEDS]
        allf = sum(all(verdict[(m, k)][f["id"]] and not verdict[(m, k)][f["id"]]["pass"] for k in SEEDS) for f in facts)
        flips = sum(len({mark(verdict[(m, k)][f["id"]]) for k in SEEDS}) > 1 for f in facts)
        L.append(f"| {m} | " + " | ".join(map(str, fails)) + f" | {allf} | {flips} |")
    maj = {m: {f["id"]: sum(bool(verdict[(m, k)][f["id"]] and not verdict[(m, k)][f["id"]]["pass"]) for k in SEEDS) >= 2
               for f in facts} for m in MATERIALS}
    differ = [f["id"] for f in facts if maj["evidence"][f["id"]] != maj["segment"][f["id"]]]
    L += ["", f"Majority verdicts (2 of 3 seeds) differ between the materials on {len(differ)} facts"
          + (f": {', '.join(differ)}." if differ else "."), ""]
    out_of = {m: {r["segment"]: r for r in runs[(m, 0)]} for m in MATERIALS}
    L += ["## Rewrites (seed 0)", "", "| Material | kept | rewritten | removed | unresolved | facts after |",
          "|---|--:|--:|--:|--:|--:|"]
    for m in MATERIALS:
        c = {}
        for r in runs[(m, 0)]:
            for o in r["outcome"].values():
                c[o["result"]] = c.get(o["result"], 0) + 1
        L.append(f"| {m} | {c.get('kept', 0)} | {c.get('rewritten', 0)} | {c.get('removed', 0)} | "
                 f"{c.get('unresolved', 0)} | {sum(len(r['final']) for r in runs[(m, 0)])} |")
    L += ["", "## Every fact", "",
          "Verdicts: E = evidence only, S = whole segment; one mark per seed. Reasons and outcomes are seed 0's.", ""]
    for s in segs:
        L += [f"### {s['id']}: {s['subgoal']}", ""]
        for f in s["facts"]:
            fid = f["id"]
            L.append(f"**[{fid}]** {f['text']}  ")
            L.append("E " + "".join(mark(verdict[('evidence', k)][fid]) for k in SEEDS)
                     + " · S " + "".join(mark(verdict[('segment', k)][fid]) for k in SEEDS))
            for m in MATERIALS:
                v = verdict[(m, 0)][fid]
                if v and not v["pass"]:
                    o = out_of[m][s["id"]]["outcome"][fid]
                    L.append(f"- {m[0].upper()}: {v['reason']}  ")
                    if o["result"] == "rewritten":
                        L += [f"  → rewritten: {t}  " for t in o["as"]]
                    else:
                        L.append(f"  → {o['result']}")
            L.append("")
    (OUT / "report.md").write_text("\n".join(L) + "\n")
    print(f"report -> {OUT / 'report.md'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.report_only:
        run_all()
    report()
