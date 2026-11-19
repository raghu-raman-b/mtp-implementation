"""Paper-ready figures for every test of the project so far.

Run from the repository root:  pipeline/results/.venv/bin/python pipeline/results/make_graphs.py [figure_function_name ...]
Reads existing result files only (no model calls); writes pipeline/results/<study>/<figure>.{pdf,png}.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scienceplots  # noqa: F401  (registers the 'science' style)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
A = ROOT / "analysis"
B = ROOT / "baseline-tests"

plt.style.use(["science", "no-latex"])
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8.5, "legend.fontsize": 7.5,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "axes.titlepad": 8, "axes.labelpad": 4,
    "legend.frameon": False, "savefig.dpi": 300, "figure.dpi": 150, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.06,
})
W1, W2 = 3.5, 7.0  # single / double column widths (inches)

# Okabe-Ito, colour-blind safe
C = dict(blue="#0072B2", orange="#E69F00", green="#009E73", sky="#56B4E9", verm="#D55E00",
         pink="#CC79A7", yellow="#F0E442", grey="#7F7F7F", purple="#6A3D9A", black="#222222")

SYS = ["ours_v2", "ours_v2_nothink", "plain", "rag", "rag_think", "graphrag_text", "graphrag_notext", "abl_facts", "abl_graph"]
SYS_NAME = {
    "ours_v2": "Proposed (knowledge layer)", "ours_v2_nothink": "Proposed (no reasoning)", "plain": "Plain LLM", "rag": "RAG",
    "rag_think": "RAG + reasoning", "graphrag_text": "GraphRAG (with text units)",
    "graphrag_notext": "GraphRAG (without text units)", "abl_facts": "Ablation: fact retrieval only",
    "abl_graph": "Ablation: graph tools only",
}
SYS_COL = {"ours_v2": C["verm"], "ours_v2_nothink": C["black"], "plain": C["grey"], "rag": C["blue"], "rag_think": C["sky"],
           "graphrag_text": C["green"], "graphrag_notext": C["pink"], "abl_facts": C["orange"],
           "abl_graph": C["purple"]}
HEAT_LAB = {"ours_v2": "Proposed\n(knowledge\nlayer)", "ours_v2_nothink": "Proposed\n(no\nreasoning)", "plain": "Plain\nLLM", "rag": "RAG", "rag_think": "RAG +\nreasoning",
            "graphrag_text": "GraphRAG\n(with text\nunits)", "graphrag_notext": "GraphRAG\n(without text\nunits)",
            "abl_facts": "Ablation:\nfact retrieval\nonly", "abl_graph": "Ablation:\ngraph tools\nonly"}
CAT_NAME = {"definition": "Definition", "explanation": "Explanation", "comparison": "Comparison",
            "list": "List", "formula": "Formula", "where": "Where taught", "prerequisite": "Prerequisite",
            "structure": "Structure", "not_covered": "Not covered", "multihop": "Multi-hop"}

ACT_SYS = ["ours", "ours_gemma", "b2", "b1"]
ACT_NAME = {"ours": "Proposed", "ours_gemma": "Proposed, same model",
            "b2": "Baseline: pipeline prompts on transcript", "b1": "Baseline: transcript prompt"}
ACT_COL = {"ours": C["verm"], "ours_gemma": C["orange"], "b2": C["blue"], "b1": C["sky"]}
KIND_NAME = {"quiz": "Quiz", "recap": "Recap", "open_question": "Open question",
             "odd_one_out": "Odd one out", "put_in_order": "Put in order",
             "concept_map": "Concept map", "recall": "Recall"}


def jload(p):
    return json.load(open(p))


def save(fig, study, name):
    d = HERE / study
    d.mkdir(exist_ok=True)
    fig.savefig(d / f"{name}.pdf")
    fig.savefig(d / f"{name}.png", dpi=300)
    plt.close(fig)
    print("wrote", study, name)


def clean(ax, grid="y"):
    ax.tick_params(which="minor", length=0)
    if grid:
        ax.grid(axis=grid, lw=0.4, alpha=0.5)
        ax.set_axisbelow(True)


def panel(ax, s):
    ax.text(-0.02, 1.04, s, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="right")


# ============================================================ segmentation
def seg_vs_human():
    """Window Difference against the human annotator on lecture 1, per method (parsed from REPORT.md)."""
    txt = open(ROOT / "event-segmentation/compare/REPORT.md").read()
    rows = {}
    for ln in txt.splitlines():
        if ln.startswith("|") and not ln.startswith("|---") and "Method" not in ln:
            c = [x.strip().strip("*") for x in ln.strip("|").split("|")]
            if len(c) >= 7 and c[3] not in ("",):
                try:
                    rows[(c[0], c[1])] = (int(c[2]), float(c[3]))
                except ValueError:
                    pass
    pick = [
        ("Gemma 4", "single pass, standalone-segments prompt, temperature 0", "LLM, final prompt"),
        ("Gemma 4, first prompt", "single pass, original wording", "LLM, first prompt"),
        ("Gemma 4 + validation (fix)", "failed cuts moved to a concluded point", "LLM + validation, move"),
        ("Gemma 4 + validation (merge)", "failed cuts dropped", "LLM + validation, drop"),
        ("TextTiling", "W=240 s, min segment 360 s (best window)", "TextTiling, best window"),
        ("TextTiling", "W=180 s, min segment 360 s (current default)", "TextTiling, default"),
        ("TSVLT settled", "stage-2 scores + min segment 240 s (not a default)", "TSVLT, minimum segment"),
        ("TopicTiling", "w=2 sentences", "TopicTiling"),
        ("TSVLT", "as trained, default settings", "TSVLT, as trained"),
        ("Seven equal slices", "baseline", "Baseline: seven equal slices"),
        ("No cuts", "baseline", "Baseline: no cuts"),
    ]
    data = [(lab, *rows[(m, s)]) for m, s, lab in pick if (m, s) in rows]
    assert len(data) == len(pick), "REPORT.md table changed"
    data.sort(key=lambda r: r[2])
    fig, ax = plt.subplots(figsize=(W1 + 0.6, 3.2))
    y = np.arange(len(data))
    cols = [C["verm"] if r[0].startswith("LLM") else (C["grey"] if r[0].startswith("Baseline") else C["blue"])
            for r in data]
    ax.barh(y, [r[2] for r in data], color=cols, height=0.65)
    for yi, r in zip(y, data):
        ax.text(r[2] + 0.015, yi, f"{r[2]:.2f} · {r[1]} segment" + ("" if r[1] == 1 else "s"), va="center", fontsize=7)
    ax.set_yticks(y, [r[0] for r in data])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.6)
    ax.set_xlabel("WindowDiff vs. human annotator")
    ax.set_title("Lecture 1 segmentation")
    clean(ax, "x")
    save(fig, "segmentation", "vs_human_lecture1")


def seg_history():
    """Segment-length profile of the four design runs (history_runs.csv)."""
    rows = list(csv.DictReader(open(A / "segmentation/data/history_runs.csv")))
    names = ["Run 1\n4B", "Run 2\n4B", "Run 3\n12B", "Run 4\n12B", "Run 4\nverified"]
    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.5))
    x = np.arange(len(rows))
    cols = [C["grey"]] * 4 + [C["verm"]]
    spec = [("median_min", "Median segment duration (min)", "Median duration"),
            ("under_2", "Segments under 2 min", "Too short"),
            ("over_15", "Segments over 15 min", "Too long")]
    for a, (k, yl, t), s in zip(axs, spec, "abc"):
        v = [float(r[k]) for r in rows]
        a.bar(x, v, color=cols, width=0.65)
        for xi, vi in zip(x, v):
            a.text(xi, vi, f"{vi:g}", ha="center", va="bottom", fontsize=6.5)
        a.set_ylabel(yl)
        a.set_title(t)
        a.set_xticks(x, names, fontsize=6.5)
        a.set_ylim(0, max(v) * 1.15)
        clean(a)
        panel(a, s)
    fig.tight_layout(w_pad=1.5)
    save(fig, "segmentation", "design_runs_profile")


def seg_run_to_run():
    """Boundary F1 between seeds per lecture, before and after verification."""
    rows = list(csv.DictReader(open(A / "segmentation/data/run_to_run_lectures.csv")))
    by = defaultdict(dict)
    for r in rows:
        by[int(r["lecture"])][r["stage"]] = float(r["boundary_f1_mean"])
    lecs = sorted(by, key=lambda l: by[l]["1b"])
    fig, ax = plt.subplots(figsize=(W1, 3.2))
    y = np.arange(len(lecs))
    for yi, l in zip(y, lecs):
        ax.plot([by[l]["1a"], by[l]["1b"]], [yi, yi], color="#BBBBBB", lw=1, zorder=1)
    ax.scatter([by[l]["1a"] for l in lecs], y, color=C["grey"], s=22, zorder=2, label="Before verification")
    ax.scatter([by[l]["1b"] for l in lecs], y, color=C["verm"], s=22, zorder=3, label="After verification")
    ax.set_yticks(y, [f"Lecture {l}" for l in lecs])
    ax.set_xlim(0.2, 1.05)
    ax.set_xlabel("Boundary F1 between seeds")
    ax.set_title("Segmentation reproducibility")
    ax.legend(loc="lower right", fontsize=6.5)
    clean(ax, "x")
    save(fig, "segmentation", "run_to_run_f1")


# ============================================================ preprocessing
def prep_pysbd():
    rows = list(csv.DictReader(open(A / "preprocessing/data/pysbd_comparison.csv")))
    fig, ax = plt.subplots(figsize=(W1 + 0.4, 2.8))
    y = np.arange(len(rows))
    both = np.array([int(r["agree"]) for r in rows], float)
    oo = np.array([int(r["only_ours"]) for r in rows], float)
    op = np.array([int(r["only_pysbd"]) for r in rows], float)
    tot = both + oo + op
    for arr, left, col, lab in [(both, 0 * both, C["blue"], "Both"),
                                (oo, both, C["green"], "Proposed only"),
                                (op, both + oo, C["orange"], "pySBD only")]:
        ax.barh(y, arr / tot * 100, left=left / tot * 100, color=col, label=lab, height=0.65)
    ax.set_yticks(y, [r["course"] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Sentence boundaries (%)")
    ax.set_title("Sentence splitting vs. pySBD")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.45, -0.22), fontsize=6.5, columnspacing=0.8,
              handletextpad=0.4)
    clean(ax, "x")
    save(fig, "preprocessing", "sentence_split_vs_pysbd")


def prep_time_error():
    rows = list(csv.DictReader(open(A / "preprocessing/data/boundary_time_errors.csv")))
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r["course"]][r["method"]].append(float(r["error_s"]))
    courses = list(by)
    meth = [("cue", "Cue edges only", C["grey"]), ("sentences", "Sentence interpolation", C["blue"]),
            ("forward", "Speaking-rate estimate", C["verm"])]
    fig, axs = plt.subplots(2, 3, figsize=(W2, 4.0), sharex=True, sharey=True)
    for ax, c, s in zip(axs.flat, courses, "abcdef"):
        for k, lab, col in meth:
            v = np.sort(by[c][k])
            if len(v):
                ax.plot(v, np.arange(1, len(v) + 1) / len(v), color=col, lw=1.2, label=lab)
        ax.set_title(c, fontsize=8)
        ax.set_xlim(0, 3)
        clean(ax, "both")
        panel(ax, s)
    for ax in axs[1]:
        ax.set_xlabel("Absolute time error (s)")
    for ax in axs[:, 0]:
        ax.set_ylabel("Cumulative share of boundaries")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(h_pad=1.2, rect=(0, 0.04, 1, 1))
    save(fig, "preprocessing", "boundary_time_error_cdf")


# ============================================================ fact judge / extraction
def factjudge_seeded():
    d = jload(A / "fact_judge/compare.json")["runs"]
    props = ["Significant", "Whole", "Established", "Grounded", "Self-contained", "Terms in full", "On the subject", "Faithful"]
    runs = [("base", "Run 1", C["verm"]), ("seed1", "Run 2", C["blue"]), ("seed2", "Run 3", C["sky"])]
    fig, ax = plt.subplots(figsize=(W2 * 0.8, 2.8))
    x = np.arange(8)
    w = 0.26
    for i, (k, lab, col) in enumerate(runs):
        pp = d[k]["seeded"]["per_property"]
        v = [pp[str(j)]["caught"] / pp[str(j)]["entries"] * 100 for j in range(1, 9)]
        ax.bar(x + (i - 1) * w, v, w, color=col, label=lab)
    ax.set_xticks(x, [f"{i + 1}. {p}" for i, p in enumerate(props)], rotation=25, ha="right")
    ax.set_ylabel("Seeded errors caught (%)")
    ax.set_ylim(0, 115)
    ax.set_title("Fact judge: seeded errors by property")
    ax.legend(ncol=3, loc="upper center", fontsize=7)
    clean(ax)
    save(fig, "fact_judge", "seeded_errors_by_property")


def factjudge_gold():
    d = jload(A / "fact_judge/compare.json")["runs"]
    runs = [("base", "Run 1"), ("seed1", "Run 2"), ("seed2", "Run 3")]
    fig, axs = plt.subplots(1, 2, figsize=(W1 + 1.0, 2.6))
    caught = []
    fa = []
    for k, _ in runs:
        g = d[k]["gold"]["judge_all"]
        nf = len(g["caught"]) + len(g["missed"])
        npass = len(g["false_alarm"]) + len(g["agree_pass"])
        caught.append(len(g["caught"]) / nf * 100)
        fa.append(len(g["false_alarm"]) / npass * 100)
    xs = np.arange(3)
    axs[0].bar(xs, caught, color=C["verm"], width=0.6)
    axs[1].bar(xs, fa, color=C["blue"], width=0.6)
    for a, v, t, s in [(axs[0], caught, "Real failures caught (%)", "a"), (axs[1], fa, "False alarms on good facts (%)", "b")]:
        a.set_xticks(xs, [r[1] for r in runs])
        a.set_ylabel(t)
        a.set_ylim(0, 100)
        for xi, vi in zip(xs, v):
            a.text(xi, vi + 1.5, f"{vi:.0f}", ha="center", fontsize=7)
        clean(a)
        panel(a, s)
    axs[0].set_title("Gold failures, n = 7", fontsize=8)
    axs[1].set_title("Gold passes, n = 55", fontsize=8)
    fig.suptitle("Fact judge against the hand-labelled reference", fontsize=9, y=0.99)
    fig.tight_layout(w_pad=2)
    save(fig, "fact_judge", "gold_reference")


def factjudge_materials():
    txt = open(A / "fact_extraction/data/judge_test/report.md").read()
    rows = {}
    for m in re.finditer(r"^\| (evidence|segment) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|", txt, re.M):
        rows.setdefault(m.group(1), [int(m.group(i)) for i in (2, 3, 4, 5, 6)])
    fig, ax = plt.subplots(figsize=(W1, 2.6))
    x = np.arange(3)
    w = 0.36
    for i, (k, lab, col) in enumerate([("evidence", "Cited evidence", C["blue"]), ("segment", "Whole segment", C["orange"])]):
        ax.bar(x + (i - .5) * w, rows[k][:3], w, color=col, label=lab)
    ax.set_xticks(x, ["Seed 0", "Seed 1", "Seed 2"])
    ax.set_ylabel("Facts failed")
    ax.set_title("Fact judge on lecture 1")
    ax.legend(loc="upper right", fontsize=7)
    ax.set_ylim(0, 11)
    clean(ax)
    save(fig, "fact_judge", "judge_material_by_seed")


# ============================================================ activities (pipeline trial)
def act_trial():
    c = jload(A / "activities/trial_v3_lectures_1_4_16/checks.json")["totals"]["judge"]["failed"]
    items = sorted(c.items(), key=lambda kv: kv[1])
    lab = [k.replace("_", " ").replace(".", ": ") for k, _ in items]
    fig, ax = plt.subplots(figsize=(W1, 3.0))
    ax.barh(lab, [v for _, v in items], color=C["blue"], height=0.65)
    ax.set_xlabel("Items failed")
    ax.set_title("Activity judge: failed criteria", fontsize=8.5)
    clean(ax, "x")
    save(fig, "activities", "trial_failed_criteria")


# ============================================================ activities study
def _act():
    return jload(B / "activities_study/out/summary.json")


def actstudy_gemma_pass():
    a = _act()["gemma_judge"]
    kinds = ["quiz", "recap", "open_question", "odd_one_out", "put_in_order"]
    fig, ax = plt.subplots(figsize=(W2, 2.7))
    x = np.arange(len(kinds))
    w = 0.2
    for i, s in enumerate(ACT_SYS):
        v = [a[f"{k}/{s}"]["pass"] / a[f"{k}/{s}"]["n"] * 100 for k in kinds]
        ax.bar(x + (i - 1.5) * w, v, w, color=ACT_COL[s], label=ACT_NAME[s])
    ax.set_xticks(x, [f"{KIND_NAME[k]}\nn = {a[f'{k}/ours']['n']}" for k in kinds])
    ax.set_ylabel("Pass rate (%)")
    ax.set_ylim(0, 135)
    ax.set_yticks(range(0, 101, 20))
    ax.set_title("Pipeline-judge pass rate by activity kind")
    ax.legend(ncol=2, loc="upper right", fontsize=7)
    clean(ax)
    save(fig, "activities_study", "pipeline_judge_pass_rate")


def actstudy_sonnet():
    a = _act()["sonnet"]
    kinds = ["quiz", "recap", "open_question", "odd_one_out", "put_in_order", "concept_map", "recall"]
    mets = [("correct", "n", "Correct", None), ("grounded_yes", "n", "Grounded in the lecture", None),
            ("d_good", "d_n", "Good distractors", ["quiz", "odd_one_out"]),
            ("goals_yes", "n", "Serves the lecture goals", None)]
    fig, axs = plt.subplots(2, 2, figsize=(W2, 5.0))
    for ax, (key, den, title, only), s in zip(axs.flat, mets, "abcd"):
        ks = only or kinds
        x = np.arange(len(ks))
        w = 0.2
        for i, sy in enumerate(ACT_SYS):
            v = []
            for k in ks:
                r = a[f"{k}/{sy}"]
                v.append(r[key] / r[den] * 100 if r.get(den) else np.nan)
            ax.bar(x + (i - 1.5) * w, v, w, color=ACT_COL[sy], label=ACT_NAME[sy])
        ax.set_xticks(x, [KIND_NAME[k].replace(" ", "\n", 1) if len(KIND_NAME[k]) > 9 else KIND_NAME[k] for k in ks], fontsize=7)
        ax.set_ylim(0, 105)
        ax.set_ylabel("Rated yes (%)")
        ax.set_title(title, fontsize=8.5)
        clean(ax)
        panel(ax, s)
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(h_pad=1.5, w_pad=1.5, rect=(0, 0.04, 1, 1))
    save(fig, "activities_study", "blind_ratings")


def actstudy_map_recall():
    a = _act()["sonnet"]
    sy = ["ours", "b2", "b1"]
    fig, axs = plt.subplots(1, 2, figsize=(W2, 2.9))
    x = np.arange(2)
    w = 0.26
    for i, s in enumerate(sy):
        r = a[f"concept_map/{s}"]
        axs[0].bar(x + (i - 1) * w, [r["correct"] / r["n"] * 100, r["grounded_yes"] / r["n"] * 100], w,
                   color=ACT_COL[s], label=ACT_NAME[s])
    axs[0].set_xticks(x, ["Edge correct", "Edge grounded"])
    axs[0].set_ylim(0, 125)
    axs[0].set_yticks(range(0, 101, 20))
    axs[0].set_ylabel("Edges rated yes (%)")
    axs[0].set_title("Concept-map edges", fontsize=8.5)
    axs[0].legend(loc="upper center", fontsize=6.5, ncol=1)
    x = np.arange(3)
    for i, s in enumerate(sy):
        r = a[f"recall/{s}"]
        axs[1].bar(x + (i - 1) * w, [r["grounded_yes"] / r["n"] * 100, r["grounded_no"] / r["n"] * 100,
                                     r["link_wrong"] / r["n"] * 100], w, color=ACT_COL[s])
    axs[1].set_xticks(x, ["Grounded", "Not grounded", "Wrong lecture link"])
    axs[1].set_ylim(0, 105)
    axs[1].set_ylabel("Share of items (%)")
    axs[1].set_title("Recall items", fontsize=8.5)
    for ax, s in zip(axs, "ab"):
        clean(ax)
        panel(ax, s)
    fig.tight_layout(w_pad=2)
    save(fig, "activities_study", "concept_map_and_recall")


def actstudy_layer_only():
    lo = _act()["layer_only"]["all"]
    items = [("Fact-linked activities", lo["acts_with_facts"]), ("Typed concept-map edges", lo["concept_map_typed"]),
             ("Spaced-review cards", _act()["layer_only"]["spaced_review_cards"]),
             ("Recall items", lo["recall_items"]), ("Crossword entries", lo["entries"]),
             ("Match-pairs", lo["pairs"]), ("Complete-map blanks", lo["blanks"]),
             ("Open questions on earlier lectures", lo["oq_earlier"])]
    items.sort(key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(W1 + 0.5, 2.9))
    ax.barh([k for k, _ in items], [v for _, v in items], color=C["verm"], height=0.65)
    for yi, (_, v) in enumerate(items):
        ax.text(v * 1.08, yi, f"{v:,}", va="center", fontsize=7)
    ax.set_xscale("log")
    ax.set_xlim(10, 40000)
    ax.set_xlabel("Count")
    ax.set_title("Activities only the knowledge layer supports")
    clean(ax, "x")
    save(fig, "activities_study", "layer_only_counts")


# ============================================================ QA bench (latency work)
def qa_latency_variants():
    variants = [("before", "Before optimisation"), ("after", "After optimisation"),
                ("think_old", "Reasoning, earlier layer"), ("think_newlayer", "Reasoning, current layer"),
                ("nothink", "No reasoning"), ("vllm_shipped", "vLLM, shipped"),
                ("vllm_fast", "vLLM, fast")]
    data = []
    for k, lab in variants:
        data.append(([json.loads(l)["seconds"] for l in open(A / f"qa/bench_{k}.jsonl")], lab))
    fig, ax = plt.subplots(figsize=(W1 + 1.0, 3.0))
    bp = ax.boxplot([d for d, _ in data], orientation="horizontal", widths=0.55, whis=(5, 95), showfliers=False,
                    patch_artist=True, medianprops=dict(color="black", lw=1))
    for p, (_, lab) in zip(bp["boxes"], data):
        p.set(facecolor=C["verm"] if "vLLM" in lab else C["sky"], alpha=0.8, lw=0.6)
    ax.set_yticks(range(1, len(data) + 1), [l for d, l in data])
    ax.invert_yaxis()
    ax.set_xlabel("Answer time (s)")
    ax.set_title("Answer latency by QA variant")
    clean(ax, "x")
    save(fig, "qa", "latency_by_variant")


def qa_calibration():
    c = jload(A / "qa/calibration.json")
    groups = [("in", "In the course", C["blue"]), ("partly", "Partly taught", C["orange"]),
              ("near", "Out of course, neighbouring topic", C["pink"]), ("far", "Out of course, unrelated", C["grey"])]
    sc = defaultdict(list)
    for r in c["rows"]:
        sc[r["label"] if r["label"] in ("in", "partly") else r["kind"]].append(r["score"])
    fig, ax = plt.subplots(figsize=(W1 + 0.6, 2.8))
    rng = np.random.default_rng(0)
    for i, (k, lab, col) in enumerate(groups):
        v = np.array(sc[k])
        ax.scatter(v, i + rng.uniform(-0.18, 0.18, len(v)), s=12, color=col, alpha=0.85, lw=0)
        ax.plot([np.median(v)] * 2, [i - 0.32, i + 0.32], color="black", lw=1.2)
    cut = c["score"]["cutoff"]
    ax.axvline(cut, color=C["verm"], ls="--", lw=1)
    ax.text(cut + 0.005, -0.45, f"cut-off {cut:.2f}", color=C["verm"], fontsize=7, va="bottom")
    ax.set_yticks(range(4), [lab for k, lab, _ in groups])
    ax.set_ylim(3.5, -0.7)
    ax.set_xlabel("Similarity of the best-matching fact")
    ax.set_title(f"Coverage check, AUC {c['score']['auc']:.3f}")
    clean(ax, "x")
    save(fig, "qa", "coverage_calibration")


# ============================================================ failures inventory
def failures_inventory():
    d = jload(A / "failures/inventory.json")
    rows = d["rows"]
    stage = {"act": "Activities", "con": "Concepts", "fact": "Facts", "seg": "Segments", "qa": "Question answering"}
    hand = ["fixed in the pipeline", "fixed in the viewer", "display rule", "hidden from learners", "not fixed (future work)"]
    hcol = [C["green"], C["blue"], C["sky"], C["orange"], C["grey"]]
    cnt = defaultdict(lambda: defaultdict(int))
    for r in rows:
        cnt[stage[r["id"].split(".")[0]]][r["handling"]] += 1
    st = list(stage.values())
    fig, axs = plt.subplots(1, 2, figsize=(W2, 3.4), gridspec_kw=dict(width_ratios=[1, 1.15]))
    left = np.zeros(len(st))
    for h, col in zip(hand, hcol):
        v = np.array([cnt[s][h] for s in st], float)
        axs[0].barh(st, v, left=left, color=col, label=h.replace(" (future work)", "").capitalize(), height=0.65)
        left += v
    axs[0].invert_yaxis()
    axs[0].set_xlabel("Failure kinds")
    axs[0].set_title("Failure kinds by stage", fontsize=8.5)
    axs[0].legend(loc="lower right", fontsize=6.5)
    rr = [(r["id"], r["count"] / r["denominator"] * 100, r["handling"]) for r in rows
          if r["count"] > 0 and r["denominator"] > 0 and r["id"] != "fact.2b.not_judged"]
    rr.sort(key=lambda t: -t[1])
    rr = rr[:14][::-1]
    axs[1].barh([t[0] for t in rr], [t[1] for t in rr], color=[hcol[hand.index(t[2])] for t in rr], height=0.65)
    axs[1].set_xlabel("Share of affected units (%)")
    axs[1].set_title("Most frequent failure kinds", fontsize=8.5)
    for ax, s in zip(axs, "ab"):
        clean(ax, "x")
        panel(ax, s)
    axs[1].tick_params(axis="y", labelsize=6.5)
    fig.tight_layout(w_pad=1.5)
    save(fig, "failures", "inventory_overview")


# ============================================================ baseline QA
def _bsum():
    return jload(B / "summary.json")


def bqa_correct_heatmap():
    s = _bsum()["per_category"]
    cats = list(CAT_NAME)
    M = np.array([[s[c][sy]["correct"] for sy in SYS] for c in cats])
    fig, ax = plt.subplots(figsize=(W2, 3.9))
    im = ax.imshow(M, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    for i in range(len(cats)):
        for j in range(len(SYS)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if M[i, j] > 0.62 else "black")
    ax.set_xticks(range(len(SYS)), [HEAT_LAB[x] for x in SYS], fontsize=6.5)
    ax.set_yticks(range(len(cats)), [CAT_NAME[c] for c in cats])
    ax.tick_params(length=0)
    ax.xaxis.tick_top()
    for sp in ax.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("Correctness")
    cb.outline.set_visible(False)
    fig.suptitle("Answer correctness by question category", fontsize=9, y=1.08)
    save(fig, "baseline_qa", "correctness_by_category")


def bqa_overall():
    o = _bsum()["overall"]
    fig, axs = plt.subplots(1, 2, figsize=(W2, 3.0), gridspec_kw=dict(width_ratios=[1, 1]))
    for sy in SYS:
        r = o[sy]
        axs[0].errorbar(r["latency_median_s"], r["correct"], xerr=[[0], [r["latency_p90_s"] - r["latency_median_s"]]],
                        fmt="o", color=SYS_COL[sy], ms=6, capsize=2, lw=0.8, label=SYS_NAME[sy])
    axs[0].set_xscale("log")
    axs[0].set_xlabel("Median answer time (s)")
    axs[0].set_ylabel("Correctness")
    axs[0].set_ylim(0.15, 0.9)
    axs[0].set_title("Correctness vs. answer time", fontsize=8.5)
    axs[0].set_xticks([1, 2, 5, 10, 20, 50], ["1", "2", "5", "10", "20", "50"])
    y = np.arange(len(SYS))
    claims = [o[s]["hallucinations"] for s in SYS]
    ans = [o[s]["answers_with_hallucination"] for s in SYS]
    axs[1].barh(y - 0.19, claims, 0.36, color=[SYS_COL[s] for s in SYS])
    axs[1].barh(y + 0.19, ans, 0.36, color=[SYS_COL[s] for s in SYS], alpha=0.45)
    from matplotlib.patches import Patch
    axs[1].legend(handles=[Patch(color=C["grey"], label="False claims"),
                           Patch(color=C["grey"], alpha=0.45, label="Answers with a false claim")],
                  loc="lower right", fontsize=6.5)
    axs[1].set_yticks(y, [SYS_NAME[s] for s in SYS])
    axs[1].invert_yaxis()
    axs[1].set_xlabel("Count")
    axs[1].set_title("False claims", fontsize=8.5)
    axs[1].tick_params(axis="y", labelsize=6.5)
    for yi, c_ in enumerate(claims):
        axs[1].text(c_ + 0.8, yi - 0.19, str(c_), va="center", fontsize=6.5)
    for ax, s in zip(axs, "ab"):
        clean(ax, "both" if ax is axs[0] else "x")
        panel(ax, s)
    axs[0].legend(loc="center right", fontsize=6.3, bbox_to_anchor=(1.0, 0.37))
    fig.tight_layout(w_pad=2)
    save(fig, "baseline_qa", "correctness_latency_hallucinations")


def bqa_context_citations():
    o = _bsum()["overall"]
    fig, axs = plt.subplots(1, 2, figsize=(W2, 2.9))
    y = np.arange(len(SYS))
    axs[0].barh(y, [o[s]["context_tokens_median"] for s in SYS], color=[SYS_COL[s] for s in SYS], height=0.65)
    axs[0].set_yticks(y, [SYS_NAME[s] for s in SYS])
    axs[0].invert_yaxis()
    axs[0].set_xlabel("Median context tokens")
    axs[0].set_title("Context size", fontsize=8.5)
    cs = [s for s in SYS if s != "plain"]
    y2 = np.arange(len(cs))
    axs[1].barh(y2, [o[s]["citation_validity"] * 100 for s in cs], color=[SYS_COL[s] for s in cs], height=0.65)
    for yi, s in enumerate(cs):
        axs[1].text(o[s]["citation_validity"] * 100 + 1, yi, f"{o[s]['citations_valid']}/{o[s]['citations']}", va="center", fontsize=6.5)
    axs[1].set_yticks(y2, [SYS_NAME[s] for s in cs])
    axs[1].invert_yaxis()
    axs[1].set_xlim(0, 120)
    axs[1].set_xlabel("Valid citations (%)")
    axs[1].set_title("Citation validity", fontsize=8.5)
    for ax, s in zip(axs, "ab"):
        clean(ax, "x")
        panel(ax, s)
        ax.tick_params(axis="y", labelsize=6.5)
    fig.tight_layout(w_pad=2)
    save(fig, "baseline_qa", "context_and_citation_validity")


def bqa_latency_dist():
    data = []
    for sy in SYS:
        data.append([json.loads(l)["seconds"] for l in open(B / f"runs/{sy}.jsonl")])
    fig, ax = plt.subplots(figsize=(W1 + 1.0, 3.1))
    bp = ax.boxplot(data, orientation="horizontal", widths=0.55, whis=(5, 95), showfliers=False, patch_artist=True,
                    medianprops=dict(color="black", lw=1))
    for p, sy in zip(bp["boxes"], SYS):
        p.set(facecolor=SYS_COL[sy], alpha=0.85, lw=0.6)
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 5, 10, 20, 50], ["1", "2", "5", "10", "20", "50"])
    ax.set_yticks(range(1, len(SYS) + 1), [SYS_NAME[s] for s in SYS])
    ax.invert_yaxis()
    ax.set_xlabel("Answer time (s)")
    ax.set_title("Answer time distribution")
    clean(ax, "x")
    save(fig, "baseline_qa", "latency_distribution")


def bqa_judge_agreement():
    j = jload(B / "judge_agreement.json")
    keys = ["ours", "plain", "rag", "abl_facts_unrestricted", "abl_graph_unrestricted"]
    names = ["Proposed (knowledge layer)", "Plain LLM", "RAG", "Ablation: fact retrieval only", "Ablation: graph tools only"]
    fig, axs = plt.subplots(1, 2, figsize=(W2, 2.8), gridspec_kw=dict(width_ratios=[1.5, 1]))
    x = np.arange(len(keys))
    w = 0.36
    axs[0].bar(x - w / 2, [j["per_system"][k]["correct_opus"] for k in keys], w, color=C["blue"], label="Judge A (Opus)")
    axs[0].bar(x + w / 2, [j["per_system"][k]["correct_sonnet"] for k in keys], w, color=C["orange"], label="Judge B (Sonnet)")
    axs[0].set_xticks(x, ["Proposed\n(knowledge\nlayer)", "Plain\nLLM", "RAG", "Ablation:\nfact retrieval\nonly", "Ablation:\ngraph tools\nonly"], fontsize=6.5)
    axs[0].set_ylim(0, 1.15)
    axs[0].set_ylabel("Mean correctness")
    axs[0].set_title("Judge comparison", fontsize=8.5)
    axs[0].legend(ncol=2, loc="upper right", fontsize=7)
    stats = [("Exact agreement", j["correct_exact"]), ("Within 0.5", j["correct_within_half"]),
             ("False-claim flag", j["halluc_flag_agree"]), ("Cohen's kappa", j["correct_kappa"])]
    axs[1].barh([s for s, _ in stats], [v for _, v in stats], color=C["green"], height=0.6)
    for yi, (_, v) in enumerate(stats):
        axs[1].text(v + 0.015, yi, f"{v:.2f}", va="center", fontsize=7)
    axs[1].invert_yaxis()
    axs[1].set_xlim(0, 1.15)
    axs[1].set_title("Agreement", fontsize=8.5)
    for ax, s in zip(axs, "ab"):
        clean(ax, "y" if ax is axs[0] else "x")
        panel(ax, s)
    fig.tight_layout(w_pad=2)
    save(fig, "baseline_qa", "judge_agreement")


# ============================================================ QA optimisation (before / after)
OPT = ["ours", "ours_v2", "ours_v2_nothink"]
OPT_NAME = {"ours": "Proposed (earlier)", "ours_v2": "Proposed (optimised, reasoning)",
            "ours_v2_nothink": "Proposed (optimised, no reasoning)", "rag": "RAG", "rag_think": "RAG + reasoning"}
OPT_COL = {"ours": C["orange"], "ours_v2": C["verm"], "ours_v2_nothink": C["black"], "rag": C["blue"],
           "rag_think": C["sky"]}


def _pct90(x):  # same rule as baseline-tests/summarize.py
    x = sorted(x)
    return x[min(len(x) - 1, int(round(0.9 * (len(x) - 1))))]


def _run1(sy, key):
    return [r[key] for r in map(json.loads, open(B / f"runs/{sy}.jsonl")) if r.get(key) is not None]


def qaopt_latency():
    rows = ["ours", "ours_v2", "ours_v2_nothink", "rag", "rag_think"]
    fig, axs = plt.subplots(1, 2, figsize=(W2, 2.5), sharey=True)
    y = np.arange(len(rows))
    for ax, key, title, s in [(axs[0], "seconds", "Answer time", "a"), (axs[1], "first_token_s", "Time to first token", "b")]:
        for yi, sy in zip(y, rows):
            v = _run1(sy, key)
            m, p = float(np.median(v)), _pct90(v)
            ax.plot([m, p], [yi, yi], color="#BBBBBB", lw=1.2, zorder=1)
            ax.scatter([m], [yi], color=OPT_COL[sy], s=34, zorder=3, marker="o")
            ax.scatter([p], [yi], color=OPT_COL[sy], s=34, zorder=3, marker="D")
            ax.text(p * 1.28, yi, f"{m:.1f} / {p:.1f}", va="center", fontsize=6.5)
        ax.set_xscale("log")
        ax.set_xlim(0.8, 160)
        ax.set_xticks([1, 2, 5, 10, 20, 50, 100], ["1", "2", "5", "10", "20", "50", "100"])
        ax.set_xlabel("Seconds")
        ax.set_title(title, fontsize=8.5)
        clean(ax, "x")
        panel(ax, s)
    axs[0].set_yticks(y, [OPT_NAME[r] for r in rows])
    axs[0].invert_yaxis()
    axs[0].tick_params(axis="y", labelsize=7)
    from matplotlib.lines import Line2D
    fig.legend([Line2D([], [], marker="o", color="k", ls="", ms=5), Line2D([], [], marker="D", color="k", ls="", ms=5)],
               ["Median", "90th percentile"], ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(w_pad=1.5, rect=(0, 0.05, 1, 1))
    save(fig, "qa_optimisation", "latency")


def qaopt_accuracy():
    ba = _bsum()["before_after"]
    rows = ["overall"] + list(CAT_NAME)
    names = ["Overall"] + [CAT_NAME[c] for c in CAT_NAME]
    fig, ax = plt.subplots(figsize=(W1 + 1.4, 3.6))
    y = np.arange(len(rows)) + np.r_[0, np.ones(len(rows) - 1) * 0.6]
    off = {"ours": -0.17, "ours_v2": 0, "ours_v2_nothink": 0.17}
    for yi in y:
        ax.axhline(yi, color="#DDDDDD", lw=0.5, zorder=0)
    for sy in OPT:
        ax.scatter([ba[r][sy]["correct"] for r in rows], y + off[sy], color=OPT_COL[sy], s=22, zorder=3,
                   label=OPT_NAME[sy])
    ax.axhline((y[0] + y[1]) / 2, color="black", lw=0.6)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlim(0.3, 1.02)
    ax.set_xlabel("Correctness")
    ax.set_title("Correctness by question category")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.13), ncol=1, fontsize=7)
    clean(ax, "x")
    save(fig, "qa_optimisation", "accuracy_by_category")


def qaopt_calls():
    ba = _bsum()["before_after"]["overall"]
    o = _bsum()["overall"]
    mets = [("Model calls", "model_calls_mean"), ("Tool calls", "tool_calls_per_q"),
            ("check_concept calls", "check_concept_per_q")]
    fig, ax = plt.subplots(figsize=(W1 + 1.0, 2.6))
    x = np.arange(len(mets))
    w = 0.2
    for i, sy in enumerate(OPT + ["rag"]):
        if sy == "rag":
            v = [o["rag"]["model_calls_mean"], 0, 0]
        else:
            v = [ba[sy][k] for _, k in mets]
        b = ax.bar(x + (i - 1.5) * w, v, w, color=OPT_COL[sy], label=OPT_NAME[sy])
        for xi, vi in zip(x + (i - 1.5) * w, v):
            ax.text(xi, vi + 0.03, f"{vi:.2f}".rstrip("0").rstrip("."), ha="center", fontsize=6)
    ax.set_xticks(x, [m for m, _ in mets])
    ax.set_ylabel("Per question")
    ax.set_ylim(0, 2.6)
    ax.set_title("Model and tool calls")
    ax.legend(loc="upper right", fontsize=6.3)
    clean(ax)
    save(fig, "qa_optimisation", "calls_per_question")


def qaopt_false_claims():
    o = _bsum()["before_after"]["overall"]
    r = _bsum()["overall"]
    rows = OPT + ["rag"]
    v = [(o[s] if s in o else r[s])["answers_with_hallucination"] for s in rows]
    fig, ax = plt.subplots(figsize=(W1, 2.6))
    x = np.arange(len(rows))
    ax.bar(x, v, color=[OPT_COL[s] for s in rows], width=0.6)
    for xi, vi in zip(x, v):
        ax.text(xi, vi + 0.1, str(vi), ha="center", fontsize=7.5)
    ax.set_xticks(x, [OPT_NAME[s].replace(" (", "\n(").replace(", ", ",\n") for s in rows], fontsize=6.3)
    ax.set_ylabel("Answers")
    ax.set_ylim(0, 6.5)
    ax.set_title("Answers with a false claim")
    clean(ax)
    save(fig, "qa_optimisation", "false_claims")


FIGS = [seg_vs_human, seg_history, seg_run_to_run, prep_pysbd, prep_time_error, factjudge_seeded, factjudge_gold,
        factjudge_materials, act_trial, actstudy_gemma_pass, actstudy_sonnet, actstudy_map_recall, actstudy_layer_only,
        qa_latency_variants, qa_calibration, failures_inventory, bqa_correct_heatmap, bqa_overall,
        bqa_context_citations, bqa_latency_dist, bqa_judge_agreement, qaopt_latency, qaopt_accuracy, qaopt_calls,
        qaopt_false_claims]

if __name__ == "__main__":
    want = set(sys.argv[1:])
    for f in FIGS:
        if not want or f.__name__ in want:
            f()
