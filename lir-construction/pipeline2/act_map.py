"""Built by code from the knowledge layer (spaced review: act_spaced.py).

    concept map     per lecture: concepts introduced in it plus earlier concepts it teaches about (a real facet),
                    ranked by links among them (edges known by this lecture), then by how many of the lecture's
                    parts teach about them; at most MAX_NODES, at most MAX_EARLIER earlier ones, linked concepts first.
                    Seeds: the top SEEDS concepts introduced here plus up to SEED_ANCHORS earlier ones. Links carry
                    the edge's label (step 6d). The choice is logged.
"""
from __future__ import annotations

from .context import Lecture, Run

MAX_NODES, MAX_EARLIER, SEEDS, SEED_ANCHORS = 14, 4, 4, 2
INSTRUCTIONS = ("Build a concept map of this lecture. Start from the seed concepts: add the concepts you think belong "
                "to the lecture, draw links between related concepts, and label each link with a short phrase (for "
                "example \"is part of\" or \"is needed for\"). Then compare your map with the reference map.")


def concept_map(R: Run, lec: Lecture) -> dict:
    C = R.registry.concepts
    taught = lambda c: sum(1 for f in c.facets if not f["only_mentioned"] and f["part"].startswith(lec.id + "/"))
    here = [c for c in C.values() if c.intro_pos == lec.pos]
    earlier = [c for c in C.values() if c.intro_pos < lec.pos and taught(c)]
    ids = {c.id for c in here + earlier}
    edges = [e for e in R.edges if e["src"] in ids and e["dst"] in ids and R.pos(e["lecture_id"]) <= lec.pos]
    deg = {cid: 0 for cid in ids}
    for e in edges:
        deg[e["src"]] += 1
        deg[e["dst"]] += 1
    rank = lambda c: (deg[c.id] == 0, -deg[c.id], -taught(c), R.order(c.introduced))
    keep_earlier = sorted(earlier, key=rank)[:MAX_EARLIER]
    nodes = sorted(here + keep_earlier, key=rank)[:MAX_NODES]
    keep = {c.id for c in nodes}
    edges = [e for e in edges if e["src"] in keep and e["dst"] in keep]
    seeds = [c.id for c in nodes if c.intro_pos == lec.pos][:SEEDS] + \
            [c.id for c in nodes if c.intro_pos < lec.pos and deg[c.id]][:SEED_ANCHORS]
    R.decisions.add("concept_map", [lec.id], f"{len(nodes)} of {len(ids)} concepts, {len(edges)} links",
                    f"ranked by links in this lecture's map, then by parts that teach them; at most {MAX_NODES} "
                    f"concepts, {MAX_EARLIER} from earlier lectures", seeds=seeds)
    return {"instructions": INSTRUCTIONS,
            "nodes": [{"concept_id": c.id, "name": c.name, "introduced_in": c.introduced.split("/")[0],
                       "seed": c.id in seeds} for c in nodes],
            "edges": [{"edge_id": e["id"], "src": e["src"], "rel": e["rel"], "dst": e["dst"], "label": e["label"]}
                      for e in edges]}
