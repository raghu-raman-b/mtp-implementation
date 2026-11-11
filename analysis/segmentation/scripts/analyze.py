"""Measurements and figures for the segmentation report.

    cd pipeline && python ../analysis/segmentation/scripts/analyze.py

History: every run of the VR course (data/history/, and the pipeline's current outputs), measured the same way:
segment durations from each segment's first and last sentence with the pipeline's own timing (stage 1b's Timing).
Run-to-run: the full pipeline on 12 lectures per seed (data/runs/seed_<k>/; seed 0 = the pipeline's outputs),
compared pair by pair, for stage 1a's answers and for stage 1b's verified segments.

Writes data/history_runs.csv, data/run_to_run_pairs.csv, data/run_to_run_lectures.csv and figures/*.png.
"""
from __future__ import annotations

import csv
import itertools
import json
import shutil
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
PIPE = HERE.parents[1] / "pipeline"
sys.path.insert(0, str(PIPE))
from scripts import lectures as lec, s1b_verify_segments as s1b  # noqa: E402

COURSE = "nptel_vr"
MAIN = PIPE / "output" / COURSE
HIST = HERE / "data" / "history"
RUNS = HERE / "data" / "runs"
LECTURES = ["1", "4", "8", "14", "17", "18", "26", "36", "39", "45", "51", "57"]
TOL = 3                                        # boundary agreement: within 3 sentences

SURFACE, INK, INK2, GRID, BAND = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#f1f0ec"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK, "text.color": INK, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})

TIMING = {}


def timing(n: str) -> s1b.Timing:
    if n not in TIMING:
        TIMING[n] = s1b.load_timing(COURSE, n)
    return TIMING[n]


def segs_from_map(path: Path) -> dict[str, list[list[str]]]:
    """{lecture: [segment as sentence IDs]} from a folder of segment maps."""
    out = {}
    for p in lec.files(path):
        n = lec.key_of(p.stem)
        ids = timing(n).ids
        out[n] = [ids[ids.index(s["first"]):ids.index(s["last"]) + 1] for s in json.loads(p.read_text()).values()]
    return out


def segs_from_raw(path: Path) -> dict[str, list[list[str]]]:
    """{lecture: segments} from stage 1a's raw answers (lectures whose answer fails the structural checks left out)."""
    out = {}
    for p in lec.files(path):
        n = lec.key_of(p.stem)
        ans = s1b.segments_of(json.loads(p.read_text()).get("answer"))
        if not s1b.check(ans, timing(n).ids):
            out[n] = s1b.build(ans, timing(n).ids)
    return out


def minutes(n: str, seg: list[str]) -> float:
    return timing(n).seconds(seg) / 60


def cuts(n: str, segs: list[list[str]]) -> list[int]:
    ids = timing(n).ids
    return [ids.index(s[0]) for s in segs[1:]]


# ---------------------------------------------------------------------------- history
RUN_LIST = [  # (label, model, what changed, segments loader)
    ("Run 1", "Gemma 4 E4B", "v2's prompt", lambda: segs_from_map(HIST / "run1_e4b_v2prompt" / "segment_maps")),
    ("Run 2", "Gemma 4 E4B", "new prompt: sub-goals, bridges, stand-alone",
     lambda: segs_from_map(HIST / "run2_e4b_newprompt" / "stage_1b_verify_segments" / "segment_maps")),
    ("Run 3", "Gemma 4 12B", "same prompt, larger model",
     lambda: segs_from_map(HIST / "run3_12b_newprompt" / "stage_1b_verify_segments" / "segment_maps")),
    ("Run 4", "Gemma 4 12B", "restructured prompt, course outline and syllabus",
     lambda: segs_from_raw(HIST / "run4_12b_restructured" / "stage_1a_segmentation" / "raw")),
    ("Run 4 + 1b", "Gemma 4 12B", "verification with retries (current)",
     lambda: segs_from_map(MAIN / "stage_1b_verify_segments" / "segment_maps")),
]


