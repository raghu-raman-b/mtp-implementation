"""Stage 4d: assemble the knowledge layer, output/<course>/knowledge/, from stages 0a to 4c, and check it. Code only.

    python scripts/s4d_assemble.py nptel_vr [--embed-model Qwen/Qwen3-Embedding-0.6B]
    python scripts/s4d_assemble.py nptel_vr --check        (check an existing knowledge/ only)

Reads   stage_3_registry/ (concepts, segment_concepts, relations), stage_2c_concepts/concept_maps/,
        stage_2b_verify_facts/fact_maps/, stage_1b_verify_segments/segment_maps/, stage_0a_preprocess/times/,
        stage_4a_definitions/definitions.json, stage_4b_goals/ (lecture_goals/, course_goals.json),
        stage_4c_lecture_graph/graph.json, input/<course>/input/ (course.json, titles.tsv)
Schema  schemas/knowledge.schema.json (checked by scripts/schema_check.py; jsonschema is not installed)
Embeds  the fact texts with scripts.embed.Embedder (default Qwen/Qwen3-Embedding-0.6B; "fake" for tests), cached
        in stage_4d_assemble/embed_cache.jsonl
Writes  output/<course>/knowledge/   (rebuilt from scratch on every run: it is wholly derived)
          index.json            course, lectures, the files, counts, the embedding model, how names are keyed
          names.json            the name index: every name, alias and acronym, keyed by name_key(), to its concepts
                                {"head mounted display": [{"concept": "C0004", "as": "name", "text": "..."}]}
          concepts.json         a card per concept: name, aliases, acronyms, definition, defined, where it is defined
                                (lecture, segment, time from its defining facts' sentences), facts (defining ones
                                first), defining facts, the facts the definition is built from, misplaced facts, its
                                relationships in both directions, the lectures that use it, the merge record
          relations.json        the relationships (subject, label, object, facts, segments)
          facts.json            the fact store: text, evidence, segment, lecture, time, concepts
          fact_embeddings.json  {"model", "dim", "vectors": {fact ID: [floats]}} (apart, so facts.json stays small)
          lectures/lec_<n>.json per lecture: its segments (sentences, times, sub-goal, objective, facts, concepts),
                                its concepts introduced, met again, defined later, assumed; its own concept map (the
                                concepts it uses, the relationships of its segments); its goal and objectives; the
                                course goals it serves; its prerequisites
          goals.json            the goal tree: course goals -> lectures -> lecture goals -> objectives -> segments ->
                                facts and concepts
          lecture_graph.json    4c's graph: links, prerequisites, each lecture's concepts by kind, and for each concept
                                the path of lectures that leads to it
          assumed.json          the course's assumed knowledge: concepts used but never defined
        output/<course>/stage_4d_assemble/checks.json   the schema errors, broken references and coverage problems

The check (also run alone with --check): every file against its definition in the schema; then every reference in
the whole layer (concept, relationship, fact, segment, sentence, lecture, objective, lecture goal, course goal)
against the IDs the layer defines (sentences: the first..last range of each segment); IDs defined twice; and
coverage: a concept without a card, a fact without a vector, vectors of different lengths, a concept missing from
the name index. Exit status 1 when anything is found.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, lectures as lec, s2a_fact_extraction as s2a  # noqa: E402
from scripts import s4a_definitions as s4a, s4b_goals as s4b, s4c_lecture_graph as s4c  # noqa: E402
from scripts import fact_checks  # noqa: E402
from scripts.schema_check import Checker  # noqa: E402

SCHEMA = ROOT / "schemas" / "knowledge.schema.json"
EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
NAME_KEY = ("lower case; hyphens and underscores become spaces; runs of spaces become one; surrounding spaces and "
            "punctuation removed (no plural folding: a lookup should also try the singular)")


def knowledge_dir(course: str) -> Path:
    return ROOT / "output" / course / "knowledge"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_4d_assemble"


# ---------------------------------------------------------------- names
def name_key(name: str) -> str:
    s = re.sub(r"[-_]", " ", name.lower())
    return re.sub(r"\s+", " ", s).strip(" .,;:!?\"'()[]{}")


def is_acronym(s: str) -> bool:
    """"XR", "HMD", "3D", "HMDs", "FoV": the one shared test, is_acronym of scripts/fact_checks.py (decision D8: a
    product name such as "HoloLens" is not an acronym)."""
    return fact_checks.is_acronym(s.strip())


def split_acronym(s: str) -> tuple[str, str | None]:
    """"head-mounted display (HMD)" -> ("head-mounted display", "HMD"); otherwise (s, None)."""
    m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", s.strip())
    if m and is_acronym(m[2]):
        return m[1].strip(), m[2].strip()
    return s.strip(), None


def name_entries(c: dict) -> list[tuple[str, str]]:
    """(as, text) for every name of a concept: its name, aliases and acronyms."""
    out = []
    for kind, text in [("name", c["name"])] + [("alias", a) for a in c["aliases"]]:
        full, acr = split_acronym(text)
        if acr:
            out += [(kind, text), (kind, full), ("acronym", acr)]
        else:
            out.append(("acronym" if kind == "alias" and is_acronym(text) else kind, text))
    return out


def name_index(concepts: dict) -> dict:
    idx: dict[str, list] = {}
    for cid, c in concepts.items():
        for kind, text in name_entries(c):
            key = name_key(text)
            if key and not any(e["concept"] == cid for e in idx.get(key, [])):
                idx.setdefault(key, []).append({"concept": cid, "as": kind, "text": text})
    return dict(sorted(idx.items()))


# ---------------------------------------------------------------- assemble
def load_json(path: Path, what: str):
    if not path.exists():
        sys.exit(f"missing {what}: {path} (run that stage first)")
    return json.loads(path.read_text())


def span(sentences: list[str], times: dict, fallback: tuple[float, float]) -> tuple[float, float]:
    ts = [times[s] for s in sentences if s in times]
    return (min(t["start"] for t in ts), max(t["end"] for t in ts)) if ts else fallback


def assemble(course: str, embed_model: str = EMBED_MODEL) -> Path:
    reg = s4a.load_registry(course)
    concepts, relations = reg["concepts"], reg["relations"]
    keys = sorted(set(lec.keys(s4a.stage_dir(course, "stage_2c_concepts") / "concept_maps"))
                  | set(s4a.registry_lectures(reg)), key=lec.order)
    texts, cmaps = s4a.load_facts(course, keys), s4a.load_concept_maps(course, keys)
    segmaps = {k: load_json(s2a.maps_dir(course) / f"{lec.stem_of(k)}.json", "segment map") for k in keys}
    times = {}
    for k in keys:
        times.update(load_json(s4a.stage_dir(course, "stage_0a_preprocess") / "times" / f"{lec.stem_of(k)}.json",
                               "sentence times"))
    defs = load_json(s4a.out_dir(course) / "definitions.json", "4a definitions")
    lgoals = {k: load_json(s4b.out_dir(course) / "lecture_goals" / f"{lec.stem_of(k)}.json", "4b lecture goals")
              for k in keys}
    cgoals = load_json(s4b.out_dir(course) / "course_goals.json", "4b course goals")
    graph = load_json(s4c.out_dir(course) / "graph.json", "4c lecture graph")
    seg_of = {sid: seg for k in keys for sid, seg in segmaps[k].items()}

    # facts: concepts that cite each, time from the evidence sentences
    fact_concepts: dict[str, list] = {}
    for cid, c in concepts.items():
        for f in c["facts"]:
            fact_concepts.setdefault(f, []).append(cid)
    facts = {}
    for fid in sorted(texts, key=s4a.fact_order):
        sid = s4a.segment_of(fid)
        seg = seg_of.get(sid, {})
        start, end = span(texts[fid]["evidence"], times, (seg.get("start", 0.0), seg.get("end", 0.0)))
        facts[fid] = {"text": texts[fid]["text"], "evidence": texts[fid]["evidence"], "segment": sid,
                      "lecture": s4a.lecture_of(fid), "start": start, "end": end,
                      "concepts": fact_concepts.get(fid, [])}

    # concept cards
    rel_out: dict[str, list] = {}
    rel_in: dict[str, list] = {}
    for rid, r in relations.items():
        rel_out.setdefault(r["subject"], []).append({"relation": rid, "label": r["label"], "concept": r["object"],
                                                     "name": concepts.get(r["object"], {}).get("name", "")})
        rel_in.setdefault(r["object"], []).append({"relation": rid, "label": r["label"], "concept": r["subject"],
                                                   "name": concepts.get(r["subject"], {}).get("name", "")})
    cards = {}
    for cid, c in concepts.items():
        defining = s4a.defining_facts(c, cmaps)
        dset = set(defining)
        where = []
        for sid in c.get("defined_in", []):
            sf = [f for f in defining if s4a.segment_of(f) == sid]
            seg = seg_of.get(sid, {})
            start, end = span([e for f in sf for e in texts[f]["evidence"]], times,
                              (seg.get("start", 0.0), seg.get("end", 0.0)))
            where.append({"lecture": s4a.lecture_of(sid), "segment": sid, "start": start, "end": end, "facts": sf})
        d = defs.get(cid, {})
        own = sorted(dict.fromkeys(f for f in c["facts"] if f in texts), key=s4a.fact_order)
        cards[cid] = {
            "name": c["name"], "aliases": c["aliases"],
            "acronyms": list(dict.fromkeys(t for kind, t in name_entries(c) if kind == "acronym")),
            "definition": d.get("definition", ""), "defined": bool(d.get("defined", False)), "defined_in": where,
            "first_defined": graph["concept_paths"].get(cid, {}).get("first_defined"),
            "facts": [f for f in own if f in dset] + [f for f in own if f not in dset],
            "defining_facts": defining, "definition_facts": d.get("facts", []), "misplaced": d.get("misplaced", []),
            "relations": {"out": rel_out.get(cid, []), "in": rel_in.get(cid, [])},
            "lectures": c["lectures"],
            "merged": [{k: m.get(k, "") for k in ("segment_concept", "name", "how", "reason")}
                       for m in c.get("merged", [])]}

    # goals
    tree = {"reasoning": cgoals.get("reasoning", ""), "course_goals": cgoals.get("goals", {}),
            "lecture_goals": {}, "objectives": {}, "segments": {}}
    serves = {k: [gid for gid, g in tree["course_goals"].items() if k in g["lectures"]] for k in keys}
    objective_of = {}
    for k in keys:
        g = lgoals[k].get(s4b.goal_id(k))
        if not g:
            continue
        tree["lecture_goals"][s4b.goal_id(k)] = {"lecture": k, "goal": g["goal"], "achieves": g["achieves"],
                                                 "objectives": g["objectives"], "course_goals": serves[k]}
        for oid in g["objectives"]:
            o = lgoals[k][oid]
            tree["objectives"][oid] = {"lecture": k, "lecture_goal": s4b.goal_id(k), "goal": o["goal"],
                                       "achieves": o["achieves"], "segments": o["segments"]}
            for sid in o["segments"]:
                objective_of.setdefault(sid, oid)
    seg_facts = {}
    for fid in facts:
        seg_facts.setdefault(facts[fid]["segment"], []).append(fid)
    seg_concepts: dict[str, list] = {}
    for cid, c in concepts.items():
        for sid in dict.fromkeys(c["segments"]):
            seg_concepts.setdefault(sid, []).append(cid)
    for k in keys:
        for sid, seg in segmaps[k].items():
            tree["segments"][sid] = {"lecture": k, "subgoal": seg["subgoal"], "objective": objective_of.get(sid),
                                     "facts": seg_facts.get(sid, []), "concepts": seg_concepts.get(sid, [])}

    # per lecture
    lectures = {}
    for k in keys:
        g = lgoals[k].get(s4b.goal_id(k))
        lectures[k] = {
            "lecture": k, "title": course_meta.lecture_title(course, k),
            "segments": {sid: {"first": seg["first"], "last": seg["last"], "start": seg["start"], "end": seg["end"],
                               "subgoal": seg["subgoal"], "objective": objective_of.get(sid),
                               "facts": seg_facts.get(sid, []), "concepts": seg_concepts.get(sid, [])}
                         for sid, seg in segmaps[k].items()},
            "concepts": graph["concept_kinds"][k],
            "concept_map": {"concepts": [cid for cid, c in concepts.items() if k in c["lectures"]],
                            "relations": [rid for rid, r in relations.items()
                                          if any(s4a.lecture_of(s) == k for s in r["segments"])]},
            "goal": {"id": s4b.goal_id(k), "goal": g["goal"], "achieves": g["achieves"]} if g else None,
            "objectives": [{"id": oid, **{f: lgoals[k][oid][f] for f in ("goal", "achieves", "segments")}}
                           for oid in (g["objectives"] if g else [])],
            "course_goals": serves[k],
            "prerequisites": graph["prerequisites"][k]}

    assumed = {"concepts": [{"concept": cid, "name": concepts[cid]["name"], "lectures": concepts[cid]["lectures"]}
                            for cid in concepts if not graph["concept_paths"][cid]["first_defined"]]}

    # embeddings
    from scripts.embed import Embedder                     # here, so --check works without the embedding model
    od = out_dir(course)
    od.mkdir(parents=True, exist_ok=True)
    emb = Embedder(embed_model, cache=od / "embed_cache.jsonl")
    fids = list(facts)
    vecs = emb.embed([facts[f]["text"] for f in fids]) if fids else []
    vectors = {f: [round(float(x), 6) for x in v] for f, v in zip(fids, vecs)}
    dim = len(vecs[0]) if vecs else 1

    kd = knowledge_dir(course)
    if kd.exists():
        shutil.rmtree(kd)
    (kd / "lectures").mkdir(parents=True)
    files = {"names": "names.json", "concepts": "concepts.json", "relations": "relations.json", "facts": "facts.json",
             "fact_embeddings": "fact_embeddings.json", "lectures": "lectures/lec_<n>.json", "goals": "goals.json",
             "lecture_graph": "lecture_graph.json", "assumed": "assumed.json"}
    index = {"course": course, "title": course_meta.load(course).get("title", ""), "lectures": keys, "files": files,
             "counts": {"lectures": len(keys), "concepts": len(cards), "relations": len(relations),
                        "facts": len(facts), "course_goals": len(tree["course_goals"]),
                        "objectives": len(tree["objectives"]), "assumed": len(assumed["concepts"])},
             "embedding": {"model": emb.model, "dim": dim, "file": "fact_embeddings.json"},
             "name_key": NAME_KEY, "lecture_graph_params": graph["params"]}
    write = lambda name, data: (kd / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")  # noqa
    write("index.json", index)
    write("names.json", name_index(concepts))
    write("concepts.json", cards)
    write("relations.json", {rid: {f: r.get(f, []) for f in ("subject", "label", "object", "facts", "segments", "from")}
                             for rid, r in relations.items()})
    write("facts.json", facts)
    (kd / "fact_embeddings.json").write_text(json.dumps({"model": emb.model, "dim": dim, "vectors": vectors}) + "\n")
    for k, data in lectures.items():
        write(f"lectures/{lec.stem_of(k)}.json", data)
    write("goals.json", tree)
    write("lecture_graph.json", graph)
    write("assumed.json", assumed)
    return kd


# ---------------------------------------------------------------- check
def check_layer(kd: Path, schema_path: Path = SCHEMA) -> dict:
    """The schema, the references and the coverage of a knowledge/ folder. Every list in the result is a problem."""
    schema = json.loads(schema_path.read_text())
    chk = Checker(schema)
    data, report = {}, {"schema": [], "broken_references": [], "duplicate_ids": [], "coverage": [], "unchecked_files": []}
    patterns = schema["x-files"]
    for p in sorted(kd.rglob("*.json")):
        rel = str(p.relative_to(kd))
        name = next((d for pat, d in patterns.items() if fnmatch.fnmatch(rel, pat)), None)
        if name is None:
            report["unchecked_files"].append(rel)
            continue
        try:
            data[rel] = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            report["schema"].append(f"{rel}: not JSON ({e})")
            continue
        chk.check(data[rel], f"#/$defs/{name}", where=rel)
    for pat in patterns:
        if not any(fnmatch.fnmatch(rel, pat) for rel in data):
            report["schema"].append(f"no file for {pat}")
    report["schema"] += chk.errors
    sentences = set()
    for rel, d in data.items():
        if rel.startswith("lectures/") and isinstance(d, dict):
            for seg in (d.get("segments") or {}).values():
                try:
                    key, a = seg["first"].rsplit("/", 1)
                    b = seg["last"].rsplit("/", 1)[1]
                    sentences |= {f"{key}/{i}" for i in range(int(a), int(b) + 1)}
                except (KeyError, TypeError, ValueError, AttributeError):
                    pass                                     # the schema check reports it
    report["broken_references"] = chk.broken({"sentence": sentences})
    report["duplicate_ids"] = chk.duplicates
    concepts, facts = data.get("concepts.json") or {}, data.get("facts.json") or {}
    emb = data.get("fact_embeddings.json") or {}
    vectors = emb.get("vectors") or {}
    cov = report["coverage"]
    if isinstance(facts, dict) and isinstance(vectors, dict):
        cov += [f"fact {f} has no vector" for f in facts if f not in vectors]
        dims = {len(v) for v in vectors.values() if isinstance(v, list)}
        if len(dims) > 1 or (dims and emb.get("dim") not in dims):
            cov.append(f"vectors of lengths {sorted(dims)}, dim says {emb.get('dim')}")
    index = data.get("names.json") or {}
    named = {e.get("concept") for es in index.values() if isinstance(es, list) for e in es if isinstance(e, dict)}
    cov += [f"concept {c} is not in the name index" for c in concepts if c not in named]
    graph = data.get("lecture_graph.json") or {}
    cov += [f"concept {c} has no path in the lecture graph" for c in concepts
            if c not in (graph.get("concept_paths") or {})]
    report["files"] = len(data)
    report["references"] = len(chk.refs)
    report["ok"] = not any(report[k] for k in ("schema", "broken_references", "duplicate_ids", "coverage",
                                               "unchecked_files"))
    return report


def summarize(report: dict) -> str:
    parts = [f"{k} {len(report[k])}" for k in ("schema", "broken_references", "duplicate_ids", "coverage",
                                               "unchecked_files") if report[k]]
    return (f"{report['files']} files, {report['references']} references: "
            + ("all good" if report["ok"] else "; ".join(parts)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--embed-model", default=EMBED_MODEL, help=f"embedding model (default {EMBED_MODEL}; 'fake' for tests)")
    ap.add_argument("--check", action="store_true", help="only check the existing knowledge/ folder")
    a = ap.parse_args()
    kd = knowledge_dir(a.course) if a.check else assemble(a.course, a.embed_model)
    report = check_layer(kd)
    od = out_dir(a.course)
    od.mkdir(parents=True, exist_ok=True)
    (od / "checks.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"4d: {kd}: {summarize(report)}")
    for k in ("schema", "broken_references", "duplicate_ids", "coverage", "unchecked_files"):
        for item in report[k][:10]:
            print(f"  {k}: {item}")
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
