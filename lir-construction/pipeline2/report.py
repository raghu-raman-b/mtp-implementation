"""The v2 run report: time and calls per step, what was kept and dropped, per lecture. Written to
output/<course>/v2/report.md (and report.json)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from .context import Run


def _m(s: float) -> str:
    return f"{s / 60:.1f} min" if s >= 60 else f"{s:.0f} s"


def write(R: Run, records: list, wall_s: float) -> str:
    calls = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "latency": 0.0})
    for r in records:
        c = calls[r["stage"]]
        c["calls"] += 1
        c["in"] += r["input_tokens"]
        c["out"] += r["output_tokens"]
        c["latency"] += r["latency_s"]
    dec = Counter((d["step"], d["decision"]) for d in R.decisions.items)
    C = R.registry.concepts if R.registry else {}
    lines = [f"# LIR v2 run: {R.course.title}", "",
             f"{len(R.lectures)} lectures, {sum(l.inp.duration for l in R.lectures) / 3600:.1f} h of video, "
             f"built in {_m(wall_s)}.", "", "## Steps", "", "| Step | Wall time |", "|---|---|"]
    lines += [f"| {s['stage']} | {_m(s['wall_s'])} |" for s in R.timer.stages]
    lines += ["", "## Calls sent (cache hits not counted)", "", "| Batch | Calls | Input tokens | Output tokens |",
              "|---|---|---|---|"]
    lines += [f"| {k} | {v['calls']:,} | {v['in']:,} | {v['out']:,} |" for k, v in sorted(calls.items())]
    lines += ["", "## Counts", "", "| What | Count |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in sorted(R.counts.items())]
    lines += ["", "## Decisions", "", "| Step | Decision | Count |", "|---|---|---|"]
    lines += [f"| {s} | {d} | {n:,} |" for (s, d), n in sorted(dec.items())]
    lines += ["", "## Per lecture", "", "| Lecture | Parts | Key points | Terms | Concepts introduced | Edges (evidence here) | Flags |",
              "|---|---|---|---|---|---|---|"]
    for l in R.lectures:
        intro = sum(1 for c in C.values() if c.introduced.startswith(l.id + "/"))
        lines.append(f"| {l.id} | {len(l.parts)} | {sum(len(p.key_points) for p in l.parts)} | "
                     f"{sum(len(p.terms) for p in l.parts)} | {intro} | "
                     f"{sum(e['lecture_id'] == l.id for e in R.edges)} | {len(l.flags)} |")
    text = "\n".join(lines) + "\n"
    d = R.out
    (d / "report.md").write_text(text, encoding="utf-8")
    (d / "report.json").write_text(json.dumps({"wall_s": wall_s, "steps": R.timer.stages, "calls": calls,
                                               "counts": R.counts,
                                               "decisions": {f"{s}: {x}": n for (s, x), n in dec.items()}},
                                              indent=1), encoding="utf-8")
    return text
