"""Numbers from runs/ and judgments.jsonl: summary.json, tables.md, examples.jsonl, demo_questions.json.

    python3 baseline-tests/summarize.py

Correctness, hallucinations and not-covered handling come from judgments.jsonl (Opus judge). Citation validity is by
code: every "(lecture N, m:ss)" an answer writes (citations.written_citations, the same for all systems) is valid when
the lecture exists and at least VALID_OVERLAP of the claim's content words occur in that lecture's transcript from
30 s before to 240 s after the cited time. Cost figures (context tokens, model calls, latency, first token) are from
run 1 of each system over all 53 questions.
"""
import json
import re
import statistics as st
from collections import defaultdict

from citations import written_citations
from common import OUT
from render_for_judge import SYSTEMS, run_files

VALID_OVERLAP = 0.5
BASELINES = ["plain", "rag", "rag_think", "graphrag_text", "graphrag_notext"]
REPEAT_SYSTEMS = ["ours", "rag", "rag_think"]
REPEAT_CATS = ["not_covered", "where", "prerequisite", "structure", "formula"]


def med(x):
    return round(st.median(x), 2) if x else None


def p90(x):
    if not x:
        return None
    x = sorted(x)
    return round(x[min(len(x) - 1, int(round(0.9 * (len(x) - 1))))], 2)


def mean(x):
    return round(sum(x) / len(x), 3) if x else None


