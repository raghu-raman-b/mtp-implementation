"""Latency and answer read for the qa weak points (not covered, comparisons, prerequisites, where, repeated citations).

    cd pipeline && python3 ../analysis/qa/bench.py TAG [--runs 2] [--variant shipped|fast] [IDS...]

Asks each question `runs` times in one process with the local Gemma (qa starts it) and appends one line per answer to
analysis/qa/bench_<TAG>.jsonl: the time, the per-round timing qa logged (model seconds, tokens, thinking characters,
tool seconds), the tools, the answer, the citations and covered. Logs go where qa puts them (output/<course>/qa/, or
$QA_OUTPUT/<course>/qa/: set QA_OUTPUT to a copy, and QA_CONFIG to a config copy whose server_log is outside output/).
--variant: "shipped" keeps qa's round-0 switches as they are; "fast" sends round 0 with thinking off and tool_choice
"required"; "think" sends round 0 with thinking on and tool_choice "auto" (the switches qa.answer has).
"""
import argparse
import importlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parents[1] / "pipeline"
sys.path.insert(0, str(PIPE))
import qa  # noqa: E402
from qa.knowledge import qa_dir  # noqa: E402

Q = [
    ("B01", "not_covered", "How does a Kalman filter fuse IMU and camera data for tracking?", None),
    ("B02", "not_covered", "What is the vergence-accommodation conflict in VR headsets?", None),
    ("B03", "not_covered", "How does redirected walking let users explore large virtual spaces?", None),
    ("B04", "off_topic", "Who won the 2022 FIFA World Cup?", None),
    ("B05", "compare", "How do full gait, partial gait and gait negation locomotion techniques differ?", None),
    ("B06", "compare", "How is augmented reality different from virtual reality?", None),
    ("B07", "compare", "What is the difference between immersion and presence?", None),
    ("B08", "list", "What are the five stages of contextual inquiry?", None),
    ("B09", "where", "In which lecture is stereoscopy taught?", None),
    ("B10", "where", "Where does the course explain the uncanny valley?", None),
    ("B11", "where", "Where is drift correction taught?", None),
    ("B12", "prereq", "What do I need to know before lecture 16?", None),
    ("B13", "prereq", "What do I need to know before lecture 40?", None),
    ("B14", "prereq", "What do I need to know before lecture 30?", None),
    ("B15", "definition", "What is extended reality?", None),
    ("B16", "how", "How does inside looking out infrared tracking work?", None),
    ("B17", "lookup", "Which statistical test should I use for a within-subject design with one factor at two levels?",
     None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--variant", choices=["shipped", "fast", "think"], default="shipped")
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    qa_answer = importlib.import_module("qa.answer")   # the module (qa.answer the attribute is the function)
    if a.variant == "fast":
        qa_answer.ROUND0_THINK, qa_answer.ROUND0_TOOL_CHOICE = False, "required"
    elif a.variant == "think":
        qa_answer.ROUND0_THINK, qa_answer.ROUND0_TOOL_CHOICE = True, "auto"
    print(f"round 0: thinking {qa_answer.ROUND0_THINK}, tool_choice {qa_answer.ROUND0_TOOL_CHOICE}", flush=True)
    out = HERE / f"bench_{a.tag}.jsonl"
    log = qa_dir("nptel_vr") / "answers.jsonl"
    t = time.time()
    qa.warm("nptel_vr")
    print(f"warm {time.time() - t:.1f}s", flush=True)
    for run in range(a.runs):
        for qid, kind, q, lec in Q:
            if a.ids and qid not in a.ids:
                continue
            t = time.time()
            r = qa.answer(q, course="nptel_vr", lecture=lec)
            dt = time.time() - t
            rec_log = json.loads(log.read_text().splitlines()[-1])
            rec = {"id": qid, "run": run, "variant": a.variant, "kind": kind, "question": q, "seconds": round(dt, 2),
                   "timing": rec_log.get("timing"), "rounds": rec_log.get("rounds"), "covered": r["covered"],
                   "tools": [s["tool"] for s in r["steps"]], "steps": r["steps"], "answer": r["answer"],
                   "citations": [c["fact"] or c["segment"] for c in r["citations"]]}
            with out.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            tm = " | ".join(f"m{x['model_s']}s o{x['out']} th{x['think_chars']}" for x in rec["timing"] or [])
            print(f"{qid} run{run} {dt:5.1f}s {rec['tools']} cov={r['covered']} :: {tm}", flush=True)


if __name__ == "__main__":
    main()
