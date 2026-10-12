#!/usr/bin/env python
"""Slide snapping: move every TopicTiling / TextTiling / TSVLT boundary forward to the next slide change.

    python compare/snap_slides.py <work dir with slide_changes.json>

A boundary is only ever moved later, to the first sentence that starts at or after the next slide
change; boundaries landing on the same slide change merge, and a boundary with no slide change
after it stays where it is. Adds methods.topictiling_snap and methods.texttiling_snap to compare/results.json.
"""
import json
import sys
from pathlib import Path

import run_compare as rc

HERE = Path(__file__).resolve().parent


def snap_forward(gaps, units, changes):
    out, moved = set(), []
    for g in gaps:
        t = units[g + 1].start
        nxt = next((s for s in changes if s >= t), None)
        if nxt is None:
            out.add(g)
            continue
        g2 = next((k for k in range(g, len(units) - 1) if units[k + 1].start >= nxt), None)
        if g2 is None:
            out.add(g)
            continue
        out.add(g2)
        moved.append(units[g2 + 1].start - t)
    return sorted(out), moved


def main():
    slides = json.loads((Path(sys.argv[1]) / "slide_changes.json").read_text())
    res = json.loads((HERE / "results.json").read_text())
    units = [rc.tt.Unit(u["start"], u["end"], u["text"]) for u in res["units"]]
    gold = res["gold"]
    changes = sorted(c["t"] for c in slides["changes"])
    def snapped(r, keys):
        gaps, moved = snap_forward(r["gaps"], units, changes)
        run = {k: r[k] for k in keys}
        run.update({"from_boundaries": r["n_boundaries"], "from_pk": r["pk"], "from_wd": r["wd"], "moved": len(moved),
                    "shift_mean": sum(moved) / len(moved) if moved else 0.0, "shift_max": max(moved, default=0.0)})
        run.update(rc.evaluate(gaps, units, gold["gaps"], gold["times"]))
        print(f"  {' '.join(f'{k}={r[k]:g}' for k in keys)}: {r['n_boundaries']} -> {run['n_boundaries']} boundaries, "
              f"mean shift {run['shift_mean']:.0f}s (max {run['shift_max']:.0f}s)  Pk {r['pk']:.3f} -> {run['pk']:.3f}  WD {r['wd']:.3f} -> {run['wd']:.3f}  "
              f"F1@30={run['f1@30']['f1']:.2f} F1@60={run['f1@60']['f1']:.2f}  cuts at {[round(t) for t in run['times']]}")
        return run

    meta = {"slide_changes": slides["changes"], "n_cuts": slides["n_cuts"], "ocr_step": slides["step"]}
    # the slide changes on their own, as a segmenter
    alone = rc.evaluate(sorted({next(k for k in range(len(units) - 1) if units[k + 1].start >= s)
                                for s in changes if units[0].start < s <= units[-1].start}), units, gold["gaps"], gold["times"])
    print(f"slide changes alone: {alone['n_boundaries']} boundaries  Pk={alone['pk']:.3f} WD={alone['wd']:.3f} "
          f"F1@30={alone['f1@30']['f1']:.2f} F1@60={alone['f1@60']['f1']:.2f}")
    print("TopicTiling + slide snap")
    res["methods"]["topictiling_snap"] = {"runs": [snapped(r, ["window"]) for r in res["methods"]["topictiling"]["runs"]],
                                          "slides_alone": alone, "meta": meta}
    print("TextTiling + slide snap")
    res["methods"]["texttiling_snap"] = {"runs": [snapped(r, ["window", "min_seg"]) for r in res["methods"]["texttiling"]["runs"]],
                                         "meta": meta}
    if "gemma" in res["methods"]:
        print("Gemma + slide snap")
        res["methods"]["gemma_snap"] = {"runs": [snapped(r, ["seed"]) for r in res["methods"]["gemma"]["runs"]], "meta": meta}
    print("TSVLT + slide snap")
    for key in ("tsvlt", "tsvlt_long"):
        for r in res["methods"][key]["runs"]:
            for st in ("stage2", "stage3", "stage4"):
                print(f"  {key} seed {r['seed']} {st}", end="")
                r[st + "_snap"] = snapped(r[st], [])
    (HERE / "results.json").write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
