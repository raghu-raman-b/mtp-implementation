"""Step 6: links between concepts, one lecture at a time (after that lecture's facets are judged). Three relations,
each read as "src REL dst":

    kind_of      src is a specific kind of the more general dst
    part_of      src is a component or part of dst
    depends_on   to understand src, a learner must first understand dst

    propose   one call per lecture (verifier): every concept named in the lecture with its canonical definition,
              what this lecture and earlier lectures teach about it (facets) and up to MAX_SENTS of the lecture's
              sentences that name it; the call lists every relation the lecture states or clearly implies, each with a
              label and evidence. Code checks: two different concepts, evidence among the sentences shown.
    judge     one call per lecture: each link supported, right direction, label true and natural? A link that holds
              the other way round is flipped by code (with the relation's plain wording as label); one that fails
              is dropped. No rewrite.
    merge     code, in course order: the same link found again joins its evidence (the earliest lecture is kept); a
              pair linked differently later is logged as a conflict and the earliest link kept. Any graph shape is
              allowed, cycles included; a two-way kind_of / part_of is flagged, and a depends_on from a concept to a
              later one is flagged "forward".
"""
from __future__ import annotations


from pipeline.llm import Call

from . import addr as A
from . import prompts as P
from .context import Lecture, Run
from .judge import Item, judge_unit
from .s5_facets import earlier

RELS = ["kind_of", "part_of", "depends_on"]
MAX_SENTS = 6


def _concepts(R: Run, lec: Lecture) -> list[str]:
    first = {}
    for (cid, pid), ids in R.mentions.items():
        if A.lecture_of(pid) == lec.id:
            first[cid] = min(first.get(cid, (10 ** 9,)), (lec.part(pid).n, ids[0]))
    return sorted(first, key=lambda c: (first[c], c))


def _sentences(R: Run, lec: Lecture, cid: str) -> list[int]:
    """Up to MAX_SENTS sentences of this lecture for the concept: the ones its facets cite first, then where named."""
    c = R.registry.concepts[cid]
    with R.lock:
        fs = [f for f in c.facets if A.lecture_of(f["part"]) == lec.id]
    taught = [A.parse_sent(s)[1] for f in fs for s in f["sentences"]]
    named = [i for (x, pid), ids in R.mentions.items() if x == cid and A.lecture_of(pid) == lec.id for i in ids]
    return sorted(list(dict.fromkeys(taught + sorted(named)))[:MAX_SENTS])


def block(R: Run, lec: Lecture) -> tuple[str, list[str], set[int]]:
    """The concept block shared by the link call and its judge: text, concept IDs by label, sentence numbers shown."""
    C = R.registry.concepts
    cids = _concepts(R, lec)
    shown: set[int] = set()
    lines = []
    for k, cid in enumerate(cids, 1):
        c = C[cid]
        with R.lock:
            here = [f for f in c.facets if A.lecture_of(f["part"]) == lec.id]
        lines.append(f'C{k}: "{c.name}"{c.alias_text()}. Definition: {c.definition}')
        taught = [f for f in here if not f["only_mentioned"]]
        lines.append("  This lecture: " + ("; ".join(f"{f['part']}: {f['says']}" for f in taught) if taught
                                           else "only mentioned"))
        prev = [f for f in earlier(R, cid, lec.pos) if not f["only_mentioned"] and f["says"]]
        if prev:
            lines.append("  Earlier lectures: " + "; ".join(f"{f['part']}: {f['says']}" for f in prev))
        ids = _sentences(R, lec, cid)
        shown |= set(ids)
        lines += [f"  [{i}] {lec.sentences[i].text}" for i in ids]
    text = (f"{P.ROLE}\n\nCourse: {R.course.title}\nLecture {lec.id}: {lec.inp.title}\n\nThe concepts named in this "
            f"lecture. For each: its definition, what this lecture teaches about it, what earlier lectures taught "
            f"about it, and sentences of this lecture that name it:\n\n" + "\n".join(lines) + "\n\n")
    return text, cids, shown


def _schema(n: int) -> dict:
    labels = [f"C{k}" for k in range(1, n + 1)]
    return {"type": "object", "additionalProperties": False, "required": ["links"], "properties": {
        "links": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["a", "relation", "b", "label", "evidence"],
            "properties": {"a": {"type": "string", "enum": labels}, "relation": {"type": "string", "enum": RELS},
                           "b": {"type": "string", "enum": labels}, "label": {"type": "string"},
                           "evidence": {"type": "array", "items": {"type": "integer"}}}}}}}


