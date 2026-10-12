#!/usr/bin/env python
"""Infographics for compare/results.json -> compare/figures/*.png (one story per image).

    python compare/plots.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8983", "#e4e3de"
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK, "axes.edgecolor": GRID, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.grid": False, "xtick.major.size": 0, "ytick.major.size": 0,
})


def figure(title, h, left=0.24, right=0.94, bottom=0.14):
    fig = plt.figure(figsize=(10, h))
    fig.text(0.04, 1 - 0.34 / h, title, fontsize=16, fontweight="bold", va="top")
    ax = fig.add_axes([left, bottom, right - left, 1 - bottom - 0.95 / h])
    return fig, ax


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / name, dpi=170)
    plt.close(fig)
    print("wrote", FIG / name)


def load():
    r = json.loads((HERE / "results.json").read_text())
    m = r["methods"]
    tt = min((x for x in m["texttiling"]["runs"] if x["min_seg"] > 0), key=lambda x: (x["wd"], x["pk"]))
    same = lambda runs, ref: next(x for x in runs if all(x[k] == ref[k] for k in ("window", "min_seg") if k in x))
    topic = next(x for x in m["topictiling"]["runs"] if x["window"] == 2)
    tsvlt = max(m["tsvlt"]["runs"], key=lambda x: x["stage4"]["n_boundaries"])
    # (label, colour, lighter variant?, evaluation)
    r["rows"] = [
        ("TextTiling", BLUE, False, tt),
        ("TextTiling + slides", BLUE, True, same(m["texttiling_snap"]["runs"], tt)),
        ("TopicTiling", ORANGE, False, topic),
        ("TopicTiling + slides", ORANGE, True, same(m["topictiling_snap"]["runs"], topic)),
        ("TSVLT", AQUA, False, tsvlt["stage4"]),
        ("TSVLT + slides", AQUA, True, tsvlt["stage4_snap"]),
        ("TSVLT settled", AQUA, False, min(m["tsvlt_dp"]["runs"], key=lambda x: (x["wd"], x["pk"]))),
    ]
    if "gemma" in m:
        r["rows"] += [("Gemma 4", VIOLET, False, m["gemma"]["runs"][0])]
        r["rows"] += [(f"Gemma 4 + {k}", VIOLET, False, m[f"gemma_{k}"]["runs"][0]) for k in ("merge", "fix") if f"gemma_{k}" in m]
        r["snap_pairs"] = [("Gemma 4", VIOLET, m["gemma"]["runs"][0]["wd"], m["gemma_snap"]["runs"][0]["wd"])]
    return r


LIGHT = 0.45


def hbars(ax, rows, values, labels, xmax):
    y = np.arange(len(rows))[::-1]
    for yi, (lab, col, light, _), v, t in zip(y, rows, values, labels):
        ax.barh(yi, v, height=0.56, color=col, alpha=LIGHT if light else 1.0, lw=0)
        ax.text(v + xmax * 0.012, yi, t, va="center", fontsize=11)
    ax.set_yticks(y)
    ax.set_yticklabels([lab for lab, *_ in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(0, xmax)
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])


# ----------------------------------------------------------------- 1. where the cuts fall
def timeline(r):
    rows = [("Human", INK, False, {"times": r["gold"]["times"]})] + r["rows"]
    t0, t1 = r["units"][0]["start"], r["units"][-1]["end"]
    fig, ax = figure("Where each method cuts the lecture", 8.2, right=0.87, bottom=0.13)
    for g in r["gold"]["times"]:
        ax.axvline(g / 60, color=MUTED, lw=0.9, ls=(0, (2, 3)), zorder=0)
    for i, (lab, col, light, ev) in enumerate(rows):
        y = len(rows) - 1 - i
        times = ev["times"]
        ax.barh(y, (t1 - t0) / 60, left=t0 / 60, height=0.5, color=col, alpha=0.10, lw=0)
        ax.vlines(np.array(times) / 60, y - 0.25, y + 0.25, color=col, lw=0.6 if len(times) > 100 else 2.4,
                  alpha=0.55 if light else 1.0, zorder=3)
        ax.text(t1 / 60 + 0.7, y, f"{len(times) + 1} segments", va="center", fontsize=10, color=INK2)
    ax.set_yticks(range(len(rows))[::-1])
    ax.set_yticklabels([lab for lab, *_ in rows])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(0, t1 / 60 + 0.3)
    ax.set_xticks(range(0, 35, 5))
    ax.set_xlabel("minutes")
    save(fig, "1_where_the_cuts_fall.png")


# ----------------------------------------------------------------- 2. agreement with the human
def error(r):
    rows = sorted(r["rows"], key=lambda x: x[3]["wd"])
    fig, ax = figure("Error against the human segmentation", 6.9, bottom=0.10)
    v = [x[3]["wd"] for x in rows]
    hbars(ax, rows, v, [f"{x:.2f}" for x in v], 1.12)
    none = r["baselines"]["none"]["wd"]
    ax.axvline(none, color=INK2, lw=1, ls=(0, (3, 3)), zorder=0)
    ax.text(none, len(rows) - 0.42, "no cuts at all", ha="center", va="bottom", fontsize=9.5, color=INK2)
    ax.set_xlabel("WindowDiff, lower is better")
    save(fig, "2_error_vs_human.png")


# ----------------------------------------------------------------- 3. how many segments
def counts(r):
    rows = [("Human", INK, False, {"n_boundaries": len(r["gold"]["times"])})] + r["rows"]
    fig, ax = figure("How many segments each method makes", 7.4, bottom=0.06)
    n = [x[3]["n_boundaries"] + 1 for x in rows]
    hbars(ax, rows, np.log10(n), [str(x) for x in n], 2.6)
    ax.get_yticklabels()[0].set_fontweight("bold")
    save(fig, "3_segment_counts.png")


# ----------------------------------------------------------------- 4-5. window size
def window_panels(r, key, title, name, ylabel, ylim, yticks, refs=()):
    m = r["methods"]
    fig = plt.figure(figsize=(11, 5.0))
    fig.text(0.04, 1 - 0.34 / 5.0, title, fontsize=16, fontweight="bold", va="top")
    axes = [fig.add_axes([0.08, 0.15, 0.31, 0.60]), fig.add_axes([0.57, 0.15, 0.31, 0.60])]
    val = (lambda x: x[key]) if key != "n" else (lambda x: x["n_boundaries"] + 1)

    def line(ax, runs, col, style, label, dy=0.0):
        runs = sorted(runs, key=lambda x: x["window"])
        xs, ys = [x["window"] for x in runs], [val(x) for x in runs]
        ls, fill, a = {"solid": ("-", col, 1.0), "open": ((0, (5, 3)), SURFACE, 1.0), "light": ("-", col, LIGHT)}[style]
        ax.plot(xs, ys, color=col, lw=2, ls=ls, marker="o", ms=6.5, mfc=fill, mec=col, mew=1.8, alpha=a)
        ax.annotate(label, (xs[-1], ys[-1]), xytext=(9, dy), textcoords="offset points", va="center", fontsize=9.5, color=INK2)

    ax = axes[0]
    tt, ts = m["texttiling"]["runs"], m["texttiling_snap"]["runs"]
    if key == "wd":
        line(ax, [x for x in ts if x["min_seg"] > 0], BLUE, "light", "+ slides")
        line(ax, [x for x in tt if x["min_seg"] > 0], BLUE, "solid", "default", 5)
        line(ax, [x for x in tt if x["min_seg"] == 0], BLUE, "open", "no min. segment", -7)
    else:  # snapping keeps TextTiling's segment count, so one line stands for both
        line(ax, [x for x in tt if x["min_seg"] > 0], BLUE, "solid", "default, + slides", -6)
        line(ax, [x for x in tt if x["min_seg"] == 0], BLUE, "open", "no min. segment", 8)
    ax.set_xticks([30, 60, 90, 120, 150, 180, 240, 300])
    ax.set_xlabel("TextTiling window (seconds)")
    ax.set_ylabel(ylabel)
    ax = axes[1]
    line(ax, m["topictiling"]["runs"], ORANGE, "solid", "TopicTiling")
    line(ax, m["topictiling_snap"]["runs"], ORANGE, "light", "+ slides")
    ax.set_xticks([1, 5, 10, 15, 20, 25, 30, 35])
    ax.set_xlabel("TopicTiling window (sentences)")
    ax.set_yticklabels([])
    for ax in axes:
        ax.set_ylim(*ylim)
        ax.set_yticks(yticks)
        ax.tick_params(axis="y", colors=INK2)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for v, lab in refs:
            ax.axhline(v, color=INK2, lw=1, ls=(0, (3, 3)), zorder=0)
            if ax is axes[1]:
                ax.annotate(lab, (ax.get_xlim()[1], v), xytext=(9, 0), textcoords="offset points", va="center", fontsize=9.5, color=INK2)
    axes[1].set_yticklabels([])
    save(fig, name)


def window_error(r):
    window_panels(r, "wd", "How window size affects error", "4_window_size_error.png", "WindowDiff, lower is better",
                  (0, 1.05), [0, 0.25, 0.5, 0.75, 1.0], refs=[(r["baselines"]["none"]["wd"], "no cuts")])


def window_count(r):
    window_panels(r, "n", "How window size affects the number of segments", "5_window_size_segments.png", "segments",
                  (0, 52), [0, 10, 20, 30, 40, 50], refs=[(len(r["gold"]["times"]) + 1, "human")])


# ----------------------------------------------------------------- 6. does slide snapping help
def snapping(r):
    rows = r["rows"]
    pairs = [(rows[i][0], rows[i][1], rows[i][3]["wd"], rows[i + 1][3]["wd"]) for i in (0, 2, 4)] + r.get("snap_pairs", [])
    fig, ax = figure("Does snapping to slide changes help?", 4.9, left=0.17, right=0.94, bottom=0.18)
    for i, (lab, col, a, b) in enumerate(pairs):
        y = len(pairs) - 1 - i
        ax.annotate("", xy=(b, y), xytext=(a, y), arrowprops=dict(arrowstyle="-|>", color=col, lw=2.4, shrinkA=7, shrinkB=2))
        ax.scatter([a], [y], s=110, color=SURFACE, edgecolor=col, lw=2.2, zorder=3)
        ax.text(a, y + 0.24, f"{a:.2f}", ha="center", fontsize=10.5, color=INK2)
        ax.text(b, y + 0.24, f"{b:.2f}", ha="center", fontsize=10.5, fontweight="bold")
        ax.text(b + (0.02 if b > a else -0.02), y, "worse" if b > a else "better", ha="left" if b > a else "right",
                va="center", fontsize=10, color=INK2)
    ax.set_yticks(range(len(pairs))[::-1])
    ax.set_yticklabels([p[0] for p in pairs])
    ax.set_ylim(-0.5, len(pairs) - 0.35)
    ax.set_xlim(0.15, 1.08)
    ax.set_xticks([0.25, 0.5, 0.75, 1.0])
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("WindowDiff before → after snapping, lower is better")
    save(fig, "6_slide_snapping.png")


if __name__ == "__main__":
    res = load()
    for old in FIG.glob("*.png"):
        old.unlink()
    timeline(res)
    error(res)
    counts(res)
    window_error(res)
    window_count(res)
    snapping(res)