def main():
    qs = [json.loads(x) for x in (OUT / "questions.jsonl").open()]
    qby = {q["id"]: q for q in qs}
    cats = list(dict.fromkeys(q["category"] for q in qs))
    runs = run_files()
    J = {(j["qid"], j["system"], j["run"]): j for j in map(json.loads, (OUT / "judgments.jsonl").open())}
    systems = [s for s in SYSTEMS if (s, 1) in runs]

    def cite_stats(recs):
        n = v = 0
        for r in recs:
            for c in written_citations(r.get("answer") or ""):
                n += 1
                v += bool(c["lecture_exists"] and c["window_sentences"] and (c["auto_overlap"] or 0) >= VALID_OVERLAP)
        return v, n

    def block(s, run, ids):
        recs = [runs[(s, run)][i] for i in ids if i in runs[(s, run)]]
        js = [J[(i, s, run)] for i in ids if (i, s, run) in J]
        nc = [j["not_covered_handled"] for j in js if qby[j["qid"]]["category"] == "not_covered"
              and j["not_covered_handled"] is not None]
        v, n = cite_stats(recs)
        return {"answers": len(recs), "judged": len(js), "correct": mean([j["correct"] for j in js]),
                "hallucinations": sum(j["hallucinations"] for j in js),
                "answers_with_hallucination": sum(j["hallucinations"] > 0 for j in js),
                "citations_valid": v, "citations": n, "citation_validity": round(v / n, 3) if n else None,
                "not_covered_handled": sum(nc), "not_covered_judged": len(nc),
                "context_tokens_median": med([r["context_tokens"] for r in recs if r.get("context_tokens")]),
                "model_calls_mean": mean([r["model_calls"] for r in recs if r.get("model_calls")]),
                "latency_median_s": med([r["seconds"] for r in recs if r.get("seconds")]),
                "latency_p90_s": p90([r["seconds"] for r in recs if r.get("seconds")]),
                "first_token_median_s": med([r["first_token_s"] for r in recs if r.get("first_token_s") is not None]),
                "errors": sum(bool(r.get("error")) for r in recs)}

    all_ids = [q["id"] for q in qs]
    summary = {"overall": {s: block(s, 1, all_ids) for s in systems},
               "per_category": {c: {s: block(s, 1, [q["id"] for q in qs if q["category"] == c]) for s in systems}
                                for c in cats},
               "repeats": {}, "valid_overlap": VALID_OVERLAP}
    for c in REPEAT_CATS:
        ids = [q["id"] for q in qs if q["category"] == c]
        for s in REPEAT_SYSTEMS:
            per_run = {r: mean([J[(i, s, r)]["correct"] for i in ids if (i, s, r) in J])
                       for (ss, r) in runs if ss == s}
            per_run = {r: v for r, v in sorted(per_run.items()) if v is not None}
            h = {r: sum(J[(i, s, r)]["hallucinations"] for i in ids if (i, s, r) in J) for r in per_run}
            if per_run:
                vals = list(per_run.values())
                summary["repeats"].setdefault(c, {})[s] = {"runs": per_run, "mean": mean(vals), "min": min(vals),
                                                         "max": max(vals), "hallucinations_per_run": h}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))

    # tables.md
    L = ["# Baseline comparison tables", "", "Run 1 of every system, 53 questions. correct: mean of 1 / 0.5 / 0 (Opus "
         "judge). halluc: false claims counted (answers with one). cit valid: by code (see summarize.py). nc handled: "
         "not-covered questions answered as not covered without invented content. ctx: median context tokens. "
         "calls: mean model calls. latency / first token in seconds.", "",
         "## Overall", "",
         "| system | correct | halluc (answers) | cit valid | nc handled | ctx | calls | latency med | latency p90 | first token |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for s in systems:
        b = summary["overall"][s]
        L.append(f'| {s} | {b["correct"]} | {b["hallucinations"]} ({b["answers_with_hallucination"]}) | '
                 f'{b["citations_valid"]}/{b["citations"]} | {b["not_covered_handled"]}/{b["not_covered_judged"]} | '
                 f'{b["context_tokens_median"]} | {b["model_calls_mean"]} | {b["latency_median_s"]} | '
                 f'{b["latency_p90_s"]} | {b["first_token_median_s"]} |')
    L += ["", "## Correct per category", "", "| category (n) | " + " | ".join(systems) + " |",
          "|---|" + "---|" * len(systems)]
    for c in cats:
        n = sum(q["category"] == c for q in qs)
        L.append(f"| {c} ({n}) | " + " | ".join(str(summary["per_category"][c][s]["correct"]) for s in systems) + " |")
    L += ["", "## Hallucinations per category (count)", "", "| category | " + " | ".join(systems) + " |",
          "|---|" + "---|" * len(systems)]
    for c in cats:
        L.append(f"| {c} | " + " | ".join(str(summary["per_category"][c][s]["hallucinations"]) for s in systems) + " |")
    L += ["", "## Citation validity per category (valid/total)", "", "| category | " + " | ".join(systems) + " |",
          "|---|" + "---|" * len(systems)]
    for c in cats:
        L.append(f"| {c} | " + " | ".join(f'{summary["per_category"][c][s]["citations_valid"]}/'
                                         f'{summary["per_category"][c][s]["citations"]}' for s in systems) + " |")
    L += ["", "## Latency median / first token median per category (s)", "", "| category | " + " | ".join(systems) + " |",
          "|---|" + "---|" * len(systems)]
    for c in cats:
        L.append(f"| {c} | " + " | ".join(f'{summary["per_category"][c][s]["latency_median_s"]} / '
                                         f'{summary["per_category"][c][s]["first_token_median_s"]}' for s in systems) + " |")
    L += ["", "## Repeats (3 runs): correct, mean ± range (min-max) across runs", "",
          "| category | " + " | ".join(REPEAT_SYSTEMS) + " |", "|---|" + "---|" * len(REPEAT_SYSTEMS)]
    for c in REPEAT_CATS:
        row = []
        for s in REPEAT_SYSTEMS:
            x = summary["repeats"].get(c, {}).get(s)
            row.append(f'{x["mean"]} ({x["min"]}-{x["max"]}, {len(x["runs"])} runs)' if x else "-")
        L.append(f"| {c} | " + " | ".join(row) + " |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n")

    # examples.jsonl: the 10 questions whose run-1 correctness differs most across systems (population std, then range)
    spread = []
    for q in qs:
        sc = [J[(q["id"], s, 1)]["correct"] for s in systems if (q["id"], s, 1) in J]
        if len(sc) >= 2:
            spread.append((st.pstdev(sc), max(sc) - min(sc), q["id"]))
    spread.sort(key=lambda x: (-x[0], -x[1], x[2]))
    with (OUT / "examples.jsonl").open("w") as f:
        for sd, rg, qid in spread[:10]:
            q = qby[qid]
            f.write(json.dumps({"id": qid, "category": q["category"], "question": q["question"],
                                "gold": q["gold_answer"], "spread_std": round(sd, 3),
                                "systems": {s: {"correct": J.get((qid, s, 1), {}).get("correct"),
                                                "hallucinations": J.get((qid, s, 1), {}).get("hallucinations"),
                                                "note": J.get((qid, s, 1), {}).get("note"),
                                                "answer": runs[(s, 1)].get(qid, {}).get("answer")}
                                            for s in systems}}, ensure_ascii=False) + "\n")

    # demo_questions.json: ours correct=1 in every judged run, best baseline (mean over its runs) lower
    def score(s, qid):
        v = [J[(qid, s, r)]["correct"] for (ss, r) in runs if ss == s and (qid, s, r) in J]
        return round(sum(v) / len(v), 3) if v else None

    demo = {}
    for q in qs:
        ours = [J[(q["id"], "ours", r)]["correct"] for (ss, r) in runs if ss == "ours" and (q["id"], "ours", r) in J]
        if not ours or min(ours) < 1:
            continue
        others = {s: score(s, q["id"]) for s in BASELINES if (s, 1) in runs}
        best = max([v for v in others.values() if v is not None], default=None)
        if best is None or best >= 1:
            continue
        m = re.search(r"lecture (\d+)", " ".join(q["gold_sources"]) if isinstance(q["gold_sources"], list)
                      else str(q["gold_sources"]))
        demo.setdefault(q["category"], []).append(
            {"id": q["id"], "q": q["question"], "category": q["category"], "lecture": m.group(1) if m else None,
             "ours_score": 1, "ours_runs": len(ours), "others": others, "best_other": best,
             "ablations": {s: score(s, q["id"]) for s in ("abl_facts", "abl_graph") if (s, 1) in runs}})
    (OUT / "demo_questions.json").write_text(json.dumps(demo, indent=1, ensure_ascii=False))
    print((OUT / "tables.md").read_text().split("## Hallucinations")[0])


if __name__ == "__main__":
    main()