def run_lecture(R: Run, lec: Lecture):
    """Propose the lecture's links, then judge them; the kept ones go to lec.links."""
    C = R.registry.concepts
    pre, cids, shown = block(R, lec)
    if len(cids) < 2:
        lec.links = []
        return
    o = R.send("links", Call(key=f"{lec.id}/links", lecture_id=lec.id, schema=_schema(len(cids)),
                             prompt_id=P.LINKS[0], prompt_version=P.LINKS[1], prompt=pre + P.LINKS[2]))
    model = R.model_of("links")
    props, pairs = [], set()
    for x in (o.parsed or {}).get("links", []):
        a, b = cids[int(x["a"][1:]) - 1], cids[int(x["b"][1:]) - 1]
        ev = sorted({i for i in x["evidence"] if i in shown})
        label = x["label"].strip().strip('"').rstrip(".")
        why = ("a concept linked to itself" if a == b else "no evidence among the sentences shown" if not ev
               else "the same pair twice" if frozenset((a, b)) in pairs
               else "label of more than 8 words or empty" if not 0 < len(label.split()) <= 8 else "")
        if why:
            R.decisions.add("links", [a, b], "dropped", why, o, model, relation=x["relation"])
            continue
        pairs.add(frozenset((a, b)))
        props.append({"src": a, "rel": x["relation"], "dst": b, "label": label,
                      "evidence": [lec.s(i) for i in ev], "lecture_id": lec.id, "flags": []})
    if o.parsed is None:
        R.flag(lec.id, f"links: answer unusable ({o.errors})")

    def show(it: Item) -> str:
        e = it.obj
        ev = " ".join(f"[{A.parse_sent(s)[1]}]" for s in e["evidence"])
        return (f'Link: "{C[e["src"]].name}" {e["rel"]} "{C[e["dst"]].name}", shown to learners as '
                f'"{C[e["src"]].name} {e["label"]} {C[e["dst"]].name}". Evidence: sentences {ev}')

    crit = ("Link: ok only if the lecture states or clearly implies the relation (kind_of: the first is a specific "
            "kind of the second; part_of: the first is a component or part of the second; depends_on: to understand "
            "the first, a learner must first understand the second) in its evidence sentences or in what this "
            "lecture teaches about the two concepts, and the sentence shown to learners is true and reads naturally.")
    items = judge_unit(R, key=f"{lec.id}/links", lid=lec.id, prefix=pre, show=show, criteria=crit,
                       with_reversed=True, items=[Item(e, "link", [e["src"], e["dst"]]) for e in props])
    kept = []
    for it in items:
        e = it.obj
        if it.ok:
            kept.append(e)
        elif it.reversed:
            kept.append({**e, "src": e["dst"], "dst": e["src"], "label": P.REL_TEXT[e["rel"]],
                         "flags": e["flags"] + ["flipped"]})
            R.decisions.add("links", [e["dst"], e["src"]], "flipped", it.reason, model=R.model_of("judge"))
        else:
            R.decisions.add("links", [e["src"], e["dst"]], "dropped", f"failed the judge: {it.reason}",
                            model=R.model_of("judge"), relation=e["rel"])
    lec.links = kept
    R.count("links_proposed", len(props))
    R.count("links_kept", len(kept))


def merged(R: Run, upto_pos: int | None = None, log: bool = False) -> list[dict]:
    """The links of lectures up to `upto_pos` (all by default), merged in course order. With log=True the merge
    decisions go to the decision log."""
    C = R.registry.concepts
    out: list[dict] = []
    by_key: dict[tuple, dict] = {}
    by_pair: dict[frozenset, dict] = {}
    for lec in R.lectures:
        if upto_pos is not None and lec.pos > upto_pos:
            break
        for e in lec.links:
            k = (e["src"], e["rel"], e["dst"])
            if k in by_key:
                by_key[k]["evidence"] = sorted(set(by_key[k]["evidence"]) | set(e["evidence"]), key=R.order)
                continue
            pair = frozenset((e["src"], e["dst"]))
            first = by_pair.get(pair)
            if first is not None and not (first["rel"] == e["rel"] and first["src"] == e["dst"]
                                          and e["rel"] in ("kind_of", "part_of")):
                if log:
                    R.decisions.add("links", [e["src"], e["dst"]], "conflict",
                                    f"{lec.id} links them as {e['src']} {e['rel']} {e['dst']}; kept the earlier "
                                    f"{first['src']} {first['rel']} {first['dst']} ({first['lecture_id']})")
                continue
            x = {**e, "flags": list(e["flags"])}
            if first is not None:   # the same kind_of / part_of both ways: kept, flagged on both
                x["flags"].append("two_way")
                if "two_way" not in first["flags"]:
                    first["flags"].append("two_way")
            if x["rel"] == "depends_on" and R.order(C[x["src"]].introduced) < R.order(C[x["dst"]].introduced):
                x["flags"].append("forward")
            by_key[k] = x
            by_pair.setdefault(pair, x)
            out.append(x)
    return out


def finalize(R: Run):
    edges = merged(R, log=True)
    edges.sort(key=lambda e: (R.pos(e["lecture_id"]), R.order(e["evidence"][0]), e["src"], e["dst"]))
    for n, e in enumerate(edges, 1):
        e["id"] = f"E{n:04d}"
    R.edges = edges
    for rel in RELS:
        R.count(f"edges_{rel}", sum(e["rel"] == rel for e in edges))
    R.dump("6_edges", edges)
