"""Step 8: the lecture map, by code. Lecture i -> lecture j (i before j) when concepts introduced in i come back in j:

    carried = concepts introduced in i that j teaches something about (a facet that is not "only mentioned"),
              plus concepts introduced in i that a concept introduced in j depends on
    weight  = the number of concepts carried

Each lecture keeps its TOP_IN strongest incoming links, with the concepts that carry them. It is always a DAG, because
links only point forward. It drives recall ("before lecture j, recall what i taught about these concepts") and
spacing (a concept that comes back is the moment to review it).
"""
from __future__ import annotations

from .context import Run

TOP_IN = 3


def run(R: Run):
    C = R.registry.concepts
    intro_lid = {c.id: c.introduced.split("/")[0] for c in C.values()}
    links: dict[tuple[str, str], set[str]] = {}
    for c in C.values():
        i = intro_lid[c.id]
        for f in c.facets:
            j = f["part"].split("/")[0]
            if not f["only_mentioned"] and R.pos(j) > R.pos(i):
                links.setdefault((i, j), set()).add(c.id)
    for e in R.edges:
        if e["rel"] == "depends_on":
            i, j = intro_lid[e["dst"]], intro_lid[e["src"]]
            if R.pos(j) > R.pos(i):
                links.setdefault((i, j), set()).add(e["dst"])
    out = []
    for lec in R.lectures:
        incoming = sorted(((i, cs) for (i, j), cs in links.items() if j == lec.id),
                          key=lambda t: (-len(t[1]), -R.pos(t[0])))
        for i, cs in incoming[:TOP_IN]:
            out.append({"src": i, "dst": lec.id, "weight": len(cs), "concepts": sorted(cs)})
        if len(incoming) > TOP_IN:
            R.decisions.add("lecture_map", [lec.id], f"kept {TOP_IN} of {len(incoming)} incoming links",
                            "strongest by number of concepts carried",
                            dropped=[{"src": i, "weight": len(cs)} for i, cs in incoming[TOP_IN:]])
    R.lecture_map = sorted(out, key=lambda x: (R.pos(x["dst"]), -x["weight"]))
    R.count("lecture_links", len(out))
