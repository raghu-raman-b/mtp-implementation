"""Stage 4c: the lecture graph (which lectures each lecture needs) and "what is needed before lecture N". Code only.

    python scripts/s4c_lecture_graph.py nptel_vr [--hub-share 0.25 --hub-min-lectures 3 --hub-floor 0.1 --min-weight 1]

Reads   output/<course>/stage_3_registry/concepts.json          (lectures and defined_in of every concept)
        output/<course>/stage_2c_concepts/concept_maps/lec_<n>.json   (the lectures of the run; defining facts)
        output/<course>/stage_2b_verify_facts/fact_maps/lec_<n>.json  (the texts of the defining facts)
        output/<course>/stage_4a_definitions/definitions.json   (the definitions; optional: null without it)
        input/<course>/input/titles.tsv
Writes  output/<course>/stage_4c_lecture_graph/
          graph.json         params, lectures, per concept its lectures, defining lectures and weight, the links,
                             the prerequisites of each lecture, its concepts by kind, and each concept's path
          needed/lec_<n>.json  what is needed before the lecture, with names, definitions and defining facts
          graph.txt          the hub concepts; the links whose concepts are all redefined; per lecture: direct and all
                             prerequisites, indirect and weak links, its concepts by kind
          checks.json        totals and the checks of the graph against its own rules (below)

Definitions. A lecture uses a concept when the concept's registry "lectures" names it; a lecture defines it when one
of its segments is in the concept's "defined_in".
- Link K -> L: K comes before L and L uses a concept that K defines. The link carries those concepts. (A concept L
  also defines itself still counts, as the plan states the rule; the link lists such concepts under "redefined".
  Decision D11, 2026-11-13: links are directed, earlier to later; the rule is kept, and graph.txt and checks.json
  list the links whose concepts are all redefined, the links that leaving such concepts out would remove.)
- Weight. A concept used in many lectures counts for less, so that not every lecture depends on the lecture that
  defines a concept everyone uses. With N lectures in the run and n the lectures that use the concept:
      free = max(hub_min_lectures, hub_share * N)
      w = 1                                                   if n <= free
      w = 1 - (1 - hub_floor) * (n - free) / (N - free)       otherwise (falls linearly to hub_floor at n = N)
  Defaults: hub_share 0.25, hub_min_lectures 3, hub_floor 0.1. A concept with w < 1 is a hub concept.
  A link's weight is the sum of its concepts' weights. A link is a prerequisite ("strong") when its weight is at
  least min_weight (default 1: one ordinary concept, or several hub concepts); otherwise it is "weak": kept and
  listed, but not a prerequisite.
- Direct prerequisites: the strong links not implied through another lecture (K -> L is "indirect" when a path of
  strong links K -> M -> ... -> L exists; this is the transitive reduction, unique since links go forward in time).
  All prerequisites of L: every lecture with a path of strong links to L.
- A lecture's concepts, by kind (a partition of the concepts it uses): introduced (the first lecture that defines it
  is this one), met_again (first defined in an earlier lecture), defined_later (used here, first defined in a later
  lecture), assumed (never defined in the course).
- What is needed before lecture N: its direct prerequisites (with the concepts each link carries), all earlier
  prerequisites, the met_again concepts with their definition (4a) and defining facts (registry merged segment
  concepts with defined=true), the assumed concepts, and the defined_later ones.
- A concept's path: the lectures that lead to it: all prerequisites of the first lecture that defines it, then that
  lecture, in course order (empty for a concept the course never defines).

Checks (the graph against its own rules; any entry here is a bug): backward_link (a link not forward in course
order), direct_implied (a direct link that another path implies), indirect_not_implied (an indirect link no path
implies), weight_mismatch (a link's kind against its weight), wrong_concepts (a link carrying a concept the later
lecture does not use or the earlier one does not define). Reported: the hub concepts, lectures with no prerequisite,
the links whose concepts are all redefined (all_redefined).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, lectures as lec  # noqa: E402
from scripts import s4a_definitions as s4a  # noqa: E402

DEFAULTS = {"hub_share": 0.25, "hub_min_lectures": 3, "hub_floor": 0.1, "min_weight": 1.0}


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_4c_lecture_graph"


# ---------------------------------------------------------------- the graph (pure functions)
def concept_lectures(concepts: dict, keys: list[str]) -> tuple[dict, dict]:
    """{cid: lectures that use it}, {cid: lectures that define it}, both in course order and within keys."""
    kset = set(keys)
    uses = {cid: sorted({k for k in c["lectures"] if k in kset}, key=lec.order) for cid, c in concepts.items()}
    defines = {cid: sorted({s4a.lecture_of(s) for s in c.get("defined_in", []) if s4a.lecture_of(s) in kset},
                           key=lec.order) for cid, c in concepts.items()}
    return uses, defines


def weight(n: int, total: int, p: dict) -> float:
    """The weight of a concept used in n of the total lectures (see the module docstring)."""
    free = max(p["hub_min_lectures"], p["hub_share"] * total)
    if n <= free or total <= free:
        return 1.0
    return 1.0 - (1.0 - p["hub_floor"]) * (n - free) / (total - free)


def reach(succ: dict, start: str) -> set:
    """Every lecture reachable from start along the edges in succ (start itself not included)."""
    seen, todo = set(), list(succ.get(start, ()))
    while todo:
        x = todo.pop()
        if x not in seen:
            seen.add(x)
            todo += succ.get(x, ())
    return seen


def build(concepts: dict, keys: list[str], params: dict | None = None) -> dict:
    """The lecture graph of the run: links, prerequisites, each lecture's concepts by kind, each concept's path."""
    p = dict(DEFAULTS, **(params or {}))
    keys = sorted(keys, key=lec.order)
    pos = {k: i for i, k in enumerate(keys)}
    uses, defines = concept_lectures(concepts, keys)
    w = {cid: weight(len(uses[cid]), len(keys), p) for cid in concepts}
    used_in = {k: [cid for cid in concepts if k in uses[cid]] for k in keys}
    links = []
    for L in keys:
        for K in keys[:pos[L]]:
            carried = [cid for cid in used_in[L] if K in defines[cid]]
            if carried:
                total = round(sum(w[c] for c in carried), 6)
                links.append({"from": K, "to": L, "concepts": carried,
                              "redefined": [c for c in carried if L in defines[c]], "weight": total,
                              "kind": "strong" if total >= p["min_weight"] else "weak"})
    succ = {}
    for ln in links:
        if ln["kind"] == "strong":
            succ.setdefault(ln["from"], []).append(ln["to"])
    for ln in links:
        if ln["kind"] == "strong":
            via = [m for m in succ[ln["from"]] if m != ln["to"] and ln["to"] in reach(succ, m)]
            ln["kind"] = "indirect" if via else "direct"
    pred = {}
    for a, bs in succ.items():
        for b in bs:
            pred.setdefault(b, []).append(a)
    prereq = {L: {"direct": sorted((ln["from"] for ln in links if ln["to"] == L and ln["kind"] == "direct"),
                                   key=lec.order),
                  "all": sorted(reach(pred, L), key=lec.order)} for L in keys}
    kinds = {}
    for L in keys:
        k = {"introduced": [], "met_again": [], "defined_later": [], "assumed": []}
        for cid in used_in[L]:
            first = defines[cid][0] if defines[cid] else None
            kind = ("assumed" if first is None else "introduced" if first == L
                    else "met_again" if pos[first] < pos[L] else "defined_later")
            k[kind].append(cid)
        kinds[L] = k
    paths = {}
    for cid in concepts:
        first = defines[cid][0] if defines[cid] else None
        paths[cid] = {"first_defined": first,
                      "path": sorted(prereq[first]["all"] + [first], key=lec.order) if first else []}
    return {"params": p, "lectures": keys,
            "concepts": {cid: {"lectures": len(uses[cid]), "defined_in": defines[cid], "weight": round(w[cid], 4)}
                         for cid in concepts},
            "links": links, "prerequisites": prereq, "concept_kinds": kinds, "concept_paths": paths}


def verify(graph: dict, concepts: dict | None = None) -> dict:
    """The graph against its own rules, computed afresh; every entry is a problem."""
    keys = graph["lectures"]
    pos = {k: i for i, k in enumerate(keys)}
    prob = {"backward_link": [], "direct_implied": [], "indirect_not_implied": [], "weight_mismatch": [],
            "wrong_concepts": []}
    strong = [ln for ln in graph["links"] if ln["kind"] in ("direct", "indirect")]
    succ = {}
    for ln in strong:
        succ.setdefault(ln["from"], set()).add(ln["to"])
    uses, defines = concept_lectures(concepts, keys) if concepts else ({}, {})
    for ln in graph["links"]:
        name = f"{ln['from']} -> {ln['to']}"
        if pos[ln["from"]] >= pos[ln["to"]]:
            prob["backward_link"].append(name)
        if (ln["kind"] == "weak") != (ln["weight"] < graph["params"]["min_weight"]):
            prob["weight_mismatch"].append(name)
        if ln["kind"] in ("direct", "indirect"):
            implied = any(ln["to"] in reach(succ, m) for m in succ.get(ln["from"], ()) if m != ln["to"])
            if ln["kind"] == "direct" and implied:
                prob["direct_implied"].append(name)
            if ln["kind"] == "indirect" and not implied:
                prob["indirect_not_implied"].append(name)
        if concepts and any(ln["to"] not in uses[c] or ln["from"] not in defines[c] for c in ln["concepts"]):
            prob["wrong_concepts"].append(name)
    return {k: v for k, v in prob.items() if v}


# ---------------------------------------------------------------- run
def needed_before(course: str, L: str, graph: dict, concepts: dict, defs: dict, texts: dict, cmaps: dict) -> dict:
    """What is needed before lecture L, with names, definitions and defining facts."""
    title = lambda k: course_meta.lecture_title(course, k)  # noqa: E731
    name = lambda c: concepts[c]["name"]  # noqa: E731
    direct = [ln for ln in graph["links"] if ln["to"] == L and ln["kind"] == "direct"]
    kinds = graph["concept_kinds"][L]

    def entry(cid: str) -> dict:
        d = defs.get(cid, {})
        return {"concept": cid, "name": name(cid), "defined_in": graph["concepts"][cid]["defined_in"],
                "weight": graph["concepts"][cid]["weight"], "definition": d.get("definition") or None,
                "defining_facts": [{"fact": f, "text": texts[f]["text"]}
                                   for f in s4a.defining_facts(concepts[cid], cmaps) if f in texts]}

    return {"lecture": L, "title": title(L),
            "direct": [{"lecture": ln["from"], "title": title(ln["from"]), "weight": ln["weight"],
                        "concepts": [{"concept": c, "name": name(c)} for c in ln["concepts"]]} for ln in direct],
            "all": [{"lecture": k, "title": title(k)} for k in graph["prerequisites"][L]["all"]],
            "concepts": [entry(c) for c in kinds["met_again"]],
            "never_defined": [{"concept": c, "name": name(c), "definition": defs.get(c, {}).get("definition") or None}
                              for c in kinds["assumed"]],
            "defined_later": [{"concept": c, "name": name(c), "first_defined": graph["concepts"][c]["defined_in"][0]}
                              for c in kinds["defined_later"]],
            "introduced": [{"concept": c, "name": name(c)} for c in kinds["introduced"]]}


def all_redefined(graph: dict) -> list[dict]:
    """The links every concept of which the later lecture defines again itself (decision D11: reported)."""
    return [ln for ln in graph["links"] if ln["concepts"] and set(ln["redefined"]) == set(ln["concepts"])]


def graph_text(course: str, graph: dict, concepts: dict) -> str:
    name = lambda c: concepts[c]["name"]  # noqa: E731
    p = graph["params"]
    out = [f"params: hub_share {p['hub_share']}, hub_min_lectures {p['hub_min_lectures']}, hub_floor {p['hub_floor']},"
           f" min_weight {p['min_weight']}; {len(graph['lectures'])} lectures", "hub concepts (weight < 1):"]
    hubs = sorted((c for c, v in graph["concepts"].items() if v["weight"] < 1), key=lambda c: graph["concepts"][c]["weight"])
    out += [f"  {c} {name(c)}: {graph['concepts'][c]['lectures']} lectures, weight {graph['concepts'][c]['weight']}"
            for c in hubs] or ["  none"]
    out.append("links whose concepts are all redefined by the later lecture (counted; leaving such concepts out would "
               "remove them):")
    out += [f"  {ln['from']} -> {ln['to']} ({ln['kind']}): {', '.join(map(name, ln['concepts']))}"
            for ln in all_redefined(graph)] or ["  none"]
    for L in graph["lectures"]:
        out += ["", f"LECTURE {L}: {course_meta.lecture_title(course, L)}"]
        for kind, label in (("direct", "direct"), ("indirect", "indirect"), ("weak", "weak")):
            ls = [ln for ln in graph["links"] if ln["to"] == L and ln["kind"] == kind]
            if ls:
                out.append(f"  {label}: " + "; ".join(f"{ln['from']} ({', '.join(map(name, ln['concepts']))}; "
                                                       f"{ln['weight']})" for ln in ls))
        out.append(f"  all prerequisites: {', '.join(graph['prerequisites'][L]['all']) or 'none'}")
        for kind, cs in graph["concept_kinds"][L].items():
            if cs:
                out.append(f"  {kind}: {', '.join(map(name, cs))}")
    return "\n".join(out) + "\n"


def run(course: str, params: dict | None = None) -> dict:
    reg = s4a.load_registry(course)
    concepts = reg["concepts"]
    keys = sorted(set(lec.keys(s4a.stage_dir(course, "stage_2c_concepts") / "concept_maps"))
                  | set(s4a.registry_lectures(reg)), key=lec.order)
    graph = build(concepts, keys, params)
    dp = s4a.out_dir(course) / "definitions.json"
    defs = json.loads(dp.read_text()) if dp.exists() else {}
    texts, cmaps = s4a.load_facts(course, keys), s4a.load_concept_maps(course, keys)
    od = out_dir(course)
    (od / "needed").mkdir(parents=True, exist_ok=True)
    (od / "graph.json").write_text(json.dumps(graph, indent=1, ensure_ascii=False) + "\n")
    for L in keys:
        (od / "needed" / f"{lec.stem_of(L)}.json").write_text(
            json.dumps(needed_before(course, L, graph, concepts, defs, texts, cmaps), indent=1, ensure_ascii=False) + "\n")
    (od / "graph.txt").write_text(graph_text(course, graph, concepts))
    problems = verify(graph, concepts)
    count = lambda kind: sum(ln["kind"] == kind for ln in graph["links"])  # noqa: E731
    totals = {"lectures": len(keys), "links": len(graph["links"]), "direct": count("direct"),
              "indirect": count("indirect"), "weak": count("weak"),
              "hub_concepts": sum(v["weight"] < 1 for v in graph["concepts"].values()),
              "no_prerequisite": [L for L in keys if not graph["prerequisites"][L]["all"]],
              "needs_first_lecture": [L for L in keys if keys and keys[0] in graph["prerequisites"][L]["direct"]],
              "assumed_concepts": sorted({c for k in graph["concept_kinds"].values() for c in k["assumed"]}),
              "all_redefined": [f"{ln['from']} -> {ln['to']}" for ln in all_redefined(graph)],
              "definitions": "4a definitions.json found" if defs else "no 4a definitions.json: definitions are null"}
    (od / "checks.json").write_text(json.dumps({"totals": totals, "problems": problems}, indent=1,
                                               ensure_ascii=False) + "\n")
    print(f"4c: {len(keys)} lectures, {totals['direct']} direct, {totals['indirect']} indirect, {totals['weak']} weak "
          f"links; {totals['hub_concepts']} hub concepts; {len(totals['assumed_concepts'])} concepts never defined")
    print(f"problems: {problems or 'none'}")
    return totals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--hub-share", type=float, default=DEFAULTS["hub_share"],
                    help="a concept used in at most this share of the lectures has full weight")
    ap.add_argument("--hub-min-lectures", type=int, default=DEFAULTS["hub_min_lectures"],
                    help="... or in at most this many lectures (so a short run has no hubs)")
    ap.add_argument("--hub-floor", type=float, default=DEFAULTS["hub_floor"],
                    help="the weight of a concept used in every lecture")
    ap.add_argument("--min-weight", type=float, default=DEFAULTS["min_weight"],
                    help="a link with at least this weight is a prerequisite")
    a = ap.parse_args()
    run(a.course, {"hub_share": a.hub_share, "hub_min_lectures": a.hub_min_lectures, "hub_floor": a.hub_floor,
                   "min_weight": a.min_weight})


if __name__ == "__main__":
    main()
