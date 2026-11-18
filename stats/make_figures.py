"""Figures for stats/REPORT.md from stats/lecture_stats.csv -> stats/figures/*.png|pdf

Usage: python stats/make_figures.py   (run compute_stats.py first)
"""
import csv
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import scienceplots  # noqa: F401  (registers the 'science' styles)

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

plt.style.use(["science"])
matplotlib.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300,
    "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b",
    "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.grid": True, "axes.grid.axis": "x", "grid.color": "#e4e3df", "grid.linewidth": 0.5,
    "axes.axisbelow": True, "legend.frameon": False,
    "ytick.minor.visible": False, "ytick.major.size": 0,
})

COLOR = {"NPTEL": "#2a78d6", "MIT": "#eb6834"}   # validated categorical slots 1-2
INK, INK2 = "#0b0b0b", "#52514e"
ORDER = ["VR/AR", "Intro ML", "C Prog.", "Lin. Alg.", "Psychology", "Deep Learn."]

rows = list(csv.DictReader(open(HERE / "lecture_stats.csv", encoding="utf-8")))
PROVIDER = {r["short"]: r["provider"] for r in rows}
rng = np.random.default_rng(0)


def tex(s):
    return s.replace("%", r"\%").replace("&", r"\&")


def vals(course, key):
    return np.array([float(r[key]) for r in rows if r["short"] == course])


def ypos():
    # NPTEL on top, a small gap, then MIT
    return {c: (len(ORDER) - i + (0.6 if PROVIDER[c] == "NPTEL" else 0)) for i, c in enumerate(ORDER)}


def course_axis(ax):
    y = ypos()
    ax.set_yticks([y[c] for c in ORDER], [tex(c) for c in ORDER])
    ax.set_ylim(min(y.values()) - 0.7, max(y.values()) + 0.7)


def provider_legend(ax, loc="lower right"):
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", ms=5, color=COLOR[p], label=p) for p in COLOR]
    ax.legend(handles=h, loc=loc, handletextpad=0.2, borderaxespad=0.3)


def boxstrip(ax, key, xlabel, fmt="{:.0f}", label_median=True):
    """Per-course distribution: thin box (IQR, median) + jittered lecture dots."""
    y = ypos()
    for c in ORDER:
        v = vals(c, key)
        col = COLOR[PROVIDER[c]]
        ax.scatter(v, y[c] + rng.uniform(-0.18, 0.18, len(v)), s=7, color=col, alpha=0.55,
                   linewidths=0, zorder=3)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        ax.add_patch(matplotlib.patches.FancyBboxPatch(
            (q1, y[c] - 0.3), max(q3 - q1, 1e-9), 0.6, boxstyle="round,pad=0,rounding_size=0.04",
            fc="none", ec=col, lw=1.0, zorder=4))
        ax.plot([med, med], [y[c] - 0.3, y[c] + 0.3], color=INK, lw=1.4, zorder=5)
        if label_median:
            ax.annotate(fmt.format(med), (med, y[c] + 0.32), ha="center", va="bottom", fontsize=6.5,
                        color=INK2)
    course_axis(ax)
    ax.set_xlabel(tex(xlabel))


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# 1. lecture length ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.6, 2.7))
boxstrip(ax, "duration_min", "Lecture length (minutes)")
ax.set_xlim(0, None)
provider_legend(ax, loc="upper right")
save(fig, "fig1_lecture_length")

# 2. speaking rate ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.6, 2.7))
boxstrip(ax, "wpm", "Speaking rate (words per minute)")
provider_legend(ax, loc="lower left")
save(fig, "fig2_speaking_rate")

