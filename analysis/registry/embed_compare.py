"""Choose the embedding model for stage 3 (and its threshold) on a labelled pair set.

    python analysis/registry/embed_compare.py nptel_vr [--pairs analysis/registry/pairs.json]
        [--models Qwen/Qwen3-Embedding-0.6B,Qwen/Qwen3-Embedding-4B,sentence-transformers/all-mpnet-base-v2]
        [--recall 0.95] [--json analysis/registry/embed_compare.json] [--report analysis/registry/report_embed.md]
        [--cache analysis/registry/embed_cache.jsonl] [--pipeline DIR] [--device cuda]

The pair gold (written by F), analysis/registry/pairs.json:
    {"pairs": [{"a": "1/S1/C0", "b": "16/S2/C3", "same": true, "kind": "synonym", "note": "optional"}, ...]}
  a, b   segment concept IDs of stage 2c (output/<course>/stage_2c_concepts/concept_maps/)
  same   true when a careful reader would make them one glossary entry
  kind   free text; the hard kinds of the plan are expected: synonym, acronym, spelling, same name (same meaning),
         same name other meaning, kind of, part of, property of, related. Results are also given per kind.
The lectures read are those the pair IDs name.

Everything is computed exactly as stage 3a does it (scripts/s3a_candidates.py: exact_entries, entry_text,
shared_terms, instruction, make_clusters), so a pair here is a pair of the entries its two segment concepts fall in:
  exact   both segment concepts are in one entry (step 1 merged them: reached whatever the threshold; a "different"
          pair here is a wrong merge no model ever sees)
  alias   their entries share a name (a candidate whatever the threshold)
  sim     the cosine similarity of the two entries' embedding texts
A "same" pair reaches the model at threshold t when it is exact, alias, or sim >= t (the cap of a cluster can still
cut it; the cut pairs at the chosen threshold are counted too).

Runs per model: each of the three --embed-facts options of s3a (decision D9: defining, any-if-none, any), each with
the instruction s3a gives it ("names and defining facts" for defining, "names and facts" for the others). For a model
that takes an instruction (Qwen3-Embedding) also: defining with the "names and facts" instruction, so that defining
and any-if-none are compared with the same instruction; and the default option without an instruction, to see what
the instruction is worth.

Per run:
  - similarity distributions of same and different pairs (min, 10th, 25th, 50th, 75th, 90th percentile, max), and
    per kind (n, mean, min, max);
  - candidate recall over thresholds: same pairs reached; different pairs that become candidates; candidate pairs
    over all entries; the largest connected cluster before the cap;
  - the highest threshold (steps of 0.01) with recall >= --recall, and at it: the candidate pairs, the clusters
    (cap from s3a), the largest cluster, the pairs the cap cuts, the "same" pairs the cap cuts (listed), the
    "different" pairs that become candidates (listed), and the twin pairs that become candidates (listed);
  - twin pairs: pairs of entries whose segment concepts in one segment cite exactly the same facts (16/S0: anchor,
    pose, position, ... all cite only F3). Option-independent; how many become candidates is not: with other facts
    in the text, their texts differ only in the names.
Models are loaded one at a time; vectors are cached (scripts/embed.py), so a rerun or a second report costs nothing.
The models' download sizes: Qwen3-Embedding-0.6B 1.2 GB, -4B 8 GB (bf16), all-mpnet-base-v2 0.4 GB.
"""
from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MODELS = ["Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-4B", "sentence-transformers/all-mpnet-base-v2"]
GRID = [round(0.30 + 0.05 * i, 2) for i in range(14)]   # 0.30 .. 0.95


def percentiles(xs: list[float]) -> dict:
    if not xs:
        return {}
    xs = sorted(xs)

    def q(p):
        k = (len(xs) - 1) * p
        lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
        return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 3)
    return {"n": len(xs), "min": round(xs[0], 3), "p10": q(.1), "p25": q(.25), "p50": q(.5), "p75": q(.75),
            "p90": q(.9), "max": round(xs[-1], 3)}


