"""Step 8: the lecture map, by code. Lecture i -> lecture j (i before j) when concepts introduced in i come back in j:

    carried = concepts introduced in i that j teaches something about (a facet that is not "only mentioned"),
              plus concepts introduced in i that a concept introduced in j depends on (links found up to j)
    weight  = the number of concepts carried

Each lecture keeps its TOP_IN strongest incoming links, with the concepts that carry them. It is always a DAG, because
links only point forward. Lecture j's incoming links use only what is known by lecture j, so recall for lecture j can
be built as soon as lecture j's facets and links are judged. It drives recall ("before lecture j, recall what i
taught about these concepts") and the order of spaced review.
"""
from __future__ import annotations

from . import addr as A
from .context import Lecture, Run
from .s6_edges import merged

TOP_IN = 3


def incoming(R: Run, lec: Lecture, log: bool = False) -> list[dict]:
    C = R.registry.concepts
    intro = {c.id: A.lecture_of(c.introduced) for c in C.values()}
    links: dict[str, set[str]] = {}
    with R.lock:
        here = [(c.id, f) for c in C.values() for f in c.facets if A.lecture_of(f["part"]) == lec.id]
    for cid, f in here:
        i = intro[cid]
        if not f["only_mentioned"] and R.pos(i) < lec.pos:
            links.setdefault(i, set()).add(cid)
    for e in merged(R, lec.pos):
        if e["rel"] == "depends_on" and intro[e["src"]] == lec.id:
            i = intro[e["dst"]]
            if R.pos(i) < lec.pos:
                links.setdefault(i, set()).add(e["dst"])
    ranked = sorted(links.items(), key=lambda t: (-len(t[1]), -R.pos(t[0])))
    if log and len(ranked) > TOP_IN:
        R.decisions.add("lecture_map", [lec.id], f"kept {TOP_IN} of {len(ranked)} incoming links",
                        "strongest by number of concepts carried",
                        dropped=[{"src": i, "weight": len(cs)} for i, cs in ranked[TOP_IN:]])
    return [{"src": i, "dst": lec.id, "weight": len(cs), "concepts": sorted(cs)} for i, cs in ranked[:TOP_IN]]


def run(R: Run):
    R.lecture_map = [x for lec in R.lectures for x in incoming(R, lec, log=True)]
    R.count("lecture_links", len(R.lecture_map))
