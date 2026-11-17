"""Tables from runs/ and judgments.jsonl -> summary.json and summary tables (markdown, printed).

    python3 baseline-tests/summarize.py

Judgment fields (one line per question and system, written by the judge after reading judge/packet_*.txt):
  correct 1 / 0.5 / 0     the answer is right against the gold and the course (not covered: says so, invents nothing)
  complete 1 / 0.5 / 0    it has the gold's main points (not covered: 1 when it says so clearly)
  hallucination true/false a claim that is false, contradicts the course, or presents something as taught in the
                           course that is not (an invented lecture, time or course content)
  outside true/false      it adds substantive claims the course does not teach (true or not): not an error for plain,
                           but against the grounding rule for the other three
  citations n, valid n    citations written (lecture + time) and those whose lecture and time hold the claim
"""
import json
import statistics as st
from collections import defaultdict

from common import OUT

SYSTEMS = ["ours", "plain", "rag", "graphrag"]
CATS = ["definition", "explanation", "comparison", "list", "formula", "where", "prerequisite", "structure",
        "not_covered"]


def pct(x):
    return round(100 * x, 1)


def main():
    qs = {json.loads(x)["id"]: json.loads(x) for x in (OUT / "questions.jsonl").open()}
    runs = {s: {json.loads(x)["id"]: json.loads(x) for x in (OUT / "runs" / f"{s}.jsonl").open()} for s in SYSTEMS}
    js = defaultdict(dict)
    for line in (OUT / "judgments.jsonl").open():
        j = json.loads(line)
        js[j["system"]][j["id"]] = j
    summary = {"questions": len(qs), "systems": {}}
    for s in SYSTEMS:
        rows = [(qs[i], js[s][i], runs[s][i]) for i in qs if i in js[s] and i in runs[s]]

        def agg(rs):
            n = len(rs)
            if not n:
                return {}
            cit = sum(j.get("citations", 0) for _, j, _ in rs)
            val = sum(j.get("valid", 0) for _, j, _ in rs)
            lat = [r["seconds"] for _, _, r in rs if r.get("seconds") is not None]
            ftk = [r["first_token_s"] for _, _, r in rs if r.get("first_token_s") is not None]
            ctx = [r["context_tokens"] for _, _, r in rs if r.get("context_tokens") is not None]
            out = [r["output_tokens"] for _, _, r in rs if r.get("output_tokens") is not None]
            calls = [r.get("model_calls", 1) for _, _, r in rs]
            return {"n": n,
                    "correct": pct(sum(j["correct"] for _, j, _ in rs) / n),
                    "fully_correct": pct(sum(j["correct"] == 1 for _, j, _ in rs) / n),
                    "complete": pct(sum(j["complete"] for _, j, _ in rs) / n),
                    "hallucination": pct(sum(bool(j["hallucination"]) for _, j, _ in rs) / n),
                    "outside": pct(sum(bool(j.get("outside")) for _, j, _ in rs) / n),
                    "answers_with_citations": pct(sum(j.get("citations", 0) > 0 for _, j, _ in rs) / n),
                    "citations": cit, "valid_citations": val,
                    "citation_validity": pct(val / cit) if cit else None,
                    "context_tokens_median": st.median(ctx) if ctx else None,
                    "context_tokens_mean": round(st.mean(ctx)) if ctx else None,
                    "output_tokens_median": st.median(out) if out else None,
                    "model_calls_mean": round(st.mean(calls), 2),
                    "latency_median_s": round(st.median(lat), 2) if lat else None,
                    "latency_p90_s": round(sorted(lat)[int(0.9 * (len(lat) - 1))], 2) if lat else None,
                    "first_token_median_s": round(st.median(ftk), 2) if ftk else None}

        covered = [x for x in rows if x[0]["category"] != "not_covered"]
        summary["systems"][s] = {"overall": agg(rows), "covered_questions": agg(covered),
                                 "by_category": {c: agg([x for x in rows if x[0]["category"] == c]) for c in CATS}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    # markdown tables
    print("| system | correct | fully correct | complete | hallucination | outside course | answers with citations | "
          "citation validity | ctx tokens (median) | output tokens (median) | model calls | latency median / p90 | first token |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in SYSTEMS:
        o = summary["systems"][s]["overall"]
        print(f"| {s} | {o['correct']} | {o['fully_correct']} | {o['complete']} | {o['hallucination']} | {o['outside']} | "
              f"{o['answers_with_citations']} | {o['citation_validity']} ({o['valid_citations']}/{o['citations']}) | "
              f"{o['context_tokens_median']} | {o['output_tokens_median']} | {o['model_calls_mean']} | "
              f"{o['latency_median_s']} / {o['latency_p90_s']} s | {o['first_token_median_s']} s |")
    print()
    print("| category (n) | " + " | ".join(SYSTEMS) + " |")
    print("|---|" + "---|" * len(SYSTEMS))
    for c in CATS:
        n = summary["systems"]["ours"]["by_category"][c].get("n")
        cells = []
        for s in SYSTEMS:
            a = summary["systems"][s]["by_category"][c]
            cells.append(f"{a['correct']} / {a['hallucination']}" if a else "-")
        print(f"| {c} ({n}) | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