def twin_pairs(s3a, concepts: dict, entry_of: dict, pos: dict) -> list[tuple[str, str, str]]:
    """Pairs of entries (a, b in entry order, the segment) whose segment concepts in one segment cite the same facts."""
    by_facts: dict[tuple, list[str]] = {}
    for scid, c in concepts.items():
        if c["facts"]:
            by_facts.setdefault((s3a.segment_of(scid), tuple(sorted(c["facts"]))), []).append(entry_of[scid])
    out = {}
    for (sid, _), es in by_facts.items():
        es = sorted(set(es), key=pos.get)
        for x in range(len(es)):
            for y in range(x + 1, len(es)):
                out.setdefault((es[x], es[y]), sid)
    return [(a, b, sid) for (a, b), sid in out.items()]


def evaluate(s3a, Embedder, course: str, pairs: list[dict], model: str, option: str, instruction: str | None,
             cache: Path, recall_target: float, device: str | None) -> dict:
    keys = sorted({p[x].split("/", 1)[0] for p in pairs for x in ("a", "b")}, key=s3a.lec.order)
    concepts, facts = s3a.load_concepts(course, keys), s3a.load_facts(course, keys)
    missing = sorted({p[x] for p in pairs for x in ("a", "b")} - set(concepts))
    if missing:
        sys.exit(f"pair IDs not in the concept maps: {missing[:10]}")
    entries = s3a.exact_entries(concepts)
    ids = list(entries)
    pos = {eid: i for i, eid in enumerate(ids)}
    entry_of = {m: eid for eid, e in entries.items() for m in e["members"]}
    emb = Embedder(model, cache=cache, device=device)
    vecs = emb.embed([s3a.entry_text(entries[i], facts, option=option) for i in ids], instruction=instruction)
    twins = twin_pairs(s3a, concepts, entry_of, pos)
    alias = s3a.shared_terms(entries)
    all_sims = s3a.similarities(vecs, min(GRID))          # every entry pair at or above the lowest threshold
    rows = []
    for p in pairs:
        ea, eb = entry_of[p["a"]], entry_of[p["b"]]
        key = tuple(sorted((ea, eb), key=pos.get))
        if ea == eb:
            how, sim = "exact", 1.0
        else:
            sim = sum(x * y for x, y in zip(vecs[pos[ea]], vecs[pos[eb]]))
            how = "alias" if key in alias else "sim"
        rows.append({**p, "entries": list(key), "how": how, "sim": round(sim, 4)})

    def reached(r, t):
        return r["how"] in ("exact", "alias") or r["sim"] >= t

    same = [r for r in rows if r["same"]]
    diff = [r for r in rows if not r["same"]]

    def at(t: float, cap: int | None = None) -> dict:
        edges = [(v + (1 if (ids[i], ids[j]) in alias else 0), i, j) for (i, j), v in all_sims.items() if v >= t]
        edges += [(1 + sum(x * y for x, y in zip(vecs[pos[a]], vecs[pos[b]])), pos[a], pos[b])
                  for a, b in alias if (pos[a], pos[b]) not in all_sims or all_sims[(pos[a], pos[b])] < t]
        comps, _ = s3a.make_clusters(len(ids), edges, len(ids) + 1)
        linked = {(min(i, j), max(i, j)) for _, i, j in edges}
        twin_cands = [(a, b, sid) for a, b, sid in twins if (pos[a], pos[b]) in linked]
        out = {"threshold": t,
               "recall": round(sum(reached(r, t) for r in same) / len(same), 3) if same else None,
               "different_as_candidates": round(sum(reached(r, t) for r in diff) / len(diff), 3) if diff else None,
               "candidate_pairs": len(edges), "largest_component": max((len(c) for c in comps), default=1),
               "twin_candidates": len(twin_cands)}
        if cap:
            clusters, cut = s3a.make_clusters(len(ids), edges, cap)
            where = {i: k for k, c in enumerate(clusters) for i in c}
            cut_same = [r for r in same if r["how"] != "exact" and reached(r, t)
                        and where.get(pos[r["entries"][0]], -1) != where.get(pos[r["entries"][1]], -2)]
            name = lambda e: entries[e]["name"]  # noqa: E731
            out.update(clusters=len(clusters), largest_cluster=max((len(c) for c in clusters), default=1),
                       cut_pairs=len(cut), same_cut=len(cut_same),
                       same_cut_pairs=[{k: r[k] for k in ("a", "b", "kind", "sim")} for r in cut_same],
                       different_candidates=[{k: r[k] for k in ("a", "b", "kind", "how", "sim")}
                                             for r in diff if reached(r, t)],
                       twin_candidate_pairs=[{"a": a, "b": b, "segment": sid, "names": [name(a), name(b)]}
                                             for a, b, sid in twin_cands])
        return out

    grid = [at(t) for t in GRID]
    best = None
    for k in range(95, 9, -1):                            # the highest threshold that keeps the recall
        t = k / 100
        if same and sum(reached(r, t) for r in same) / len(same) >= recall_target:
            best = at(t, s3a.CAP)
            best["cap"] = s3a.CAP
            break
    kinds = {}
    for r in rows:
        kinds.setdefault((r["kind"], r["same"]), []).append(r)
    per_kind = [{"kind": k, "same": s, "n": len(v), "exact": sum(r["how"] == "exact" for r in v),
                 "alias": sum(r["how"] == "alias" for r in v),
                 "mean": round(statistics.mean(r["sim"] for r in v), 3), "min": round(min(r["sim"] for r in v), 3),
                 "max": round(max(r["sim"] for r in v), 3)} for (k, s), v in sorted(kinds.items())]
    res = {"model": model, "option": option, "instruction": emb.prefix(instruction),
           "instruction_text": instruction or "", "entries": len(ids), "twin_pairs": len(twins),
           "segment_concepts": len(concepts), "dim": len(vecs[0]) if vecs else 0, "embedded_now": emb.computed,
           "same": percentiles([r["sim"] for r in same if r["how"] != "exact"]),
           "different": percentiles([r["sim"] for r in diff if r["how"] != "exact"]),
           "same_exact": sum(r["how"] == "exact" for r in same), "same_alias": sum(r["how"] == "alias" for r in same),
           "different_exact": [(r["a"], r["b"], r["kind"]) for r in diff if r["how"] == "exact"],
           "per_kind": per_kind, "grid": grid, "at_target": best,
           "missed_at_target": [{k: r[k] for k in ("a", "b", "kind", "sim")} for r in same
                                if best and not reached(r, best["threshold"])],
           "pairs": rows}
    emb._st = None
    del emb
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    return res


