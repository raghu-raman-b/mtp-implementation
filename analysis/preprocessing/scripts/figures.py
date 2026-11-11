"""Figures for the preprocessing report (from analysis/preprocessing/data/).

    python analysis/preprocessing/scripts/figures.py
"""
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {"forward": "#2a78d6", "sentences": "#eb6834", "cue": "#1baf7a"}
LABELS = {"forward": "Forward from the nearest exact time", "sentences": "Both sides, nearest exact sentence times",
          "cue": "Both sides, edges of the cue (adopted)"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK, "text.color": INK, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def boundary_errors():
    rows = list(csv.DictReader(open(HERE / "data" / "boundary_time_errors.csv")))
    courses = list(dict.fromkeys(r["course"] for r in rows))
    err = defaultdict(list)
    for r in rows:
        err[(r["course"], r["method"])].append(float(r["error_s"]))
    n = {c: len(err[(c, "cue")]) for c in courses}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, (title, q) in zip(axes, (("Median error", 0.5), ("90th percentile error", 0.9))):
        for k, m in enumerate(SERIES):
            xs = [sorted(err[(c, m)])[int(q * (len(err[(c, m)]) - 1))] for c in courses]
            ys = [i + (k - 1) * 0.22 for i in range(len(courses))]
            ax.scatter(xs, ys, s=46, color=SERIES[m], edgecolor=SURFACE, linewidth=1.5, zorder=3, label=LABELS[m])
        ax.set_xscale("log")
        ax.set_xlim(0.1, 60)
        ax.set_xticks([0.1, 0.3, 1, 3, 10, 30])
        ax.set_xticklabels(["0.1", "0.3", "1", "3", "10", "30"])
        ax.minorticks_off()
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(range(len(courses)))
    axes[0].set_yticklabels([f"{c}  (n={n[c]:,})" for c in courses])
    axes[0].invert_yaxis()
    fig.supxlabel("seconds between the estimate and the boundary's place in its cue (log scale)", fontsize=10,
                  color=INK2, y=0.09)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.suptitle("Estimated time of a sentence boundary inside a subtitle cue, by method", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.11, 1, 0.95))
    fig.savefig(HERE / "figures" / "boundary_time_error.png", dpi=160)


if __name__ == "__main__":
    (HERE / "figures").mkdir(exist_ok=True)
    boundary_errors()
