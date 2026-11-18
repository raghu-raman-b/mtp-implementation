"""Calibrate fact_lookup's "no close match" cut-off on in-course and out-of-course queries.

    cd pipeline && python3 ../analysis/qa/calibrate.py [--course nptel_vr]

Reads analysis/qa/calibration_queries.json; for each query takes the best fact score the way fact_lookup computes it
(the query, its acronyms expanded, its keywords, and the two other wordings), both with and without the other
wordings; writes analysis/qa/calibration.json: every score with the top fact, the two distributions, the separation
(AUC, the gap) and the cut-off chosen. The rule: the cut-off is used to stop early, so missing an in-course question
costs more than letting an out-of-course one through; take the highest cut-off that keeps every in-course query at or
above it, then place it in the middle of the gap between the classes when there is one.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "pipeline"))
from qa.knowledge import Knowledge  # noqa: E402
from qa.tools import keywords  # noqa: E402


def best(kb, q, alts):
    variants = [v for v in dict.fromkeys([q, *alts, kb.expand_acronyms(q), keywords(q)]) if v]
    hits = kb.search(variants, k=3)
    return hits[0][1], hits[0][0]


def stats(xs):
    xs = sorted(xs)
    pick = lambda p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]  # noqa: E731
    return {"n": len(xs), "min": xs[0], "p05": pick(0.05), "median": statistics.median(xs), "p95": pick(0.95),
            "max": xs[-1]}


def auc(pos, neg):
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


MARGIN = 0.05


def choose(keep, neg):
    lo, hi = max(neg), min(keep)
    if hi > lo:                                   # separable: the middle of the gap
        return round((hi + lo) / 2, 3), "middle of the gap (every in-course query above, every out-of-course below)"
    return round(hi - MARGIN, 2), f"{MARGIN} below the lowest in-course or partly score (the classes overlap)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", default="nptel_vr")
    a = ap.parse_args()
    kb = Knowledge.load(a.course)
    data = json.loads((HERE / "calibration_queries.json").read_text())
    rows = []
    for label in ("in", "partly", "out"):
        for item in data[label]:
            s_alts, f_alts = best(kb, item["q"], item["alts"])
            s_q, _ = best(kb, item["q"], [])
            rows.append({"label": label, "kind": item.get("kind", "in"), "q": item["q"], "score": s_alts,
                         "score_query_only": s_q, "top_fact": f_alts, "top_text": kb.facts[f_alts]["text"][:160]})
    out = {"course": a.course, "embed_model": kb.embed_model}
    for key in ("score", "score_query_only"):
        pos = [r[key] for r in rows if r["label"] == "in"]
        neg = [r[key] for r in rows if r["label"] == "out"]
        part = [r[key] for r in rows if r["label"] == "partly"]
        near = [r[key] for r in rows if r["kind"] == "near"]
        far = [r[key] for r in rows if r["kind"] == "far"]
        t, how = choose(pos + part, neg)
        out[key] = {"in": stats(pos), "partly": sorted(part), "out": stats(neg), "out_near": stats(near), "out_far": stats(far),
                    "auc": round(auc(pos, neg), 4), "gap": round(min(pos) - max(neg), 4), "cutoff": t, "rule": how,
                    "at_cutoff": {"in_below": sum(p < t for p in pos), "partly_below": sum(p < t for p in part),
                                  "out_below": sum(n < t for n in neg), "out_at_or_above": sum(n >= t for n in neg)},
                    "at_old_0.4": {"in_below": sum(p < 0.4 for p in pos), "out_below": sum(n < 0.4 for n in neg), "out_at_or_above": sum(n >= 0.4 for n in neg)}}
    out["rows"] = sorted(rows, key=lambda r: -r["score"])
    (HERE / "calibration.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for key in ("score", "score_query_only"):
        print(key, json.dumps({k: v for k, v in out[key].items()}, indent=None))
    for r in out["rows"]:
        print(f"{r['label']:6s} {r['kind']:4s} {r['score']:.3f} {r['score_query_only']:.3f} {r['q'][:55]:55s} | "
              f"{r['top_text'][:90]}")


if __name__ == "__main__":
    main()
