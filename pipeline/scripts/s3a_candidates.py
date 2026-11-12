"""Stage 3a: the concept registry, steps 1 and 2: exact merges by name, then candidate pairs and clusters.

    python scripts/s3a_candidates.py nptel_vr [--only 1,4,16] [--embed-model Qwen/Qwen3-Embedding-0.6B]
                                              [--embed-facts defining|any-if-none|any] [--threshold 0.75]
                                              [--cap 12] [--device cuda] [--out DIR]

Reads   output/<course>/stage_2c_concepts/concept_maps/lec_<n>.json   {"4/S1/C0": {"name", "aliases", "facts", "defined"}}
        output/<course>/stage_2b_verify_facts/fact_maps/lec_<n>.json  the fact texts (for the embedding text)
Writes  output/<course>/stage_3_registry/ (or --out)
          clusters.json        settings, entries (step 1), candidate pairs, clusters and the pairs the cap cut (step 2);
                               s3b adds the model's grouping to each cluster
          text/clusters.txt    the clusters, readable
          embed/cache.jsonl    the embedding cache (scripts/embed.py): a rerun never embeds a text again

Step 1, exact merge. Segment concepts whose names are the same term become one entry (E0001, ... in course order):
  the same term = the same words ignoring case, hyphens, slashes, apostrophes and other punctuation, where each word
  may differ by a plural ending (s, es, y/ies: "lens" and "lenses", "degree of freedom" and "degrees of freedom"),
  or the same letters once the spaces are removed, up to a plural ending ("head set" and "headsets").
  A name that is an acronym (is_acronym of scripts/fact_checks.py, the one shared test: one token with at least two
  capitals, or a digit and a capital, and no run of two lower-case letters: "HMD", "VR", "FoV", "3D", "6DoF"; not
  "HoloLens", "OpenGL") is never merged here, even with the same acronym: a shared acronym alone goes to step 3. Its
  entry reaches the model through the shared-alias rule below.
  An entry's name is the wording most of its segment concepts use (ties: the first in course order); its names are
  that name, then the other names and aliases of its segment concepts in course order (case ignored for repeats).
Step 2, candidates and clusters.
  Each entry is embedded (scripts/embed.py) as "<name>; also called: <other names>. <facts>", with up to
  EMBED_FACTS facts, chosen by --embed-facts (decision D9):
    defining      the facts of its segment concepts that have defined=true, in course order (an entry with none:
                  names only)
    any-if-none   (default) as defining; an entry with no defining fact gets its other facts instead, in course
                  order, up to the same number
    any           every entry filled up to the number: its defining facts first, then its other facts
  Both sides of a pair get the same instruction (applied only for models that take one, e.g. Qwen3-Embedding):
  INSTRUCTION ("... with its names and defining facts ...") for defining, INSTRUCTION_FACTS ("... with its names and
  facts ...") for the two options that use other facts. A pair of entries is a candidate when its cosine similarity
  is at least --threshold, or when the two share a term among their names (the same-term rule above, acronyms
  included).
  Clusters are the connected candidates, at most --cap entries each. They are built by adding the candidate pairs
  strongest first (a shared-alias pair counts 1 more than its similarity, so those come first; ties in entry order),
  joining two parts only while the joined part stays within the cap. Below the cap this is exactly the connected
  components; a larger component is split where its weakest links are. The candidate pairs whose two entries end in
  different clusters are listed under "cut" (they can never merge). Entries with no candidate are not in a cluster:
  each becomes a concept of its own.

clusters.json:
  {"settings": {"lectures", "embed_model", "instruction" (the prefix the model got; "" for a model without the
                convention), "threshold", "cap", "embed_facts" (the option), "embed_fact_count" (EMBED_FACTS),
                "inputs": hash of the concept maps (s3b and s3c refuse stale clusters)},
   "entries":  {"E0001": {"name", "names", "members": [segment concepts], "lectures", "segments", "facts",
                          "defining_facts": the facts of its members with defined=true, "defined_in",
                          "text": the embedding text}},
   "candidates": [{"a": "E0001", "b": "E0007", "sim": 0.81, "alias": [shared terms]}],
   "clusters": {"K0001": {"entries": [...], "pairs": n candidate pairs inside}},
   "cut": [candidate pairs split by the cap]}
s3b adds each cluster's groups, and "same_checks" (scripts/s3b_same.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import lectures as lec, s2b_verify_facts as s2b, s2c_concepts as s2c  # noqa: E402
from scripts.fact_checks import is_acronym  # noqa: E402  (the one shared acronym test; s3b takes it from here)

EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
THRESHOLD = 0.70     # provisional: analysis/registry/embed_compare.py chooses it on the pair gold
CAP = 12             # entries per cluster (one model call)
EMBED_FACTS = 5      # facts in an entry's embedding text
EMBED_OPTIONS = ("defining", "any-if-none", "any")
EMBED_OPTION = "any-if-none"   # decision D9 (2026-11-13); "defining" kept for the comparison
INSTRUCTION = "Given a concept from a lecture course, with its names and defining facts, find the same concept"
INSTRUCTION_FACTS = "Given a concept from a lecture course, with its names and facts, find the same concept"


def instruction(option: str) -> str:
    """The embedding instruction for an --embed-facts option: "names and facts" when other facts are used."""
    return INSTRUCTION if option == "defining" else INSTRUCTION_FACTS


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_3_registry"


# ---------------------------------------------------------------- IDs and order
def sc_order(scid: str) -> tuple:
    """Course order of a segment concept, relationship or fact ID: "4/S1/C0" -> (lecture order, 1, 0)."""
    key, seg, item = scid.split("/")
    return lec.order(key), int(seg[1:]), int(item[1:])


def seg_order(sid: str) -> tuple:
    key, seg = sid.split("/")
    return lec.order(key), int(seg[1:])


def lecture_of(scid: str) -> str:
    return scid.split("/", 1)[0]


def segment_of(scid: str) -> str:
    return scid.rsplit("/", 1)[0]


# ---------------------------------------------------------------- inputs
def concept_files(course: str, keys: list[str] | None = None) -> list[Path]:
    folder = s2c.out_dir(course) / "concept_maps"
    if keys:
        return [folder / f"{lec.stem_of(k)}.json" for k in keys]
    return lec.files(folder)


def load_concepts(course: str, keys: list[str] | None = None) -> dict:
    """Every segment concept of the lectures, in course order."""
    out = {}
    for p in concept_files(course, keys):
        out.update(json.loads(p.read_text()))
    return dict(sorted(out.items(), key=lambda kv: sc_order(kv[0])))


def load_facts(course: str, keys: list[str]) -> dict:
    """Fact ID -> text, from the verified facts (2b)."""
    out = {}
    for k in keys:
        p = s2b.out_dir(course) / "fact_maps" / f"{lec.stem_of(k)}.json"
        if p.exists():
            out.update({fid: f["text"] for fid, f in json.loads(p.read_text()).items()})
    return out


def inputs_hash(course: str, keys: list[str]) -> str:
    h = hashlib.sha256()
    for p in concept_files(course, keys):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- the same term
def words(term: str) -> list[str]:
    """Lower-case words: hyphens, slashes, underscores split; apostrophes vanish ("Fitts's" -> "fittss"); other
    punctuation is a space (but + and # stay: "C++")."""
    t = re.sub(r"['’]", "", term.lower())
    return re.sub(r"[^a-z0-9+#]+", " ", t).split()


def plural_pair(a: str, b: str) -> bool:
    """a and b are the same word up to a plural ending (s, es, y -> ies)."""
    if a == b:
        return True
    if len(a) > len(b):
        a, b = b, a
    return len(a) >= 2 and (b == a + "s" or b == a + "es" or (a.endswith("y") and b == a[:-1] + "ies"))


def same_term(a: str, b: str) -> bool:
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return False
    if len(wa) == len(wb) and all(plural_pair(x, y) for x, y in zip(wa, wb)):
        return True
    return plural_pair("".join(wa), "".join(wb))


def term_classes(terms: list[str]) -> dict[str, int]:
    """Union-find over the terms by same_term: term -> class number (the index of its class's first term). Only terms
    whose joined words start with the same two letters are compared (a plural ending never changes those)."""
    uniq = list(dict.fromkeys(terms))
    parent = list(range(len(uniq)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    buckets: dict[str, list[int]] = {}
    for i, t in enumerate(uniq):
        joined = "".join(words(t))
        if joined:
            buckets.setdefault(joined[:2], []).append(i)
    for idx in buckets.values():
        for x in range(len(idx)):
            for y in range(x + 1, len(idx)):
                i, j = idx[x], idx[y]
                if find(i) != find(j) and same_term(uniq[i], uniq[j]):
                    a, b = sorted((find(i), find(j)))
                    parent[b] = a
    return {t: find(i) for i, t in enumerate(uniq)}


# ---------------------------------------------------------------- step 1: exact merge
def _dedupe(names: list[str]) -> list[str]:
    seen, out = set(), []
    for n in names:
        n = n.strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def exact_entries(concepts: dict) -> dict:
    """Step 1: entries E0001... in course order; each joins the segment concepts whose (non-acronym) names are the
    same term."""
    names = [c["name"] for c in concepts.values() if not is_acronym(c["name"].strip())]
    cls = term_classes(names)
    groups: dict = {}
    for scid, c in concepts.items():                 # concepts are in course order, so groups are too
        k = ("term", cls[c["name"]]) if not is_acronym(c["name"].strip()) else ("acronym", scid)
        groups.setdefault(k, []).append(scid)
    entries = {}
    for i, members in enumerate(groups.values(), 1):
        cs = [concepts[m] for m in members]
        counts: dict[str, int] = {}
        for c in cs:
            counts[c["name"].strip()] = counts.get(c["name"].strip(), 0) + 1
        name = max(counts, key=lambda n: counts[n])          # first of the most used (dicts keep order)
        facts = sorted({f for c in cs for f in c["facts"]}, key=sc_order)
        entries[f"E{i:04d}"] = {
            "name": name,
            "names": _dedupe([name] + [x for c in cs for x in [c["name"]] + c["aliases"]]),
            "members": members,
            "lectures": sorted({lecture_of(m) for m in members}, key=lec.order),
            "segments": sorted({segment_of(m) for m in members}, key=seg_order),
            "facts": facts,
            "defining_facts": sorted({f for c in cs if c["defined"] for f in c["facts"]}, key=sc_order),
            "defined_in": sorted({segment_of(m) for m, c in zip(members, cs) if c["defined"]}, key=seg_order),
        }
    return entries


# ---------------------------------------------------------------- step 2: candidates and clusters
def embed_facts(entry: dict, facts: dict, option: str = EMBED_OPTION, n_facts: int = EMBED_FACTS) -> list[str]:
    """The fact IDs of an entry's embedding text under an --embed-facts option (module docstring), in order."""
    if option not in EMBED_OPTIONS:
        raise ValueError(f"unknown --embed-facts option {option!r} (one of {', '.join(EMBED_OPTIONS)})")
    defining = [f for f in entry["defining_facts"] if f in facts]
    others = [f for f in entry["facts"] if f in facts and f not in set(defining)]
    if option == "defining" or (option == "any-if-none" and defining):
        return defining[:n_facts]
    if option == "any-if-none":
        return others[:n_facts]
    return (defining + others)[:n_facts]


def entry_text(entry: dict, facts: dict, n_facts: int = EMBED_FACTS, option: str = EMBED_OPTION) -> str:
    text = entry["name"]
    if len(entry["names"]) > 1:
        text += "; also called: " + ", ".join(entry["names"][1:])
    shown = [facts[f] for f in embed_facts(entry, facts, option, n_facts)]
    return text + (". " + " ".join(shown) if shown else "")


def shared_terms(entries: dict) -> dict[tuple[str, str], list[str]]:
    """Pairs of entries that share a term among their names (same_term, acronyms included): (a, b) -> the terms."""
    ids = list(entries)
    cls = term_classes([n for e in entries.values() for n in e["names"]])
    by_class: dict[int, list[tuple[str, str]]] = {}
    for eid in ids:
        for n in entries[eid]["names"]:
            by_class.setdefault(cls[n], []).append((eid, n))
    out: dict[tuple[str, str], list[str]] = {}
    for members in by_class.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                (a, na), (b, nb) = members[x], members[y]
                if a == b:
                    continue
                key = tuple(sorted((a, b)))
                term = na if a == key[0] else nb
                out.setdefault(key, [])
                if term not in out[key]:
                    out[key].append(term)
    return out


def similarities(vectors: list[list[float]], threshold: float) -> dict[tuple[int, int], float]:
    """(i, j) -> cosine for the pairs at or above the threshold (numpy when it is there, else plain Python)."""
    try:
        import numpy as np
    except ImportError:
        np = None
    out = {}
    if np is not None and vectors:
        m = np.asarray(vectors, dtype=np.float64)
        s = m @ m.T
        for i, j in zip(*np.nonzero(np.triu(s >= threshold, k=1))):
            out[(int(i), int(j))] = float(s[i, j])
        return out
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            v = sum(a * b for a, b in zip(vectors[i], vectors[j]))
            if v >= threshold:
                out[(i, j)] = v
    return out


def make_clusters(n: int, edges: list[tuple[float, int, int]], cap: int) -> tuple[list[list[int]], list[int]]:
    """Clusters of nodes 0..n-1 from weighted edges (weight, i, j): strongest first, two parts joined only while the
    joined part has at most `cap` nodes. Returns the clusters (2 nodes or more, each sorted, in order of their first
    node) and the indices of the edges whose ends end in different clusters."""
    parent, size = list(range(n)), [1] * n

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for w, i, j in sorted(edges, key=lambda e: (-e[0], e[1], e[2])):
        a, b = find(i), find(j)
        if a != b and size[a] + size[b] <= cap:
            a, b = min(a, b), max(a, b)
            parent[b], size[a] = a, size[a] + size[b]
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    clusters = sorted((g for g in groups.values() if len(g) > 1), key=lambda g: g[0])
    cut = [k for k, (_, i, j) in enumerate(edges) if find(i) != find(j)]
    return clusters, cut


# ---------------------------------------------------------------- text view
def write_text(od: Path, data: dict):
    """text/clusters.txt: each cluster with its entries, and the model's groups when s3b has run."""
    E, lines = data["entries"], []
    s = data["settings"]
    lines.append(f"{len(E)} entries, {len(data['candidates'])} candidate pairs, {len(data['clusters'])} clusters, "
                 f"{len(data['cut'])} pairs cut by the cap ({s['embed_model']}, embed facts {s['embed_facts']}, "
                 f"threshold {s['threshold']}, cap {s['cap']})\n")
    sims = {(p["a"], p["b"]): p for p in data["candidates"]}
    for kid, k in data["clusters"].items():
        lines.append(f"{kid}  {len(k['entries'])} entries, {k['pairs']} candidate pairs")
        for i, eid in enumerate(k["entries"], 1):
            e = E[eid]
            lines.append(f"  [{i}] {eid} {e['name']}" + (f" ({', '.join(e['names'][1:])})" if len(e["names"]) > 1 else "")
                         + f"  lectures {', '.join(e['lectures'])}; {len(e['members'])} segment concepts")
        pairs = [(a, b) for (a, b) in sims if a in k["entries"] and b in k["entries"]]
        lines.append("  pairs: " + "; ".join(f"{a}-{b} {sims[(a, b)]['sim']:.3f}"
                                             + (" alias" if sims[(a, b)]["alias"] else "") for a, b in pairs))
        if "groups" in k:
            if k.get("ok"):
                lines.append("  model:")
            elif k.get("unresolved"):
                lines.append(f"  model: UNRESOLVED ({'; '.join(k['unresolved'])}): its best answer kept, repaired")
            else:
                lines.append(f"  model: NO ANSWER ({'; '.join(k.get('errors', []))}), kept apart")
            for g in k["groups"]:
                lines.append(f"    {' + '.join(g['entries'])} -> {g['name']}: {g['reason']}")
            if k.get("retry"):
                r = k["retry"]
                lines.append(f"  retried ({k['attempts']} attempts): lost {'; '.join(r['lost']) or 'nothing'}; "
                             f"added {'; '.join(r['added']) or 'nothing'}")
        lines.append("")
    if data["cut"]:
        lines.append("Cut by the cap:")
        lines += [f"  {p['a']} {E[p['a']]['name']} - {p['b']} {E[p['b']]['name']}  {p['sim']:.3f}"
                  + (" alias" if p["alias"] else "") for p in data["cut"]]
    (od / "text").mkdir(parents=True, exist_ok=True)
    (od / "text" / "clusters.txt").write_text("\n".join(lines) + "\n")


def save(od: Path, data: dict):
    (od / "clusters.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    write_text(od, data)


def load(od: Path, course: str) -> dict:
    """clusters.json, refused when the concept maps changed since it was written."""
    data = json.loads((od / "clusters.json").read_text())
    if inputs_hash(course, data["settings"]["lectures"]) != data["settings"]["inputs"]:
        sys.exit(f"{od / 'clusters.json'} is stale: the concept maps changed since s3a ran; run s3a again")
    return data


# ---------------------------------------------------------------- run
def run(course: str, lectures: list | None = None, embed_model: str = EMBED_MODEL, threshold: float = THRESHOLD,
        cap: int = CAP, device: str | None = None, out: Path | None = None, embed_option: str = EMBED_OPTION) -> dict:
    """Steps 1 and 2 over the lectures (all with concept maps by default)."""
    from scripts.embed import Embedder
    t0 = time.time()
    keys = lec.normalize(lectures) or lec.keys(s2c.out_dir(course) / "concept_maps")
    od = Path(out) if out else out_dir(course)
    od.mkdir(parents=True, exist_ok=True)
    concepts, facts = load_concepts(course, keys), load_facts(course, keys)
    entries = exact_entries(concepts)
    ids = list(entries)
    for e in entries.values():
        e["text"] = entry_text(e, facts, option=embed_option)
    emb = Embedder(embed_model, cache=od / "embed" / "cache.jsonl", device=device)
    vecs = emb.embed([entries[i]["text"] for i in ids], instruction=instruction(embed_option))
    sims = similarities(vecs, threshold)
    alias = shared_terms(entries)
    pos = {eid: i for i, eid in enumerate(ids)}
    pairs = sorted(set(sims) | {(pos[a], pos[b]) for a, b in alias})
    cands = []
    for i, j in pairs:
        sim = sims.get((i, j))
        if sim is None:
            sim = sum(x * y for x, y in zip(vecs[i], vecs[j]))
        cands.append({"a": ids[i], "b": ids[j], "sim": round(sim, 4), "alias": alias.get((ids[i], ids[j]), [])})
    edges = [(c["sim"] + (1 if c["alias"] else 0), pos[c["a"]], pos[c["b"]]) for c in cands]
    clusters, cut = make_clusters(len(ids), edges, cap)
    kmap = {}
    for k, members in enumerate(clusters, 1):
        es = [ids[i] for i in members]
        inside = sum(1 for c in cands if c["a"] in es and c["b"] in es)
        kmap[f"K{k:04d}"] = {"entries": es, "pairs": inside}
    data = {"settings": {"lectures": keys, "embed_model": embed_model,
                         "instruction": emb.prefix(instruction(embed_option)), "threshold": threshold, "cap": cap,
                         "embed_facts": embed_option, "embed_fact_count": EMBED_FACTS,
                         "inputs": inputs_hash(course, keys)},
            "entries": entries, "candidates": cands, "clusters": kmap, "cut": [cands[k] for k in cut]}
    save(od, data)
    n_exact = sum(len(e["members"]) - 1 for e in entries.values())
    totals = {"segment_concepts": len(concepts), "entries": len(entries), "exact_merged": n_exact,
              "candidates": len(cands), "alias_pairs": len(alias), "clusters": len(kmap),
              "in_clusters": sum(len(k["entries"]) for k in kmap.values()), "cut": len(cut),
              "embedded": emb.computed, "wall_s": round(time.time() - t0, 1)}
    print(f"3a: {totals['segment_concepts']} segment concepts -> {totals['entries']} entries "
          f"({n_exact} exact merges); {totals['candidates']} candidate pairs ({totals['alias_pairs']} share a name); "
          f"{totals['clusters']} clusters holding {totals['in_clusters']} entries; {totals['cut']} pairs cut by the "
          f"cap; {emb.computed} texts embedded ({embed_model}, embed facts {embed_option}), {totals['wall_s']} s")
    return totals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--only", help="lectures, e.g. 1,4,16 (default: all with concept maps)")
    ap.add_argument("--embed-model", default=EMBED_MODEL, help=f"embedding model (default {EMBED_MODEL}; 'fake' "
                                                               f"for tests)")
    ap.add_argument("--embed-facts", default=EMBED_OPTION, choices=EMBED_OPTIONS,
                    help=f"the facts in an entry's embedding text (default {EMBED_OPTION}; see above)")
    ap.add_argument("--threshold", type=float, default=THRESHOLD, help=f"similarity for a candidate (default {THRESHOLD})")
    ap.add_argument("--cap", type=int, default=CAP, help=f"entries per cluster (default {CAP})")
    ap.add_argument("--device", help="embedding device, e.g. cuda or cpu (default: CUDA when there is one)")
    ap.add_argument("--out", help="output folder (default: output/<course>/stage_3_registry)")
    a = ap.parse_args()
    run(a.course, lec.parse_only(a.only) if a.only else None, a.embed_model, a.threshold, a.cap, a.device,
        Path(a.out) if a.out else None, a.embed_facts)


if __name__ == "__main__":
    main()
