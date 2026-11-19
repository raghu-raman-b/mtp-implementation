"""PNG figures from summary.json (run 1): figures/correct_by_category.png, hallucinations.png, latency_vs_correct.png,
context_tokens.png. Okabe-Ito palette (colour-blind safe).

    python3 baseline-tests/figures.py
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import OUT

PAL = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
F = OUT / "figures"


def main():
    S = json.loads((OUT / "summary.json").read_text())
    systems = list(S["overall"])
    col = {s: PAL[i % len(PAL)] for i, s in enumerate(systems)}
    cats = list(S["per_category"])
    F.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    fig, ax = plt.subplots(figsize=(12, 4.8))
    w = 0.8 / len(systems)
    for i, s in enumerate(systems):
        ys = [S["per_category"][c][s]["correct"] or 0 for c in cats]
        ax.bar([k + (i - (len(systems) - 1) / 2) * w for k in range(len(cats))], ys, w, label=s, color=col[s])
    ax.set_xticks(range(len(cats)), cats)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("question category")
    ax.set_ylabel("mean correct (1 / 0.5 / 0)")
    ax.set_title("Correctness by category and system (run 1)")
    ax.legend(ncol=4, fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    fig.savefig(F / "correct_by_category.png", dpi=150)
    plt.close(fig)

    def bars(key, ylabel, title, name):
        fig, ax = plt.subplots(figsize=(8, 4))
        ys = [S["overall"][s][key] or 0 for s in systems]
        ax.bar(systems, ys, color=[col[s] for s in systems])
        for k, y in enumerate(ys):
            ax.text(k, y, f"{y:g}", ha="center", va="bottom", fontsize=8)
        ax.set_xlabel("system")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
        fig.tight_layout()
        fig.savefig(F / name, dpi=150)
        plt.close(fig)

    bars("hallucinations", "hallucinated claims (count, 65 questions)", "Hallucinations per system (run 1)",
         "hallucinations.png")
    bars("context_tokens_median", "median context tokens per question", "Context size per system (run 1)",
         "context_tokens.png")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for s in systems:
        b = S["overall"][s]
        if b["latency_median_s"] is None:
            continue
        ax.scatter(b["latency_median_s"], b["correct"], s=60, color=col[s], label=s, edgecolor="black", linewidth=0.5)
        ax.annotate(s, (b["latency_median_s"], b["correct"]), textcoords="offset points", xytext=(6, 4), fontsize=8)
    ax.set_xlabel("median latency per question (s)")
    ax.set_ylabel("mean correct (1 / 0.5 / 0)")
    ax.set_title("Latency vs correctness (run 1)")
    fig.tight_layout()
    fig.savefig(F / "latency_vs_correct.png", dpi=150)
    plt.close(fig)
    print("figures in", F)


if __name__ == "__main__":
    main()
