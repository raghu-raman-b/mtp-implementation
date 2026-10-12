#!/usr/bin/env python
"""Can TSVLT be made to settle on a human-like number of segments?

    python compare/tsvlt_settle.py

TSVLT thresholds a per-sentence boundary probability, with nothing limiting how many sentences pass.
Here its probabilities (stage 2 CNN, stage 3 graph-refined) are kept, but the boundaries are chosen by
the pipeline's own selector (texttiling.select_boundaries: best-scoring set with a minimum segment
duration). Adds methods.tsvlt_dp to compare/results.json.
"""
import json
from pathlib import Path

import numpy as np

import run_compare as rc

HERE = Path(__file__).resolve().parent
MIN_SEGS = [120.0, 240.0, 360.0]


def main():
    res = json.loads((HERE / "results.json").read_text())
    units = [rc.tt.Unit(u["start"], u["end"], u["text"]) for u in res["units"]]
    gold = res["gold"]
    runs = []
    for key, name in (("tsvlt", "default training"), ("tsvlt_long", "CNN 300 epochs")):
        for stage in ("p2", "p3"):
            for min_seg in MIN_SEGS:
                per_seed = []
                for r in res["methods"][key]["runs"]:
                    # probability at sentence i (first sentence of a new topic) scores the gap before it
                    score = np.array(r[stage][1:])
                    gaps, tau = rc.tt.select_boundaries(units, score, min_seg)
                    per_seed.append(rc.evaluate(gaps, units, gold["gaps"], gold["times"]))
                wd = [e["wd"] for e in per_seed]
                best = per_seed[int(np.argsort(wd)[len(wd) // 2])]  # median seed
                runs.append({"training": key, "scores": "stage 2" if stage == "p2" else "stage 3", "min_seg": min_seg,
                             "wd_seeds": wd, "n_seeds": [e["n_boundaries"] for e in per_seed], **best})
                print(f"{name:>16} {runs[-1]['scores']} min_seg={min_seg:>3.0f}s: segments {[n + 1 for n in runs[-1]['n_seeds']]} "
                      f"WD per seed {[round(x, 2) for x in wd]}  median-seed cuts at {[round(t) for t in best['times']]} "
                      f"F1@60={best['f1@60']['f1']:.2f}")
    res["methods"]["tsvlt_dp"] = {"runs": runs}
    (HERE / "results.json").write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
