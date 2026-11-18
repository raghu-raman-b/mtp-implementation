"""Step 5: what each part teaches about each concept it names. Runs after the registry, lecture by lecture in course
order (facets build on earlier facets); the parts of one lecture run at once.

    5a mentions   code: the concept's canonical name and the names and abbreviations the lecturer used for it, found in
                  every part from the lecture that introduces it on; the parts where it is a key term always count
    5b facets     one call per part (MAX_CONCEPTS concepts at most per call): for each concept named there, taught or
                  only mentioned, and what the part teaches about it, saying what is new compared with every earlier
                  facet of the concept (as written, before their judge: the chain does not wait for the judge)
    judge         one call per part, off the chain: each facet supported by its sentences? Rewritten once; a facet
                  that still fails becomes "only mentioned"
"""
from __future__ import annotations


from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import addr as A
from . import prompts as P
from .context import Lecture, Part, Run
from .judge import Item, judge_unit, rewrite_items
from .match import SentenceIndex
from .s2_parts import prefix

MAX_CONCEPTS = 25


def mentions(R: Run) -> dict[tuple[str, str], list[int]]:
    """(concept id, part id) -> sentence numbers in that part where the concept is named."""
    idx = SentenceIndex()
    for lec in R.lectures:
        for i, s in enumerate(lec.sentences):
            idx.add(lec.id, i, s.text)
    out: dict[tuple[str, str], set[int]] = {}
    terms = {t["id"]: (lec, t) for lec in R.lectures for p in lec.parts for t in p.terms}
    for c in R.registry.concepts.values():
        hits = set()
        for nm in [c.name] + [a["text"] for a in c.aliases if a["kind"] == "name"]:
            hits |= set(idx.find_phrase(nm))
        for ab in c.abbrevs():
            hits |= set(idx.find_abbrev(ab))
        for lid, i in hits:
            lec = R.lec(lid)
            if lec.pos >= c.intro_pos:
                out.setdefault((c.id, lec.part_of(i).id), set()).add(i)
        for tid in c.terms:
            lec, t = terms[tid]
            out.setdefault((c.id, lec.part_of(t["sentences"][0]).id), set()).update(t["sentences"])
    R.mentions = {k: sorted(v) for k, v in out.items()}
    R.count("concept_part_mentions", len(R.mentions))
    return R.mentions


def earlier(R: Run, cid: str, pos: int) -> list[dict]:
    """The concept's facets from lectures before `pos`, as written (drafts), in course order."""
    with R.lock:
        fs = list(R.registry.concepts[cid].facets)
    fs = [f for f in fs if R.pos(A.lecture_of(f["part"])) < pos and f["draft"]]
    return sorted(fs, key=lambda f: (R.pos(A.lecture_of(f["part"])), f["part"]))


def _concept_lines(R: Run, lec: Lecture, p: Part, cids: list[str]) -> str:
    C = R.registry.concepts
    lines = []
    for k, cid in enumerate(cids, 1):
        c = C[cid]
        ids = R.mentions.get((cid, p.id), [])
        prev = earlier(R, cid, lec.pos)
        lines.append(f'C{k}: "{c.name}"{c.alias_text()}. Definition: {c.definition}')
        lines.append(f"  Named in sentences {ids}.")
        if prev:
            lines.append("  Earlier lectures taught:")
            lines += [f"   - {f['part']}: {f['draft']}" for f in prev]
        else:
            lines.append("  Earlier lectures: nothing yet.")
    return "\n".join(lines)


def _schema(n: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["facets"], "properties": {
        "facets": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["concept", "only_mentioned", "says", "sentence_ids"], "properties": {
                "concept": {"type": "string", "enum": [f"C{k}" for k in range(1, n + 1)]},
                "only_mentioned": {"type": "boolean"}, "says": {"type": "string"},
                "sentence_ids": {"type": "array", "items": {"type": "integer"}}}}}}}


