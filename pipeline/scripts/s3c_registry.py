"""Stage 3c: the concept registry, step 4: one concept per group, and the relationships rebuilt over the concepts.

    python scripts/s3c_registry.py nptel_vr [--out DIR]

Reads   output/<course>/stage_3_registry/clusters.json   (s3a's entries, s3b's groups)
        output/<course>/stage_2c_concepts/concept_maps/lec_<n>.json, relations/lec_<n>.json
Writes  output/<course>/stage_3_registry/ (or --out)
          concepts.json          {"C0001": {"name", "aliases", "facts", "lectures", "segments", "defined_in",
                                            "merged": [{"segment_concept", "name", "how", "reason"}]}}
          segment_concepts.json  {"1/S1/C0": "C0001", ...}  every segment concept
          relations.json         {"R0001": {"subject": "C0001", "label", "object": "C0002", "facts", "segments",
                                            "from": [segment relationship IDs]}}
          decisions.jsonl        one line per merge, per cluster kept apart, per relationship dropped or joined
          text/registry.txt      the concepts with their merges, the relationships, what was dropped

No model, no randomness: the same clusters.json and 2c outputs always give the same files.

Concepts. Each group of the model (s3b) is one concept; an entry outside every cluster, or in a cluster without an
answer, is one concept by itself. A cluster whose answer is unresolved (every attempt failed its check) has the groups
of its best answer as s3b repaired them. Concepts are numbered C0001... in course order: by their first segment
concept (lecture order, then segment, then concept index). A concept's
  name      the group's name (the model's choice) or the entry's name (the wording most of its segment concepts use)
  aliases   every other name and alias of its segment concepts, in course order (a repeat that differs only in
            case is dropped)
  facts, lectures, segments   joined, in course order; defined_in: the segments whose segment concept had defined
  merged    every segment concept in it, in course order, with how it came in:
            "first"  the concept's first segment concept
            "exact"  same normalised name as the first segment concept of its entry (step 1)
            "model"  the first segment concept of another entry the model grouped with it (step 3; the model's reason)
Relationships. Every segment relationship of 2c, in course order, is mapped through segment_concepts.json: its ends
renamed to concepts. One whose two ends are now the same concept is dropped; one with an end missing from the map is
dropped (neither should happen silently: both are logged). Relationships with the same subject, label (case and
spacing ignored; the first wording is kept) and object are one relationship, numbered R0001... in order of first
appearance, with the facts, segments and segment relationship IDs of all of them.
decisions.jsonl kinds: exact, model (a segment concept joined, with "into": the concept's first segment concept),
separate (a group of one in a cluster: the model's reason), no_answer (an entry of a cluster without an answer, kept
apart), unresolved (one line per cluster whose answer was kept with problems: the problems; its model and separate
lines carry "unresolved": true), self_loop, missing_end (a segment relationship dropped), joined (a segment
relationship joined into an earlier one).
Every segment relationship is either in exactly one relationship's "from" or in one self_loop/missing_end line.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import lectures as lec, s2c_concepts as s2c, s3a_candidates as s3a  # noqa: E402

order, seg_order, segment_of = s3a.sc_order, s3a.seg_order, s3a.segment_of


def load_relations(course: str, keys: list[str]) -> dict:
    out = {}
    for k in keys:
        p = s2c.out_dir(course) / "relations" / f"{lec.stem_of(k)}.json"
        if p.exists():
            out.update(json.loads(p.read_text()))
    return dict(sorted(out.items(), key=lambda kv: order(kv[0])))


def label_key(label: str) -> str:
    return " ".join(label.lower().split())


# ---------------------------------------------------------------- concepts
NO_MODEL = False   # --no-model (MVP, 2026-11-13): build the registry from the exact merges of 3a only, without 3b


def groups_of(data: dict) -> list[dict]:
    """Every group: {"entries", "name", "how": "model" | None, "reason", "cluster"}; entries outside the clusters
    are groups of one."""
    out, covered = [], set()
    for kid, k in data["clusters"].items():
        if "groups" not in k:
            if NO_MODEL:                  # MVP: no 3b answers; the cluster's entries stay apart (groups of one below)
                continue
            sys.exit(f"cluster {kid} has no groups: run s3b first")
        for g in k["groups"]:
            out.append({"entries": g["entries"], "name": g["name"], "reason": g["reason"], "cluster": kid,
                        "no_answer": k.get("no_answer", False), "unresolved": bool(k.get("unresolved")),
                        "errors": k.get("errors", [])})
            covered |= set(g["entries"])
    for eid, e in data["entries"].items():
        if eid not in covered:
            out.append({"entries": [eid], "name": e["name"], "reason": "", "cluster": None, "no_answer": False,
                        "unresolved": False, "errors": []})
    return out


def build_concepts(data: dict, concepts2c: dict) -> tuple[dict, dict, list[dict]]:
    """concepts.json, segment_concepts.json and the merge decisions."""
    E = data["entries"]
    groups = groups_of(data)
    for g in groups:
        g["members"] = sorted((m for e in g["entries"] for m in E[e]["members"]), key=order)
    groups.sort(key=lambda g: order(g["members"][0]))
    entry_of = {m: eid for eid, e in E.items() for m in e["members"]}
    concepts, sc_map, decisions = {}, {}, []
    for kid, k in data["clusters"].items():
        if k.get("unresolved"):
            decisions.append({"kind": "unresolved", "cluster": kid, "entries": k["entries"],
                              "reason": "; ".join(k["unresolved"])})
    for i, g in enumerate(groups, 1):
        cid = f"C{i:04d}"
        first = g["members"][0]
        merged = []
        for m in g["members"]:
            c, entry = concepts2c[m], E[entry_of[m]]
            if m == first:
                how, reason = "first", ""
            elif m != entry["members"][0]:
                head = entry["members"][0]
                how, reason = "exact", f"same normalised name as {head} ({concepts2c[head]['name']})"
                decisions.append({"kind": "exact", "concept": cid, "segment_concept": m, "name": c["name"],
                                  "into": head, "reason": reason})
            else:
                how, reason = "model", g["reason"]
                decisions.append({"kind": "model", "concept": cid, "segment_concept": m, "name": c["name"],
                                  "into": first, "cluster": g["cluster"], "entries": g["entries"],
                                  "reason": reason, **({"unresolved": True} if g["unresolved"] else {})})
            merged.append({"segment_concept": m, "name": c["name"], "how": how, "reason": reason})
            sc_map[m] = cid
        if g["cluster"] and len(g["entries"]) == 1:
            decisions.append({"kind": "no_answer" if g["no_answer"] else "separate", "concept": cid,
                              "cluster": g["cluster"], "entries": g["entries"], "segment_concepts": g["members"],
                              "reason": "; ".join(g["errors"]) if g["no_answer"] else g["reason"],
                              **({"unresolved": True} if g["unresolved"] else {})})
        aliases, seen = [], {g["name"].lower()}
        for m in g["members"]:                     # course order of the segment concepts' names
            for x in [concepts2c[m]["name"]] + concepts2c[m]["aliases"]:
                x = x.strip()
                if x and x.lower() not in seen:
                    seen.add(x.lower())
                    aliases.append(x)
        concepts[cid] = {
            "name": g["name"],
            "aliases": aliases,
            "facts": sorted({f for m in g["members"] for f in concepts2c[m]["facts"]}, key=order),
            "lectures": sorted({m.split("/", 1)[0] for m in g["members"]}, key=lec.order),
            "segments": sorted({segment_of(m) for m in g["members"]}, key=seg_order),
            "defined_in": sorted({segment_of(m) for m in g["members"] if concepts2c[m]["defined"]}, key=seg_order),
            "merged": merged,
        }
    return concepts, sc_map, decisions


# ---------------------------------------------------------------- relationships
def build_relations(rel2c: dict, sc_map: dict, concepts2c: dict) -> tuple[dict, list[dict]]:
    out, by_key, decisions = {}, {}, []
    for rid, r in rel2c.items():
        s, o = sc_map.get(r["subject"]), sc_map.get(r["object"])
        if s is None or o is None:
            missing = [e for e in (r["subject"], r["object"]) if e not in sc_map]
            decisions.append({"kind": "missing_end", "relation": rid, "label": r["label"],
                              "reason": f"no concept for {', '.join(missing)}"})
            continue
        if s == o:
            decisions.append({"kind": "self_loop", "relation": rid, "concept": s, "label": r["label"],
                              "reason": f"both ends ({r['subject']} {concepts2c[r['subject']]['name']}, "
                                        f"{r['object']} {concepts2c[r['object']]['name']}) are now {s}"})
            continue
        key = (s, label_key(r["label"]), o)
        if key in by_key:
            new = out[by_key[key]]
            decisions.append({"kind": "joined", "relation": rid, "into": by_key[key],
                              "reason": f"same subject, label and object as {new['from'][0]}"})
        else:
            by_key[key] = f"R{len(out) + 1:04d}"
            new = out[by_key[key]] = {"subject": s, "label": r["label"], "object": o, "facts": [], "segments": [],
                                      "from": []}
        new["from"].append(rid)
        new["facts"] = sorted(set(new["facts"]) | set(r["facts"]), key=order)
        new["segments"] = sorted(set(new["segments"]) | {segment_of(rid)}, key=seg_order)
    return out, decisions


# ---------------------------------------------------------------- text view
def write_text(od: Path, concepts: dict, relations: dict, decisions: list[dict], totals: dict):
    lines = [f"{totals['segment_concepts']} segment concepts -> {totals['concepts']} concepts "
             f"({totals['exact']} exact merges, {totals['model']} model merges); {totals['segment_relations']} "
             f"segment relationships -> {totals['relations']} relationships ({totals['joined']} joined, "
             f"{totals['self_loop']} self-loops and {totals['missing_end']} with a missing end dropped); "
             f"{totals['pairs_several_labels']} concept pairs with several labels", ""]
    for cid, c in concepts.items():
        lines.append(f"{cid}  {c['name']}" + (f"  ({', '.join(c['aliases'])})" if c["aliases"] else ""))
        lines.append(f"       lectures {', '.join(c['lectures'])}; defined in {', '.join(c['defined_in']) or '-'}; "
                     f"{len(c['facts'])} facts")
        if len(c["merged"]) > 1:
            for m in c["merged"]:
                lines.append(f"       {m['segment_concept']:<10} {m['name']:<32} {m['how']}"
                             + (f": {m['reason']}" if m["how"] == "model" else ""))
    lines += ["", "Relationships"]
    name = {cid: c["name"] for cid, c in concepts.items()}
    for rid, r in relations.items():
        lines.append(f"{rid}  {name[r['subject']]} | {r['label']} | {name[r['object']]}  "
                     f"({r['subject']} -> {r['object']}; facts {', '.join(r['facts'])}; from {', '.join(r['from'])})")
    dropped = [d for d in decisions if d["kind"] in ("self_loop", "missing_end")]
    if dropped:
        lines += ["", "Dropped segment relationships"]
        lines += [f"{d['relation']}  {d['label']}: {d['kind']}: {d['reason']}" for d in dropped]
    unresolved = [d for d in decisions if d["kind"] == "unresolved"]
    if unresolved:
        lines += ["", "Clusters with an unresolved answer (the best answer kept, repaired in code)"]
        lines += [f"{d['cluster']}  {', '.join(d['entries'])}: {d['reason']}" for d in unresolved]
    apart = [d for d in decisions if d["kind"] == "no_answer"]
    if apart:
        lines += ["", "Clusters without an answer (kept apart)"]
        lines += [f"{d['cluster']}  {d['concept']} {name[d['concept']]}: {d['reason']}" for d in apart]
    (od / "text").mkdir(parents=True, exist_ok=True)
    (od / "text" / "registry.txt").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- run
def run(course: str, out: Path | None = None) -> dict:
    t0 = time.time()
    od = Path(out) if out else s3a.out_dir(course)
    data = s3a.load(od, course)
    keys = data["settings"]["lectures"]
    concepts2c, rel2c = s3a.load_concepts(course, keys), load_relations(course, keys)
    concepts, sc_map, dec_c = build_concepts(data, concepts2c)
    relations, dec_r = build_relations(rel2c, sc_map, concepts2c)
    decisions = dec_c + dec_r
    kinds = {k: sum(d["kind"] == k for d in decisions)
             for k in ("exact", "model", "separate", "no_answer", "unresolved", "self_loop", "missing_end", "joined")}
    pairs: dict[tuple, set] = {}
    for r in relations.values():
        pairs.setdefault(tuple(sorted((r["subject"], r["object"]))), set()).add(label_key(r["label"]))
    totals = {"segment_concepts": len(concepts2c), "concepts": len(concepts), "segment_relations": len(rel2c),
              "relations": len(relations), **kinds,
              "pairs_several_labels": sum(len(v) > 1 for v in pairs.values())}
    dump = lambda obj: json.dumps(obj, indent=1, ensure_ascii=False) + "\n"   # noqa: E731
    (od / "concepts.json").write_text(dump(concepts))
    (od / "segment_concepts.json").write_text(dump(sc_map))
    (od / "relations.json").write_text(dump(relations))
    (od / "decisions.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in decisions))
    write_text(od, concepts, relations, decisions, totals)
    totals["wall_s"] = round(time.time() - t0, 1)
    print(f"3c: {totals['segment_concepts']} segment concepts -> {totals['concepts']} concepts ({kinds['exact']} exact, "
          f"{kinds['model']} model merges; {kinds['unresolved']} clusters with an unresolved answer; "
          f"{kinds['no_answer']} entries kept apart without an answer); "
          f"{totals['segment_relations']} segment relationships -> {totals['relations']} ({kinds['joined']} joined, "
          f"{kinds['self_loop']} self-loops, {kinds['missing_end']} missing ends dropped); "
          f"{totals['pairs_several_labels']} concept pairs with several labels")
    return totals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--out", help="the stage folder (default: output/<course>/stage_3_registry)")
    ap.add_argument("--no-model", action="store_true",
                    help="clusters without 3b answers keep their entries apart (MVP: the registry from exact merges)")
    a = ap.parse_args()
    global NO_MODEL
    NO_MODEL = a.no_model
    run(a.course, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