# 3. words vs duration ------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.6, 2.8))
xmax = max(float(r["duration_min"]) for r in rows) * 1.05
ymax = 21
for rate in (100, 150, 200):  # iso-rate guides: words = rate x minutes
    x_end = min(xmax, ymax * 1000 / rate)
    ax.plot([0, x_end], [0, rate * x_end / 1000], color="#c9c8c3", lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.annotate(f"{rate} wpm", (x_end, rate * x_end / 1000), xytext=(-2, -2), textcoords="offset points",
                fontsize=6, color=INK2, ha="right", va="top")
for p in COLOR:
    pts = [(float(r["duration_min"]), int(r["words"]) / 1000) for r in rows if r["provider"] == p]
    ax.scatter(*zip(*pts), s=10, color=COLOR[p], alpha=0.8, linewidths=0.4, edgecolors="white", label=p,
               zorder=3)
ax.set_xlim(0, xmax)
ax.set_ylim(0, ymax)
ax.set_xlabel("Lecture length (minutes)")
ax.set_ylabel("Words per lecture (thousands)")
ax.grid(axis="both")
ax.legend(loc="upper left", handletextpad=0.2)
save(fig, "fig3_words_vs_length")

# 4. interaction ------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
boxstrip(axes[0], "questions_per_1k", "Question marks per 1,000 words", fmt="{:.1f}")
boxstrip(axes[1], "audience_turns_per_hour", "Audience turns per hour", fmt="{:.1f}")
boxstrip(axes[2], "you_per_1k", "``you'' per 1,000 words", fmt="{:.0f}")
for a in axes:
    a.set_xlim(0, None)
axes[0].set_yticks(axes[0].get_yticks(), [tex(c) + (r"$^\dagger$" if c == "Intro ML" else "") for c in ORDER])
for a, t in zip(axes, "abc"):
    a.set_title(f"({t})", loc="left", fontsize=8, color=INK2)
provider_legend(axes[1], loc="upper right")
fig.tight_layout(w_pad=0.8)
save(fig, "fig4_interaction")

# 5. discourse profile (dumbbell, provider medians) -------------------------------
markers = [("i", "I / me / my"), ("we", "we / us / our"), ("you", "you / your"), ("so", "so"),
           ("okay", "okay"), ("right", "right"), ("yeah", "yeah / yes")]
fig, ax = plt.subplots(figsize=(3.6, 2.6))
for i, (k, lab) in enumerate(markers):
    yy = len(markers) - i
    med = {p: np.median([float(r[f"{k}_per_1k"]) for r in rows if r["provider"] == p]) for p in COLOR}
    ax.plot([med["NPTEL"], med["MIT"]], [yy, yy], color="#c9c8c3", lw=1.2, zorder=1)
    for p in COLOR:
        ax.scatter(med[p], yy, s=28, color=COLOR[p], zorder=3, linewidths=1, edgecolors="white",
                   label=p if i == 0 else None)
ax.set_yticks(range(len(markers), 0, -1), [m[1] for m in markers])
ax.set_xlabel("Median occurrences per 1,000 words")
ax.set_xlim(0, None)
ax.legend(loc="lower right", handletextpad=0.2)
save(fig, "fig5_discourse_markers")

# 6. lecture framing --------------------------------------------------------------
fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.4), sharey=True)
specs = [("opens_with_greeting", "Opens with greeting (\\%)", 100, "{:.0f}"),
         ("closes_with_signoff", "Closes with sign-off (\\%)", 100, "{:.0f}"),
         ("backward_refs", "Refs to earlier lectures", 1, "{:.1f}"),
         ("forward_refs", "Refs to later lectures", 1, "{:.1f}")]
y = ypos()
for a, (k, lab, scale, fmt) in zip(axes, specs):
    for c in ORDER:
        v = vals(c, k).mean() * scale
        a.barh(y[c], v, height=0.62, color=COLOR[PROVIDER[c]], zorder=3)
        a.annotate(fmt.format(v), (v, y[c]), xytext=(2, 0), textcoords="offset points", va="center",
                   fontsize=6.5, color=INK2)
    a.set_xlabel(lab)
    a.set_xlim(0, (105 if scale == 100 else None))
    course_axis(a)
axes[2].set_xlim(0, 1.6)
axes[3].set_xlim(0, 1.6)
axes[2].set_xlabel("Refs to earlier lectures\n(mean per lecture)")
axes[3].set_xlabel("Refs to later lectures\n(mean per lecture)")
from matplotlib.lines import Line2D
fig.tight_layout(w_pad=0.6)
fig.legend(handles=[Line2D([], [], marker="s", ls="", ms=5, color=COLOR[p], label=p) for p in COLOR],
           loc="lower center", bbox_to_anchor=(0.5, 0.98), ncol=2, handletextpad=0.2, columnspacing=1.2)
save(fig, "fig6_lecture_framing")

# 7. caption granularity ----------------------------------------------------------
for r in rows:
    r["sec_per_cue"] = str(float(r["duration_min"]) * 60 / int(r["cues"]))
fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.6), sharey=True)
boxstrip(axes[0], "sec_per_cue", "Seconds per cue", fmt="{:.1f}")
boxstrip(axes[1], "words_per_cue", "Words per cue", fmt="{:.1f}")
for a, t in zip(axes, "ab"):
    a.set_xlim(0, None)
    a.set_title(f"({t})", loc="left", fontsize=8, color=INK2)
provider_legend(axes[1])
fig.tight_layout(w_pad=0.8)
save(fig, "fig7_caption_granularity")
