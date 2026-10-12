#!/usr/bin/env python
"""Run the pipeline's labeling stages (subgoals -> hierarchy -> top goal) on each method's best
segmentation from compare/results.json. Resumable; writes compare/labels/<name>/.

    python compare/label_best.py
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_ir  # noqa: E402
import run  # noqa: E402
from goals import LLM  # noqa: E402

ROOT = HERE.parent.parent


def pick(res):
    """(name, description, gaps) per method: lowest WindowDiff, ties broken by Pk."""
    best = lambda runs: min(runs, key=lambda r: (r["wd"], r["pk"]))
    m = res["methods"]
    tt_default = best([r for r in m["texttiling"]["runs"] if r["min_seg"] > 0])
    tt_free = best([r for r in m["texttiling"]["runs"] if r["min_seg"] == 0])
    topic = next(r for r in m["topictiling"]["runs"] if r["window"] == 2)
    tsvlt = min(m["tsvlt_long"]["runs"], key=lambda r: (r["stage3"]["wd"], r["stage3"]["pk"], r["seed"]))
    tt_snap = best(m["texttiling_snap"]["runs"])
    topic_snap = next(r for r in m["topictiling_snap"]["runs"] if r["window"] == 2)
    return [
        ("texttiling_snap", f"TextTiling, window {tt_snap['window']}s, min segment {tt_snap['min_seg']:g}s, snapped forward to slide changes", tt_snap["gaps"]),
        ("topictiling_snap", "TopicTiling, window 2 sentences, snapped forward to slide changes", topic_snap["gaps"]),
        ("texttiling_w%d" % tt_default["window"], f"TextTiling, window {tt_default['window']}s, min segment 360s", tt_default["gaps"]),
        ("texttiling_w%d_free" % tt_free["window"], f"TextTiling, window {tt_free['window']}s, no min segment", tt_free["gaps"]),
        ("tsvlt_stage3", f"TSVLT stage 3, stage 2 trained 300 epochs, seed {tsvlt['seed']}", tsvlt["stage3"]["gaps"]),
        ("topictiling_w2", "TopicTiling, window 2 sentences", topic["gaps"]),
        ("tsvlt_snap", "TSVLT final output (default training, seed 0), snapped forward to slide changes",
         m["tsvlt"]["runs"][0]["stage4_snap"]["gaps"]),
        ("tsvlt_settled", "TSVLT stage-2 scores (300 epochs), boundaries chosen with a minimum-segment selector",
         best(m["tsvlt_dp"]["runs"])["gaps"]),
        ("gemma", "Gemma 4 asked for boundaries directly (seed 0, temperature 0)", m["gemma"]["runs"][0]["gaps"]),
        ("gemma_merge", "Gemma 4 + validation, failed cuts dropped (segments merged)", m["gemma_merge"]["runs"][0]["gaps"]),
        ("gemma_fix", "Gemma 4 + validation, failed cuts moved to a concluded point", m["gemma_fix"]["runs"][0]["gaps"]),
        ("human_coarse", "Human coarse boundaries (P01)", res["gold"]["gaps"]),
    ]


def main():
    res = json.loads((HERE / "results.json").read_text())
    units = res["units"]
    lec_dir = ROOT / res["lecture"]
    args = SimpleNamespace(force=False, port=8080)
    llm = LLM(f"http://127.0.0.1:{args.port}")
    for name, desc, gaps in pick(res):
        out = HERE / "labels" / name
        out.mkdir(parents=True, exist_ok=True)
        segs, a = [], 0
        for b in sorted(gaps) + [len(units) - 1]:
            segs.append({"id": f"S{len(segs) + 1:02d}", "start": units[a]["start"], "end": units[b]["end"],
                         "text": " ".join(u["text"] for u in units[a:b + 1])})
            a = b + 1
        run.write_json(out / "segments.json", {"lecture": f"{lec_dir.parent.name} / {lec_dir.name}", "srt": res["srt"],
                                               "method": desc, "segments": segs})
        run.say(f"\n{name}: {desc} -> {len(segs)} segments")
        run.run_labeling(lec_dir, segs, out, args, llm)
        build_ir.build(out)


if __name__ == "__main__":
    main()
