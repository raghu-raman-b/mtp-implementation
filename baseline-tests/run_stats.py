"""Run-side numbers only (no judgments): per system and run, overall and per category: answers, errors, latency
median / p90, first-token median, context-token median, mean model calls. Also the GraphRAG index size, written into
README.md in place of GRAPHRAG_SIZE.  -> run_stats.json, run_stats.md

    python3 baseline-tests/run_stats.py
"""
import json

from common import OUT
from render_for_judge import SYSTEMS, run_files
from summarize import med, p90, mean


def block(recs):
    def vals(k):
        return [r[k] for r in recs if r.get(k) is not None]
    return {"answers": len(recs), "errors": sum(bool(r.get("error")) for r in recs),
            "latency_median_s": med(vals("seconds")), "latency_p90_s": p90(vals("seconds")),
            "first_token_median_s": med(vals("first_token_s")),
            "context_tokens_median": med(vals("context_tokens")), "model_calls_mean": mean(vals("model_calls"))}


def graphrag_size():
    G = OUT / "graphrag"
    out = {}
    ex = G / "extractions.jsonl"
    if ex.exists():
        out["text_units_extracted"] = sum(1 for _ in ex.open())
    if (G / "graph.json").exists():
        g = json.load((G / "graph.json").open())
        out.update(entities=len(g["entities"]), relationships=len(g["relationships"]),
                   communities=len(g["communities"]))
    rp = G / "community_reports.jsonl"
    if rp.exists():
        out["community_reports"] = sum(1 for _ in rp.open())
    return out


def main():
    qs = [json.loads(x) for x in (OUT / "questions.jsonl").open()]
    cats = list(dict.fromkeys(q["category"] for q in qs))
    qcat = {q["id"]: q["category"] for q in qs}
    runs = run_files()
    keys = sorted(runs, key=lambda k: (SYSTEMS.index(k[0]), k[1]))
    stats = {f"{s} r{r}": {"overall": block(list(runs[(s, r)].values())),
                           "per_category": {c: block([x for i, x in runs[(s, r)].items() if qcat.get(i) == c])
                                            for c in cats if any(qcat.get(i) == c for i in runs[(s, r)])}}
             for s, r in keys}
    size = graphrag_size()
    (OUT / "run_stats.json").write_text(json.dumps({"runs": stats, "graphrag_index": size}, indent=1))

    cols = ["answers", "errors", "latency_median_s", "latency_p90_s", "first_token_median_s",
            "context_tokens_median", "model_calls_mean"]
    hdr = ["| run | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    L = ["# Run-side numbers (no correctness)", "", "Latency and first token in seconds; context tokens median; "
         "model calls mean. Per run file.", "", "## Overall", ""] + hdr
    for k, v in stats.items():
        L.append(f"| {k} | " + " | ".join(str(v["overall"][c]) for c in cols) + " |")
    for c in cats:
        L += ["", f"## {c}", ""] + hdr
        for k, v in stats.items():
            if c in v["per_category"]:
                L.append(f"| {k} | " + " | ".join(str(v["per_category"][c][x]) for x in cols) + " |")
    L += ["", "## GraphRAG index", "", json.dumps(size)]
    (OUT / "run_stats.md").write_text("\n".join(L) + "\n")

    if size.get("entities") is not None:
        txt = (f"{size.get('text_units_extracted')} text units extracted, {size['entities']} entities, "
               f"{size['relationships']} relationships, {size['communities']} communities, "
               f"{size.get('community_reports')} community reports")
        rd = OUT / "README.md"
        rd.write_text(rd.read_text().replace("GRAPHRAG_SIZE", txt))
    print(json.dumps(size))


if __name__ == "__main__":
    main()
