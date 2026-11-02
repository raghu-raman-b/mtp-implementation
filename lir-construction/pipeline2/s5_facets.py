"""Step 5: what each part says about each concept it names.

    5a mentions   code: the concept's name and the names and abbreviations the lecturer used for it, found in every
                  part from the lecture that introduces it on; the parts where it is a key term always count
    5b facet      one call per concept and part: what the part teaches about it, or "only mentioned"
                  (calls on one part run in order on one slot: they share the part's transcript)
"""
from __future__ import annotations

from pydantic import BaseModel

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Run
from .match import SentenceIndex
from .s2_parts import prefix


class Facet(BaseModel):
    only_mentioned: bool
    says: str
    sentence_ids: list[int]


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
    return {k: sorted(v) for k, v in out.items()}


def run(R: Run):
    llm = R.llm("facets")
    found = mentions(R)
    reg = R.registry
    calls = []
    for (cid, pid), ids in found.items():
        c = reg.concepts[cid]
        lec = R.lec(pid.split("/")[0])
        p = lec.part(pid)
        d = c.definition_as_of(R, lec.id)
        text = P.FACET[2].format(name=c.name, aliases=c.alias_text(), definition=d["text"] if d else "", ids=ids)

        def check(x: Facet, p=p):
            if x.only_mentioned:
                return []
            errs = [] if x.says.strip() else ["says is empty; write what the part teaches, or set only_mentioned"]
            bad = [i for i in x.sentence_ids if not p.contains(i)]
            if bad or not x.sentence_ids:
                errs.append(f"sentence_ids must be numbers of sentences in this part ({p.a} to {p.b})")
            return errs
        calls.append(Call(key=f"{cid}@{pid}", lecture_id=lec.id, prompt=prefix(R, lec, p) + text, schema=Facet,
                          prompt_id=P.FACET[0], prompt_version=P.FACET[1], group=pid, check=check,
                          ctx={"cid": cid, "lec": lec, "part": p, "ids": ids}))
    for o in llm.run("v2_facets", calls, f"facets ({len(calls)} concept-part pairs)"):
        cid, lec, p, ids = (o.call.ctx[k] for k in ("cid", "lec", "part", "ids"))
        R.record(o, "facets", llm, o.call.key)
        x: Facet | None = o.parsed if o.ok else None
        real = x is not None and not x.only_mentioned
        if o.parsed is not None and not o.ok:
            R.decisions.add("facets", [f"{cid}@{p.id}"], "kept as a mention", f"answer failed the checks: {o.errors}",
                            o, llm.model)
        reg.concepts[cid].facets.append({
            "id": f"{cid}@{p.id}", "part": p.id, "only_mentioned": not real,
            "says": strip_ids(x.says) if real else None,
            "sentences": [lec.s(i) for i in sorted(set(x.sentence_ids))] if real else [],
            "named_in": [lec.s(i) for i in ids]})
        R.count("facets_real" if real else "facets_mention")
    for c in reg.concepts.values():
        c.facets.sort(key=lambda f: (R.pos(f["part"].split("/")[0]), f["part"]))
    R.dump("5_facets", {c.id: c.facets for c in reg.concepts.values()})