def summarize(segs: dict[str, list[list[str]]]) -> dict:
    d = [minutes(n, s) for n, ss in segs.items() for s in ss]
    per = [len(ss) for ss in segs.values()]
    flagged = 0
    for n, ss in segs.items():
        for k, s in enumerate(ss):
            m = minutes(n, s)
            flagged += m > 15 or (m < 2 and k < len(ss) - 1)
    return {"lectures": len(segs), "segments": len(d), "per_lecture_min": min(per), "per_lecture_max": max(per),
            "per_lecture_mean": round(st.mean(per), 1), "median_min": round(st.median(d), 2),
            "under_1": sum(x < 1 for x in d), "under_2": sum(x < 2 for x in d), "over_10": sum(x > 10 for x in d),
            "over_15": sum(x > 15 for x in d), "longest_min": round(max(d), 1),
            "first_under_2": sum(minutes(n, ss[0]) < 2 for n, ss in segs.items()),
            "last_under_2": sum(minutes(n, ss[-1]) < 2 for n, ss in segs.items()),
            "flagged": flagged, "_durations": d}


def history():
    rows, dists = [], []
    for label, model, change, load in RUN_LIST:
        s = summarize(load())
        dists.append((label, model, change, s.pop("_durations")))
        rows.append({"run": label, "model": model, "change": change, **s})
    with open(HERE / "data" / "history_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # figure: duration histograms, one panel per run
    fig, axes = plt.subplots(len(dists), 1, figsize=(9, 1.45 * len(dists) + 0.9), sharex=True)
    bins = [x * 0.5 for x in range(0, 65)]
    for ax, (label, model, change, d), row in zip(axes, dists, rows):
        ax.axvspan(2, 15, color=BAND, zorder=0)
        ax.hist([min(x, 31.9) for x in d], bins=bins, color=BLUE, edgecolor=SURFACE, linewidth=0.6, zorder=2)
        long = sorted(x for x in d if x > 15)
        ax.scatter(long, [14 + 18 * (i % 2) for i in range(len(long))], s=22, color=INK, zorder=3)
        ax.set_ylim(0, 120)
        ax.set_yticks([0, 50, 100])
        ax.text(1.0, 0.92, f"{row['segments']} segments · median {row['median_min']:.1f} min · "
                f"{row['over_15']} over 15 min · longest {row['longest_min']:.0f} min",
                transform=ax.transAxes, ha="right", va="top", fontsize=9, color=INK2)
        ax.set_title(f"{label}: {model}, {change}", loc="left", fontsize=10, color=INK, pad=3)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(axis="y", length=0, labelsize=8, labelcolor=INK2)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[-1].set_xlim(0, 32)
    axes[-1].set_xticks([0, 2, 5, 10, 15, 20, 25, 30])
    axes[-1].set_xlabel("segment duration (minutes); shaded: 2–15 min; a dot: one segment over 15 min")
    fig.suptitle("Segment durations in the VR course (63 lectures), run by run", x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(HERE / "figures" / "history_durations.png", dpi=160)
    return rows


# ---------------------------------------------------------------------------- run-to-run
def seed_dirs() -> dict[int, Path]:
    """Seed 0 is the pipeline's own outputs for the sample lectures, copied into data/runs/seed_0/."""
    s0 = RUNS / "seed_0"
    shutil.rmtree(s0, ignore_errors=True)
    for stage, subs in (("stage_1a_segmentation", ("raw",)), ("stage_1b_verify_segments", ("segment_maps", "retry"))):
        for sub in subs:
            (s0 / stage / sub).mkdir(parents=True)
            for n in LECTURES:
                p = MAIN / stage / sub / f"{lec.stem_of(n)}.json"
                if p.exists():
                    shutil.copy(p, s0 / stage / sub / p.name)
    report = json.loads((MAIN / "stage_1b_verify_segments" / "report.json").read_text())
    (s0 / "stage_1b_verify_segments" / "report.json").write_text(
        json.dumps({lec.stem_of(n): report[lec.stem_of(n)] for n in LECTURES}, indent=1) + "\n")
    return {int(p.name.split("_")[1]): p for p in sorted(RUNS.glob("seed_*"))}


def boundary_f1(a: list[int], b: list[int], tol: int = TOL) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    p = sum(any(abs(x - y) <= tol for y in b) for x in a) / len(a)
    r = sum(any(abs(y - x) <= tol for x in a) for y in b) / len(b)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def window_diff(a: list[int], b: list[int], n: int) -> float:
    """WindowDiff (Pevzner & Hearst 2002) between two segmentations of n sentences; k = half the mean segment
    length of the reference a. 0 = identical."""
    k = max(1, round(n / (len(a) + 1) / 2))
    ba, bb = set(a), set(b)
    count = lambda bs, i: sum(1 for x in bs if i < x <= i + k)  # noqa: E731
    return sum(count(ba, i) != count(bb, i) for i in range(n - k)) / (n - k)


def run_to_run():
    seeds = seed_dirs()
    stages = {"1a": {s: segs_from_raw(p / "stage_1a_segmentation" / "raw") for s, p in seeds.items()},
              "1b": {s: segs_from_map(p / "stage_1b_verify_segments" / "segment_maps") for s, p in seeds.items()}}
    pairs, per_lecture = [], []
    for stage, by_seed in stages.items():
        for n in LECTURES:
            have = [s for s in seeds if n in by_seed[s]]
            counts = [len(by_seed[s][n]) for s in have]
            durs = [minutes(n, x) for s in have for x in by_seed[s][n]]
            f1s, wds = [], []
            for a, b in itertools.combinations(have, 2):
                ca, cb = cuts(n, by_seed[a][n]), cuts(n, by_seed[b][n])
                f1, wd = boundary_f1(ca, cb), (window_diff(ca, cb, len(timing(n).ids)) +
                                               window_diff(cb, ca, len(timing(n).ids))) / 2
                f1s.append(f1)
                wds.append(wd)
                pairs.append({"stage": stage, "lecture": n, "seed_a": a, "seed_b": b, "segments_a": len(ca) + 1,
                              "segments_b": len(cb) + 1, "boundary_f1": round(f1, 3), "window_diff": round(wd, 3)})
            per_lecture.append({"stage": stage, "lecture": n, "seeds": len(have), "segments_min": min(counts),
                                "segments_max": max(counts), "segments_mean": round(st.mean(counts), 1),
                                "boundary_f1_mean": round(st.mean(f1s), 3), "window_diff_mean": round(st.mean(wds), 3),
                                "flagged": sum(m > 15 for m in durs), "longest_min": round(max(durs), 1)})
    for name, rows in (("run_to_run_pairs.csv", pairs), ("run_to_run_lectures.csv", per_lecture)):
        with open(HERE / "data" / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    fig_barcode(stages["1b"], seeds)
    fig_agreement(per_lecture)
    return seeds, stages, pairs, per_lecture


def fig_barcode(by_seed: dict, seeds: dict):
    """One panel per lecture: a row per seed, a tick at each cut (minutes into the lecture)."""
    cols = 3
    rows = (len(LECTURES) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(11, 1.25 * rows + 0.8))
    for ax, n in zip(axes.flat, LECTURES):
        t = timing(n)
        total = t.after(len(t.ids) - 1)[0] / 60
        for r, s in enumerate(sorted(seeds)):
            if n not in by_seed[s]:
                continue
            segs = by_seed[s][n]
            xs = [t.before(t.ids.index(x[0]))[0] / 60 for x in segs[1:]]
            ax.plot([0, total], [r, r], color=GRID, linewidth=1, zorder=1)
            ax.vlines(xs, r - 0.32, r + 0.32, color=BLUE, linewidth=2, zorder=2)
        ax.set_xlim(0, total)
        ax.set_ylim(len(seeds) - 0.5, -0.5)
        ax.set_yticks(range(len(seeds)))
        ax.set_yticklabels([f"seed {s}" for s in sorted(seeds)], fontsize=7, color=INK2)
        ax.set_title(f"Lecture {n} ({total:.0f} min)", loc="left", fontsize=9, pad=2)
        ax.tick_params(length=0, labelsize=7)
        for sp in ("top", "right", "left", "bottom"):
            ax.spines[sp].set_visible(False)
    for ax in list(axes.flat)[len(LECTURES):]:
        ax.axis("off")
    fig.suptitle("Where each seed cuts (stage 1b output; x: minutes into the lecture)", x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(HERE / "figures" / "run_to_run_cuts.png", dpi=160)


def fig_agreement(per_lecture: list[dict]):
    """Mean pairwise boundary F1 per lecture, stage 1a answers vs stage 1b output."""
    fig, ax = plt.subplots(figsize=(8, 4.6))
    by = {(r["stage"], r["lecture"]): r for r in per_lecture}
    for i, n in enumerate(LECTURES):
        a, b = by[("1a", n)]["boundary_f1_mean"], by[("1b", n)]["boundary_f1_mean"]
        ax.plot([a, b], [i, i], color=GRID, linewidth=2, zorder=1)
        ax.scatter([a], [i], s=48, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
                   label="Stage 1a answers" if i == 0 else None)
        ax.scatter([b], [i], s=48, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
                   label="After stage 1b (final)" if i == 0 else None)
    for stage, color in (("1a", ORANGE), ("1b", BLUE)):
        m = st.mean(r["boundary_f1_mean"] for r in per_lecture if r["stage"] == stage)
        ax.axvline(m, color=color, linewidth=1, linestyle=(0, (3, 3)), zorder=0)
    ax.set_yticks(range(len(LECTURES)))
    ax.set_yticklabels([f"Lecture {n}" for n in LECTURES])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel(f"mean pairwise boundary F1 between seeds (cuts within {TOL} sentences count as the same; "
                  "dashed: mean)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    ax.set_title("How much the cuts agree between seeds, per lecture", loc="left", fontsize=12)
    fig.tight_layout()
    fig.savefig(HERE / "figures" / "run_to_run_agreement.png", dpi=160)


def between_runs(rows_hist):
    """Boundary F1 between consecutive runs on the same 12 lectures, to set run-to-run noise against."""
    loads = {label: load for label, _, _, load in RUN_LIST}
    sets = {k: v() for k, v in loads.items()}
    out = {}
    for a, b in (("Run 1", "Run 2"), ("Run 2", "Run 3"), ("Run 3", "Run 4"), ("Run 4", "Run 4 + 1b")):
        f = [boundary_f1(cuts(n, sets[a][n]), cuts(n, sets[b][n])) for n in LECTURES if n in sets[a] and n in sets[b]]
        out[f"{a} vs {b}"] = round(st.mean(f), 3)
    return out


def main():
    (HERE / "figures").mkdir(exist_ok=True)
    rows = history()
    for r in rows:
        print({k: v for k, v in r.items() if k not in ("model", "change")})
    print("between consecutive runs (12 sample lectures, mean boundary F1):", between_runs(rows))
    if len(list(RUNS.glob("seed_*"))) >= 1:
        seeds, stages, pairs, per_lecture = run_to_run()
        for stage in ("1a", "1b"):
            pr = [p for p in pairs if p["stage"] == stage]
            pl = [p for p in per_lecture if p["stage"] == stage]
            print(f"stage {stage}: seeds {sorted(seeds)}, pairs {len(pr)}, mean F1 {st.mean(p['boundary_f1'] for p in pr):.3f}, "
                  f"mean WindowDiff {st.mean(p['window_diff'] for p in pr):.3f}, "
                  f"segments per lecture spread (max-min) mean {st.mean(p['segments_max'] - p['segments_min'] for p in pl):.1f}")
        for p in per_lecture:
            print(p)


if __name__ == "__main__":
    main()
