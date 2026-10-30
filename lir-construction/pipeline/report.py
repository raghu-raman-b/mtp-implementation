"""Timing, cost and quality report, written automatically at the end of every run.

Stages run as batches across lectures, so a lecture's time is attributed: each stage's wall time is split over
lectures in proportion to the time their calls held a server slot (the sum of their request latencies). Stages
without LLM calls are split by sentence count.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict

from .context import Run

# which LLM-call stages belong to which timed stage
FAMILY = {
    "stage1_segment": {"stage1_segment"}, "stage2_annotate": {"stage2_annotate"}, "stage3_goals": {"stage3_goals"},
    "stage4_course_state": {"stage4_canonicalize", "stage4_edges"},
    "stage5_generate": {"stage5_primer", "stage5_quiz", "stage5_summary", "stage5_open_questions", "stage5_generate"},
    "stage6_calibrate": {"stage6_calibrate"}, "stage6_judge": {"stage6_judge", "stage6_repair"},
}
KIND_LABEL = {"subgoal": "sub-goal describes segment", "term": "definition faithful", "quiz": "quiz item answerable + correct",
              "summary": "summary supported", "oq": "open question sound", "recall": "recall item sound",
              "edge": "edge true"}


def _m(s: float) -> str:
    return f"{s / 60:.1f}"


def write(R: Run, total_wall: float, extra: dict | None = None) -> str:
    recs = R.llm.records
    lecs = R.lectures
    sentences = {l.id: len(l.sentences) for l in lecs}
    per_lec = defaultdict(float)
    per_lec_stage = defaultdict(lambda: defaultdict(float))
    stage_rows = []
    for st in R.timer.stages:
        fam = FAMILY.get(st["stage"], {st["stage"]})
        rs = [r for r in recs if r["stage"] in fam]
        busy = defaultdict(float)
        for r in rs:
            if r["lecture_id"] != "_course":
                busy[r["lecture_id"]] += r["latency_s"]
        tot = sum(busy.values())
        for l in lecs:
            share = busy[l.id] / tot if tot else sentences[l.id] / max(1, sum(sentences.values()))
            per_lec[l.id] += st["wall_s"] * share
            per_lec_stage[l.id][st["stage"]] += st["wall_s"] * share
        out_tok = sum(r["output_tokens"] for r in rs)
        stage_rows.append({"stage": st["stage"], "wall_s": round(st["wall_s"], 1), "calls": len(rs),
                           "input_tokens": sum(r["input_tokens"] for r in rs), "output_tokens": out_tok,
                           "throughput_tok_s": round(out_tok / st["wall_s"], 1) if st["wall_s"] else 0,
                           "models": sorted({r.get("model", "") for r in rs})})
    calls_by_lec, tok_by_lec = defaultdict(int), defaultdict(int)
    for r in recs:
        calls_by_lec[r["lecture_id"]] += 1
        tok_by_lec[r["lecture_id"]] += r["output_tokens"]

    # layer-2 pass rates per stage (judge and repair calls excluded: they have their own table)
    origins = [o for l in lecs for o in l.origin] + R.course_origin
    pass_rows = []
    for stage in sorted({o["stage"] for o in origins if not o["stage"].startswith("stage6_judge")}):
        os_ = [o for o in origins if o["stage"] == stage]
        first = sum(o["validator"]["passed"] and o["retries"] == 0 for o in os_)
        later = sum(o["validator"]["passed"] and o["retries"] > 0 for o in os_)
        pass_rows.append({"stage": stage, "items": len(os_), "passed_first": first, "passed_after_retry": later,
                          "failed": len(os_) - first - later})
    # layer-3 judge results per check
    judge = defaultdict(lambda: defaultdict(int))
    for l in lecs:
        for kind, c in l.quality.get("checks", {}).items():
            for k, v in c.items():
                judge[kind][k] += v
    video = sum(l.inp.duration for l in lecs)
    pipeline = sum(s["wall_s"] for s in R.timer.stages)
    rows = []
    for l in lecs:
        rows.append({"lecture_id": l.id, "title": l.inp.title, "video_min": round(l.inp.duration / 60, 1),
                     "sentences": sentences[l.id], "segments": len(l.segments), "llm_calls": calls_by_lec[l.id],
                     "output_tokens": tok_by_lec[l.id], "processing_min": round(per_lec[l.id] / 60, 2),
                     "processing_min_per_video_hour": round(per_lec[l.id] / 60 / (l.inp.duration / 3600), 2)
                     if l.inp.duration else None,
                     "by_stage_s": {k: round(v, 1) for k, v in per_lec_stage[l.id].items()},
                     "timing_source": l.inp.timing_source, "flags": len(l.flags)})
    data = {"course_id": R.course.course_id, "generator": R.llm.model, "judge_model": R.judge.model if R.judge else None,
            "slots": R.server.slots, "date": time.strftime("%Y-%m-%d %H:%M"), "pipeline_wall_s": round(pipeline, 1),
            "total_wall_s": round(total_wall, 1), "video_s": round(video, 1), "lectures": rows, "stages": stage_rows,
            "pass_rates": pass_rows, "judge": {k: dict(v) for k, v in judge.items()}, **(extra or {})}
    (R.out / "timing.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

    n = max(1, len(lecs))
    L = [f"# LIR build report: {R.course.title}", "",
         f"{time.strftime('%Y-%m-%d %H:%M')} · generator **{R.llm.model}** · judge **{data['judge_model']}** · "
         f"{R.server.slots} parallel slots · thinking on for every call · temperature 0", "",
         "## Summary", "",
         f"- **{len(lecs)} lectures, {_m(video)} min of video, built in {_m(pipeline)} min** "
         f"(about **{_m(pipeline / n)} min per lecture**, "
         + (f"**{pipeline / 60 / (video / 3600):.1f} min of processing per hour of video**)." if video else ").")]
    L.append(f"- {len(recs):,} LLM calls, {sum(r['output_tokens'] for r in recs):,} output tokens (including "
             f"thinking), {sum(r['input_tokens'] for r in recs):,} input tokens.")
    if extra and extra.get("videos"):
        v = extra["videos"]
        L.append(f"- Videos: {v['done']}/{v['total']} downloaded" + (f"; failed: {', '.join(v['failed'])}" if v["failed"]
                                                                      else "."))
    if extra and extra.get("api") and extra["api"]["calls"]:
        a = extra["api"]
        L.append(f"- API spend: **${a['run_usd']:.3f}** this run ({a['calls']} calls); ${a['total_usd']:.3f} of the "
                 f"${a['budget_usd']:.2f} budget used so far (ledger: `api_spend.json`)."
                 + (f" {a['unjudged']} items were not judged because the budget ran out." if a.get("unjudged") else ""))
    if extra and extra.get("scoring"):
        sc = extra["scoring"]
        L.append(f"- Open-answer scorer: m = {sc['m']}, tau = {sc['tau']}"
                 + (f" (calibrated, {sc['agreement']:.0%} agreement on {sc['answers']} generated answers)."
                    if sc.get("calibrated") else " (defaults)."))
    L += ["", "## Per lecture", "",
          "Processing time is attributed: each stage's wall time is split across lectures by how long their calls "
          "held a server slot.", "",
          "| Lecture | Title | Video (min) | Segments | LLM calls | Output tokens | Processing (min) | min per video hour |",
          "|---|---|--:|--:|--:|--:|--:|--:|"]
    for r in rows:
        L.append(f"| {r['lecture_id']} | {r['title']} | {r['video_min']} | {r['segments']} | {r['llm_calls']} | "
                 f"{r['output_tokens']:,} | {r['processing_min']} | {r['processing_min_per_video_hour']} |")
    L += ["", "## Per stage", "", "| Stage | Wall time (s) | LLM calls | Input tokens | Output tokens | Output tok/s |",
          "|---|--:|--:|--:|--:|--:|"]
    for s in stage_rows:
        L.append(f"| {s['stage']} | {s['wall_s']} | {s['calls']} | {s['input_tokens']:,} | {s['output_tokens']:,} | "
                 f"{s['throughput_tok_s']} |")
    L += ["", "## Validation: code checks (layer 2)", "",
          "| Stage | Items | Passed first time | Passed after retry | Still failing (resolved by code) |",
          "|---|--:|--:|--:|--:|"]
    for p in pass_rows:
        L.append(f"| {p['stage']} | {p['items']} | {p['passed_first']} | {p['passed_after_retry']} | {p['failed']} |")
    if judge:
        L += ["", "## Validation: judge (layer 3)", "",
              "| Check | Judged | Passed first time | Repaired and passed | Dropped | Replaced by code | Not judged (budget) |",
              "|---|--:|--:|--:|--:|--:|--:|"]
        for kind, c in judge.items():
            L.append(f"| {KIND_LABEL.get(kind, kind)} | {c.get('judged', 0)} | {c.get('passed_first', 0)} | "
                     f"{c.get('repaired', 0)} | {c.get('dropped', 0)} | {c.get('replaced_by_code', 0)} | "
                     f"{c.get('not_judged_budget', 0)} |")
    flagged = [(l.id, f) for l in lecs for f in l.flags]
    if flagged:
        L += ["", "## Notes", "", "Items that failed code checks and were repaired or replaced by code:", ""]
        L += [f"- {lid}: {f}" for lid, f in flagged]
    L += ["", "Raw numbers: `timing.json`. Per-call tokens, retries and validator results: the `origin` list in each "
              "lecture file; judge results: its `quality` field.", ""]
    text = "\n".join(L)
    (R.out / "timing_report.md").write_text(text, encoding="utf-8")
    return text