def instruction_label(r: dict) -> str:
    """How a run's instruction is named in the report: "defining facts", "facts", or "no"."""
    if not r["instruction"]:
        return "no"
    return "defining facts" if "defining facts" in r["instruction_text"] else "facts"


def report(results: list[dict], recall_target: float, n_pairs: int) -> str:
    out = [f"# Embedding models for the concept registry ({n_pairs} labelled pairs)", ""]
    out += ["| Model | Embed facts | Instruction | Same: p10 / p50 | Different: p50 / p90 | Same exact, alias | "
            f"Threshold for recall >= {recall_target:.0%} | Candidate pairs there | Different as candidates | "
            "Twin pairs as candidates | Clusters, largest, cut pairs, same pairs cut |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        b = r["at_target"] or {}
        out.append(f"| {r['model']} | {r['option']} | {instruction_label(r)} | {r['same'].get('p10')} / "
                   f"{r['same'].get('p50')} | {r['different'].get('p50')} / {r['different'].get('p90')} | "
                   f"{r['same_exact']}, {r['same_alias']} | {b.get('threshold', 'not reached')} | "
                   f"{b.get('candidate_pairs', '')} | {b.get('different_as_candidates', '')} "
                   f"({len(b.get('different_candidates', []))}) | {b.get('twin_candidates', '')} of {r['twin_pairs']} | "
                   f"{b.get('clusters', '')}, {b.get('largest_cluster', '')}, {b.get('cut_pairs', '')}, "
                   f"{b.get('same_cut', '')} |")
    for r in results:
        b = r["at_target"] or {}
        out += ["", f"## {r['model']}, embed facts {r['option']}, instruction: {instruction_label(r)}", "",
                f"{r['segment_concepts']} segment concepts, {r['entries']} entries after the exact merge, "
                f"dimension {r['dim']}.", "",
                f"Same pairs (not exact): {r['same']}", "", f"Different pairs (not exact): {r['different']}", ""]
        if r["different_exact"]:
            out += [f"Different pairs merged by the exact rule (wrong merges before any model): "
                    f"{r['different_exact']}", ""]
        out += ["| Threshold | Recall | Different as candidates | Candidate pairs | Largest component | "
                "Twin pairs as candidates |", "|---|---|---|---|---|---|"]
        out += [f"| {g['threshold']} | {g['recall']} | {g['different_as_candidates']} | {g['candidate_pairs']} | "
                f"{g['largest_component']} | {g['twin_candidates']} |" for g in r["grid"]]
        out += ["", "| Kind | Same | n | exact | alias | mean | min | max |", "|---|---|---|---|---|---|---|---|"]
        out += [f"| {k['kind']} | {k['same']} | {k['n']} | {k['exact']} | {k['alias']} | {k['mean']} | {k['min']} | "
                f"{k['max']} |" for k in r["per_kind"]]
        if r["missed_at_target"]:
            out += ["", "Same pairs missed at the chosen threshold: "
                    + "; ".join(f"{m['a']} - {m['b']} ({m['kind']}, {m['sim']})" for m in r["missed_at_target"])]
        if b:
            out += ["", f"At threshold {b['threshold']}: largest cluster {b['largest_cluster']} entries (cap "
                    f"{b.get('cap', '')}).",
                    "", "Different pairs that become candidates: "
                    + ("; ".join(f"{m['a']} - {m['b']} ({m['kind']}, {m['how']}, {m['sim']})"
                                 for m in b["different_candidates"]) or "none"),
                    "", "Same pairs the cap cuts: "
                    + ("; ".join(f"{m['a']} - {m['b']} ({m['kind']}, {m['sim']})" for m in b["same_cut_pairs"])
                       or "none"),
                    "", f"Twin pairs (same segment, identical facts) that become candidates, {b['twin_candidates']} "
                    f"of {r['twin_pairs']}: "
                    + ("; ".join(f"{m['segment']} {m['names'][0]} - {m['names'][1]}" for m in b["twin_candidate_pairs"])
                       or "none")]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course")
    ap.add_argument("--pairs", default=str(HERE / "pairs.json"))
    ap.add_argument("--models", default=",".join(MODELS), help="comma-separated model IDs ('fake' for a test)")
    ap.add_argument("--recall", type=float, default=0.95, help="recall target for the threshold (default 0.95)")
    ap.add_argument("--json", default=str(HERE / "embed_compare.json"))
    ap.add_argument("--report", default=str(HERE / "report_embed.md"))
    ap.add_argument("--cache", default=str(HERE / "embed_cache.jsonl"))
    ap.add_argument("--pipeline", default=str(REPO / "pipeline"), help="the pipeline folder (its scripts and output)")
    ap.add_argument("--device")
    a = ap.parse_args()
    sys.path.insert(0, a.pipeline)
    from scripts import s3a_candidates as s3a           # noqa: E402  (the pipeline given)
    from scripts.embed import Embedder, INSTRUCT        # noqa: E402
    import re
    pairs = json.loads(Path(a.pairs).read_text())["pairs"]
    results = []
    for model in a.models.split(","):
        runs = [(opt, s3a.instruction(opt)) for opt in s3a.EMBED_OPTIONS]
        if any(re.search(p, model) for p in INSTRUCT):
            runs += [("defining", s3a.INSTRUCTION_FACTS), (s3a.EMBED_OPTION, None)]
        for option, instr in runs:
            results.append(evaluate(s3a, Embedder, a.course, pairs, model, option, instr, Path(a.cache), a.recall,
                                    a.device))
            r = results[-1]
            b = r["at_target"] or {}
            print(f"{model}, embed facts {option}, instruction: {instruction_label(r)}: threshold for recall >= "
                  f"{a.recall:.0%}: {b.get('threshold', 'not reached')}, {b.get('candidate_pairs', '-')} candidate "
                  f"pairs, {b.get('twin_candidates', '-')} of {r['twin_pairs']} twin pairs as candidates", flush=True)
    Path(a.json).write_text(json.dumps({"pairs": len(pairs), "recall_target": a.recall, "results": results},
                                       indent=1, ensure_ascii=False) + "\n")
    text = report(results, a.recall, len(pairs))
    Path(a.report).write_text(text)
    print(text.split("\n## ", 1)[0])


if __name__ == "__main__":
    main()