def _chunk(R: Run, lec: Lecture, p: Part, cids: list[str], n: int) -> list[dict]:
    o = R.send("facets", Call(key=f"{p.id}/facets/{n}", lecture_id=lec.id, schema=_schema(len(cids)),
                              prompt=prefix(R, lec, p) + P.FACETS[2].format(concepts=_concept_lines(R, lec, p, cids)),
                              prompt_id=P.FACETS[0], prompt_version=P.FACETS[1]))
    got = {}
    for x in (o.parsed or {}).get("facets", []):
        got.setdefault(int(x["concept"][1:]) - 1, x)
    model = R.model_of("facets")
    out = []
    for k, cid in enumerate(cids):
        x = got.get(k)
        ids = sorted({i for i in (x or {}).get("sentence_ids", []) if p.contains(i)})
        real = bool(x and not x["only_mentioned"] and x["says"].strip() and ids)
        if x and not x["only_mentioned"] and not real:
            R.decisions.add("facets", [f"{cid}@{p.id}"], "kept as a mention",
                            "no statement or no sentence of this part cited", o, model)
        elif x is None:
            R.decisions.add("facets", [f"{cid}@{p.id}"], "kept as a mention",
                            f"the answer gave nothing for this concept{'' if o.parsed else f': {o.errors}'}", o, model)
        says = strip_ids(x["says"]) if real else None
        out.append({"id": f"{cid}@{p.id}", "part": p.id, "only_mentioned": not real, "says": says,
                    "sentences": [lec.s(i) for i in ids] if real else [],
                    "named_in": [lec.s(i) for i in R.mentions.get((cid, p.id), [])], "draft": says, "_cid": cid})
    return out


def run_lecture(R: Run, lec: Lecture):
    """All parts of one lecture (parts and chunks in parallel). Needs every earlier lecture's facets."""
    jobs = []
    for p in lec.parts:
        cids = sorted({cid for (cid, pid) in R.mentions if pid == p.id},
                      key=lambda c: (R.mentions[(c, p.id)][0], c))
        for n in range(0, len(cids), MAX_CONCEPTS):
            jobs.append((p, cids[n:n + MAX_CONCEPTS], n // MAX_CONCEPTS))
    found = R.flow.map("facets part", lambda j: _chunk(R, lec, *j), jobs)
    C = R.registry.concepts
    with R.lock:
        for (p, _, _), fs in zip(jobs, found):
            for f in fs:
                p.facets.append(f)
                C[f["_cid"]].facets.append(f)
    for p in lec.parts:
        p.facets.sort(key=lambda f: f["id"])
    R.count("facets_real", sum(1 for p in lec.parts for f in p.facets if not f["only_mentioned"]))
    R.count("facets_mention", sum(1 for p in lec.parts for f in p.facets if f["only_mentioned"]))


CRIT = "Facet: ok only if the statement is supported by its cited sentences and says something this part teaches " \
       "about the concept."


def judge_part(R: Run, lec: Lecture, p: Part):
    C = R.registry.concepts
    real = [f for f in p.facets if not f["only_mentioned"]]
    if not real:
        return
    pre = prefix(R, lec, p)

    def show(it: Item) -> str:
        f = it.obj
        return (f'Concept "{C[f["_cid"]].name}". What this part teaches about it: "{f["says"]}" '
                f'(cited sentences {[A.parse_sent(s)[1] for s in f["sentences"]]})')

    def rewrite(failed):
        r = rewrite_items(R, key=f"{p.id}/facets", lid=lec.id, prefix=pre, failed=failed, show=show,
                          item_schema={"properties": {"only_mentioned": {"type": "boolean"}, "says": {"type": "string"},
                                                      "sentence_ids": {"type": "array", "items": {"type": "integer"}}}},
                          rules="Say in one statement (at most 30 words), as a fact of the subject, what this part "
                                "teaches about the concept, with the numbers of the sentences that teach it; or set "
                                "only_mentioned if the part teaches nothing about it.",
                          check=lambda it, x: [] if x["only_mentioned"] or (
                              x["says"].strip() and x["sentence_ids"] and all(p.contains(i) for i in x["sentence_ids"]))
                          else [f"sentences must be in this part ({p.a} to {p.b})"])
        out = {}
        for k, x in r.items():
            if not x["only_mentioned"]:
                out[k] = {**failed[k].obj, "says": strip_ids(x["says"]),
                          "sentences": [lec.s(i) for i in sorted(set(x["sentence_ids"]))]}
        return out

    items = judge_unit(R, key=f"{p.id}/facets", lid=lec.id, prefix=pre, show=show, criteria=CRIT, rewrite=rewrite,
                       items=[Item(f, "facet", f["sentences"]) for f in real])
    with R.lock:
        for it, f in zip(items, real):
            if it.ok:
                f.update({"says": it.obj["says"], "sentences": it.obj["sentences"]})
            else:
                f.update({"only_mentioned": True, "says": None, "sentences": []})
                R.decisions.add("judge", [f["id"]], "facet became a mention", "failed the judge after a rewrite")
