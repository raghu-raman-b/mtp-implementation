"""Step 6: edges between concepts. Three relations, each read as "src REL dst":

    kind_of      src is a specific kind of the more general dst
    part_of      src is a component or part of dst
    depends_on   to understand src, a learner must first understand dst

    6a pairs     code, three sources:
                   - similar but not the same (answered "different" in step 4)
                   - a concept that a part teaches about (a facet) where another concept is introduced
                   - a concept named in another's definition or in the sentences that explain it
    6b relation  one call per pair: which relation (or none), with the sentences that show it
    6c checks    code: the evidence names both concepts; no cycles in a relation; depends_on points from a later
                 concept to an earlier one (otherwise flagged "forward")
    6d label     a link phrase for concept maps, written from the evidence and checked (one rewrite; otherwise
                 the relation's plain wording)
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from pipeline.llm import Call
from pipeline.validate import norm_words

from . import match as M
from . import prompts as P
from .context import Run
from .s4_registry import Concept, labelled

REL_ENUM = ["a_kind_of_b", "b_kind_of_a", "a_part_of_b", "b_part_of_a", "a_depends_on_b", "b_depends_on_a", "none"]
MAX_POOL = 14


class Label(BaseModel):
    label: str


class Check(BaseModel):
    reason: str
    ok: bool


def names_in(c: Concept, text: str) -> bool:
    return any(M.phrase_in(n, text) for n in [c.name] + [a["text"] for a in c.aliases if a["kind"] == "name"]) or \
        any(M.abbrev_in(a, text) for a in c.abbrevs())


def _ngrams(text: str) -> set[str]:
    w = norm_words(text)
    return {" ".join(w[i:i + n]) for n in range(1, M.MAX_NGRAM + 1) for i in range(len(w) - n + 1)}


# ------------------------------------------------------------------ 6a
def candidates(R: Run) -> dict[frozenset, dict]:
    reg = R.registry
    C = reg.concepts
    pairs: dict[frozenset, dict] = {}
    term_of = {t["id"]: (lec, t) for lec in R.lectures for p in lec.parts for t in p.terms}

    def add(a: str, b: str, lid: str, pool: list[str], why: str):
        if a == b:
            return
        k = frozenset((a, b))
        cur = pairs.get(k)
        if cur is None or R.pos(lid) < R.pos(cur["lid"]):
            pairs[k] = {"lid": lid, "pool": list(dict.fromkeys(pool)), "why": {why}}
        elif lid == cur["lid"]:
            cur["pool"] = list(dict.fromkeys(cur["pool"] + pool))
            cur["why"].add(why)
        else:
            cur["why"].add(why)

    def sources_as_of(c: Concept, lid: str) -> list[str]:
        d = c.definition_as_of(R, lid)
        return (d["sources"] if d else [c.introduced])[:6]

    # similar but different
    for a, b, lid in R.similar_pairs:
        add(a, b, lid, sources_as_of(C[a], lid) + sources_as_of(C[b], lid), "similar")
    # a facet in the part where the other concept is introduced
    in_part: dict[str, dict[str, list[str]]] = {}   # part -> concept -> sentences that teach or define it there
    for c in C.values():
        for f in c.facets:
            if not f["only_mentioned"]:
                in_part.setdefault(f["part"], {}).setdefault(c.id, []).extend(f["sentences"])
        for tid in c.terms:
            lec, t = term_of[tid]
            in_part.setdefault(lec.part_of(t["sentences"][0]).id, {}).setdefault(c.id, []).extend(
                lec.s(i) for i in t["sentences"])
    for b in C.values():
        here = in_part.get(b.introduced_part, {})
        for a, sents in here.items():
            if a != b.id:
                add(a, b.id, b.introduced_part.split("/")[0], here.get(b.id, [])[:7] + sents[:7], "facet")
    # named in the other's definition or defining sentences
    keys = {c.id: ([M.key(c.name)] + [M.key(x["text"]) for x in c.aliases if x["kind"] == "name"], c.abbrevs())
            for c in C.values()}
    for b in C.values():
        for d in b.definitions:
            text = d["text"] + " " + " ".join(R.lec(s.split("/")[0]).sentences[int(s.rsplit("/S", 1)[1])].text
                                             for s in d["sources"])
            grams, words = _ngrams(text), set(re.findall(r"[A-Za-z0-9]+", text))
            for a in C.values():
                if a.id == b.id or a.intro_pos > R.pos(d["as_of"]):
                    continue
                ks, abbrs = keys[a.id]
                if any(k and k in grams for k in ks) or any(x in words for x in abbrs):
                    add(a.id, b.id, d["as_of"], d["sources"][:10], "named in definition")
    for v in pairs.values():
        v["pool"] = sorted(v["pool"], key=R.order)[:MAX_POOL]
    return pairs


# ------------------------------------------------------------------ 6b
def _relation_call(R: Run, A: Concept, B: Concept, info: dict) -> Call:
    lid, pool = info["lid"], info["pool"]
    da, db = A.definition_as_of(R, lid), B.definition_as_of(R, lid)
    schema = {"type": "object", "additionalProperties": False, "required": ["reason", "relation", "evidence"],
              "properties": {"reason": {"type": "string"}, "relation": {"type": "string", "enum": REL_ENUM},
                             "evidence": {"type": "array", "maxItems": 8, "items": {"type": "string", "enum": pool}}}}

    def check(x):
        if x["relation"] == "none":
            return []
        if not x["evidence"]:
            return ["give the labels of the sentences that support the relation, or answer none"]
        text = labelled(R, x["evidence"])
        miss = [c.name for c in (A, B) if not names_in(c, text)]
        if miss:
            return [f"the evidence sentences must name both concepts; {' and '.join(miss)} is not named in them. "
                    f"Cite sentences that name both, or answer none"]
        return []
    return Call(key=f"{A.id}|{B.id}", lecture_id=lid, schema=schema, check=check,
                prompt=P.RELATION[2].format(role=P.ROLE, course=R.course.title, a=A.name,
                                            a_def=da["text"] if da else "", b=B.name, b_def=db["text"] if db else "",
                                            sents=labelled(R, pool), example=pool[0]),
                prompt_id=P.RELATION[0], prompt_version=P.RELATION[1], ctx={"A": A, "B": B, "info": info})


def _cycles(R: Run, edges: list[dict]) -> list[dict]:
    """Drop edges until no relation has a cycle: in each cycle, the edge with the latest evidence goes."""
    for rel in ("kind_of", "part_of", "depends_on"):
        while True:
            es = [e for e in edges if e["rel"] == rel]
            adj: dict[str, list[dict]] = {}
            for e in es:
                adj.setdefault(e["src"], []).append(e)
            cycle = _find_cycle(adj)
            if not cycle:
                break
            worst = max(cycle, key=lambda e: max(R.order(s) for s in e["evidence"]))
            edges.remove(worst)
            R.decisions.add("relation", worst["evidence"], "dropped (cycle)",
                            f"{rel} cycle through {[e['src'] for e in cycle]}; this edge has the latest evidence",
                            src=worst["src"], rel=rel, dst=worst["dst"])
    return edges


def _find_cycle(adj: dict[str, list[dict]]) -> list[dict] | None:
    state: dict[str, int] = {}
    stack: list[dict] = []

    def dfs(u):
        state[u] = 1
        for e in adj.get(u, []):
            v = e["dst"]
            stack.append(e)
            if state.get(v) == 1:
                i = next(k for k, x in enumerate(stack) if x["src"] == v)
                return stack[i:]
            if state.get(v) is None:
                r = dfs(v)
                if r:
                    return r
            stack.pop()
        state[u] = 2
        return None

    for u in list(adj):
        if state.get(u) is None:
            r = dfs(u)
            if r:
                return r
    return None


# ------------------------------------------------------------------ 6d
def _label_job(R: Run, e: dict, llm):
    C = R.registry.concepts
    src, dst = C[e["src"]].name, C[e["dst"]].name
    rel_text = P.REL_TEXT[e["rel"]]
    sents = labelled(R, e["evidence"])

    def job(send):
        label, reason = None, ""
        for attempt in range(2):
            extra = P.REWRITE.format(previous=label, reason=reason) if attempt else ""
            o = send(Call(key=f"{e['src']}-{e['rel']}-{e['dst']}/label/{attempt}", lecture_id=e["lecture_id"],
                          schema=Label, prompt_id=P.LABEL[0], prompt_version=P.LABEL[1],
                          prompt=P.LABEL[2].format(role=P.ROLE, sents=sents, src=src, dst=dst, rel_text=rel_text) + extra,
                          check=lambda x: [] if 0 < len(x.label.split()) <= 8 else ["write a label of 2 to 6 words"]))
            R.record(o, "label", llm, o.call.key)
            if o.parsed is None or not o.ok:
                reason = f"no usable label: {o.errors}"
                break
            label = o.parsed.label.strip().strip('"').rstrip(".")
            g = send(Call(key=f"{e['src']}-{e['rel']}-{e['dst']}/label_check/{attempt}", lecture_id=e["lecture_id"],
                          schema=Check, prompt_id=P.LABEL_CHECK[0], prompt_version=P.LABEL_CHECK[1],
                          prompt=P.LABEL_CHECK[2].format(role=P.ROLE, sents=sents, src=src, dst=dst, label=label,
                                                         rel_text=rel_text)))
            R.record(g, "label", llm, g.call.key)
            if g.parsed is not None and g.parsed.ok:
                return label, None
            reason = g.parsed.reason if g.parsed else f"no usable check: {g.errors}"
        return rel_text, reason
    return job


def run(R: Run):
    C = R.registry.concepts
    pairs = candidates(R)
    R.count("edge_candidates", len(pairs))
    llm = R.llm("relation")
    calls = []
    for k, info in pairs.items():
        a, b = sorted(k, key=lambda cid: (R.order(C[cid].introduced), cid))   # A = introduced first
        calls.append(_relation_call(R, C[a], C[b], info))
    edges = []
    for o in llm.run("v2_edges", calls, f"relations ({len(calls)} pairs)"):
        A, B, info = o.call.ctx["A"], o.call.ctx["B"], o.call.ctx["info"]
        R.record(o, "relation", llm, o.call.key)
        x = o.parsed
        if x is None or not o.ok or x["relation"] == "none":
            why = (x or {}).get("reason", "") if o.ok else f"failed the checks: {o.errors}"
            R.decisions.add("relation", [A.id, B.id], "none" if o.ok else "dropped", why, o, llm.model,
                            sources=sorted(info["why"]))
            continue
        rel = x["relation"]
        a_first = rel.startswith("a_")
        kind = rel[2:-2]                              # "kind_of", "part_of", "depends_on"
        src, dst = (A, B) if a_first else (B, A)
        flags = []
        if kind == "depends_on" and R.order(src.introduced) < R.order(dst.introduced):
            flags.append("forward")                   # src was introduced before the concept it depends on
        edges.append({"src": src.id, "rel": kind, "dst": dst.id, "label": None,
                      "evidence": sorted(set(x["evidence"]), key=R.order), "lecture_id": info["lid"], "flags": flags})
        R.decisions.add("relation", [src.id, dst.id], f"{src.id} {kind} {dst.id}", x["reason"], o, llm.model,
                        evidence=x["evidence"], sources=sorted(info["why"]), flags=flags)
    edges = _cycles(R, edges)
    edges.sort(key=lambda e: (R.pos(e["lecture_id"]), R.order(e["evidence"][0]), e["src"], e["dst"]))
    for n, e in enumerate(edges, 1):
        e["id"] = f"E{n:04d}"
    lab = R.llm("label")
    for e, (label, failed) in zip(edges, lab.run_jobs("v2_edge_labels", [_label_job(R, e, lab) for e in edges],
                                                      f"link labels ({len(edges)})")):
        e["label"] = label
        if failed:
            R.decisions.add("label", [e["id"]], "plain wording", failed, model=lab.model, label=label)
    R.edges = edges
    for rel in ("kind_of", "part_of", "depends_on"):
        R.count(f"edges_{rel}", sum(e["rel"] == rel for e in edges))
    R.dump("6_edges", edges)
