"""Step 4: the concept registry, built lecture by lecture in course order.

For the terms of lecture k:
    4a candidates   code: the same name (or a name/alias the lecturer used) joins at once; otherwise registry concepts
                    (as of lecture k-1) with the same attested abbreviation or among the NEIGHBOURS nearest by
                    embedding at FLOOR or more, and the same for other terms of lecture k
    4b same?        one yes/no call per candidate pair. A term is compared with the concept's entry (name, current
                    definition, sources), never with one of its members, so merges cannot chain. Terms of one lecture
                    form a new concept together only if every pair of them answered "same".
    4c definition   the definition as of lecture k, written from the previous one plus lecture k's definitions,
                    checked against all their sentences (one rewrite)
Pairs that were similar but answered "different" are kept for the edge step.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel

from pipeline.embed import embed
from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids
from pipeline.validate import display_name

from . import match as M
from . import prompts as P
from .context import Lecture, Run

NEIGHBOURS, FLOOR = 5, 0.6
MAX_SENTS = 6            # sentences shown per side in a same-concept call
MAX_DEF_SENTS = 24       # sentences shown when refining a definition


class Same(BaseModel):
    reason: str
    same: bool


class Define(BaseModel):
    definition: str


class Grounded(BaseModel):
    reason: str
    supported: bool


@dataclass
class Concept:
    id: str
    name: str
    aliases: list[dict]           # {text, kind: name | abbreviation, said_at}
    introduced: str               # sentence address
    introduced_part: str
    intro_pos: int
    terms: list[str] = field(default_factory=list)          # term occurrence IDs
    definitions: list[dict] = field(default_factory=list)   # {as_of, text, sources, from_terms}
    facets: list[dict] = field(default_factory=list)
    emb: np.ndarray | None = None

    def keys(self) -> set[str]:
        return {M.key(self.name)} | {M.key(a["text"]) for a in self.aliases if a["kind"] == "name"}

    def abbrevs(self) -> set[str]:
        return {a["text"] for a in self.aliases if a["kind"] == "abbreviation"}

    def latest(self) -> dict | None:
        return self.definitions[-1] if self.definitions else None

    def definition_as_of(self, R: Run, lid: str) -> dict | None:
        k = R.pos(lid)
        ok = [d for d in self.definitions if R.pos(d["as_of"]) <= k]
        return ok[-1] if ok else None

    def alias_text(self) -> str:
        names = [a["text"] for a in self.aliases][:5]
        return f" (also called {', '.join(names)})" if names else ""


class Registry:
    def __init__(self):
        self.concepts: dict[str, Concept] = {}

    def new_id(self) -> str:
        return f"C{len(self.concepts) + 1:04d}"


def labelled(R: Run, addresses) -> str:
    out = []
    for a in addresses:
        lid, i = a.rsplit("/S", 1)
        out.append(f"[{a}] {R.lec(lid).sentences[int(i)].text}")
    return "\n".join(out)


def _attach(c: Concept, t: dict, lec: Lecture):
    c.terms.append(t["id"])
    t["concept_id"] = c.id
    at = lec.s(t["sentences"][0])
    for nm in (t["name"], t["surface"]):
        if M.key(nm) and M.key(nm) not in c.keys():
            c.aliases.append({"text": display_name(nm), "kind": "name", "said_at": at})
    if t["abbreviation"] and t["abbreviation"] not in c.abbrevs():
        c.aliases.append({"text": t["abbreviation"], "kind": "abbreviation", "said_at": t["abbreviation_at"]})


def _same_call(R: Run, lec: Lecture, key: str, group: str, a: dict, b: dict, ctx: dict) -> Call:
    return Call(key=key, lecture_id=lec.id, group=group, schema=Same, prompt_id=P.SAME[0], prompt_version=P.SAME[1],
                prompt=P.SAME[2].format(role=P.ROLE, course=R.course.title, a_name=a["name"], a_alias=a["alias"],
                                        a_def=a["def"], a_where=a["where"], a_sents=a["sents"], b_name=b["name"],
                                        b_alias=b["alias"], b_def=b["def"], b_where=b["where"], b_sents=b["sents"]),
                ctx=ctx)


def _concept_side(R: Run, c: Concept) -> dict:
    d = c.latest()
    return {"name": c.name, "alias": c.alias_text(), "def": d["text"] if d else "(no definition)",
            "where": f"from lecture {d['as_of'] if d else c.introduced.split('/')[0]}",
            "sents": labelled(R, (d["sources"] if d else [c.introduced])[:MAX_SENTS])}


def _term_side(R: Run, lec: Lecture, t: dict) -> dict:
    alias = f" (abbreviation: {t['abbreviation']})" if t["abbreviation"] else ""
    return {"name": t["name"], "alias": alias, "def": t["definition"], "where": f"lecture {lec.id}",
            "sents": labelled(R, [lec.s(i) for i in t["sentences"][:MAX_SENTS]])}


def _lecture(R: Run, reg: Registry, lec: Lecture, llm):
    terms = [t for p in lec.parts for t in p.terms]
    if not terms:
        return
    model = llm.model
    T = embed([f"{t['name']}: {t['definition']}" for t in terms])
    existing = list(reg.concepts.values())
    E = np.stack([c.emb for c in existing]) if existing else None
    key_to_cid = {}
    for c in existing:
        for k in c.keys():
            key_to_cid.setdefault(k, c.id)
    subj = lambda i: [lec.s(j) for j in terms[i]["sentences"]]

    # groups of terms with the same name inside this lecture: one representative each
    groups: list[list[int]] = []
    by_key: dict[str, int] = {}
    for i, t in enumerate(terms):
        k = M.key(t["name"])
        if k in by_key:
            groups[by_key[k]].append(i)
            R.decisions.add("same", subj(i), "same name", f'same name as {terms[groups[by_key[k]][0]]["id"]}',
                            term=t["id"])
        else:
            by_key[k] = len(groups)
            groups.append([i])
    rep_of = {i: g[0] for g in groups for i in g}

    joined: dict[int, str] = {}           # representative -> concept id
    for g in groups:
        r = g[0]
        t = terms[r]
        hit = next((key_to_cid[k] for k in (M.key(t["name"]), M.key(t["surface"])) if k in key_to_cid), None)
        if hit:
            joined[r] = hit
            R.decisions.add("same", subj(r), "joined by name", f'"{t["name"]}" is a name of {hit} '
                            f'({reg.concepts[hit].name})', term=t["id"], concept=hit)
    reps = [g[0] for g in groups]
    sim_t = T @ T.T
    sims_c = (E @ T.T) if E is not None else None   # concepts x terms

    def concept_cands(r: int) -> list[str]:
        t, out = terms[r], []
        if t["abbreviation"]:
            out += [c.id for c in existing if t["abbreviation"] in c.abbrevs()]
        if sims_c is not None:
            col = sims_c[:, r]
            out += [existing[j].id for j in np.argsort(-col)[:NEIGHBOURS] if col[j] >= FLOOR]
        return list(dict.fromkeys(out))

    def term_cands(r: int) -> list[int]:
        t, out = terms[r], []
        others = [x for x in reps if x != r]
        if t["abbreviation"]:
            out += [x for x in others if terms[x]["abbreviation"] == t["abbreviation"]]
        out += [x for x in sorted(others, key=lambda x: -sim_t[r, x])[:NEIGHBOURS] if sim_t[r, x] >= FLOOR]
        return list(dict.fromkeys(out))

    answers: dict[tuple, bool] = {}       # ("c", rep, cid) or ("t", min rep, max rep) -> same?

    def ask(pairs: list[tuple]):
        calls = []
        for p in pairs:
            if p in answers:
                continue
            if p[0] == "c":
                _, r, cid = p
                calls.append(_same_call(R, lec, f"{lec.id}/same/{cid}|{terms[r]['id']}", cid,
                                        _concept_side(R, reg.concepts[cid]), _term_side(R, lec, terms[r]), {"pair": p}))
            else:
                _, x, y = p
                calls.append(_same_call(R, lec, f"{lec.id}/same/{terms[x]['id']}|{terms[y]['id']}", terms[x]["id"],
                                        _term_side(R, lec, terms[x]), _term_side(R, lec, terms[y]), {"pair": p}))
        for o in llm.run("v2_registry_same", calls, f"{lec.id}: same-concept checks ({len(calls)})"):
            p = o.call.ctx["pair"]
            R.record(o, "same", llm, o.call.key)
            same = bool(o.parsed and o.parsed.same)
            answers[p] = same
            why = o.parsed.reason if o.parsed else f"no usable answer: {o.errors}"
            if p[0] == "c":
                R.decisions.add("same", subj(p[1]), "same" if same else "different", why, o, model,
                                term=terms[p[1]]["id"], concept=p[2])
            else:
                R.decisions.add("same", subj(p[1]) + subj(p[2]), "same" if same else "different", why, o, model,
                                terms=[terms[p[1]]["id"], terms[p[2]]["id"]])
            R.count("same_checks")

    tt = lambda x, y: ("t", min(x, y), max(x, y))
    round1 = [("c", r, cid) for r in reps if r not in joined for cid in concept_cands(r)]
    round1 += list(dict.fromkeys(tt(r, x) for r in reps for x in term_cands(r)))
    ask(round1)

    def resolve():
        for r in reps:
            if r in joined:
                continue
            yes = [cid for cid in concept_cands(r) if answers.get(("c", r, cid))]
            if yes:
                best = max(yes, key=lambda cid: float(sims_c[[c.id for c in existing].index(cid), r]))
                joined[r] = best
                if len(yes) > 1:
                    R.decisions.add("same", subj(r), "conflict", f"same as {yes}; joined {best}, the most similar",
                                    term=terms[r]["id"], concepts=yes)
    resolve()
    # round 2: a term "same" as a term that joined a concept is asked about that concept directly
    round2 = [("c", r, joined[x]) for r in reps if r not in joined for x in reps
              if x in joined and answers.get(tt(r, x)) and ("c", r, joined[x]) not in answers]
    if round2:
        ask(list(dict.fromkeys(round2)))
        for r in reps:  # make the round-2 concepts candidates of their terms
            if r in joined:
                continue
            yes = [cid for (k, rr, cid) in [p for p in answers if p[0] == "c"] if rr == r and answers[("c", rr, cid)]]
            if yes:
                joined[r] = yes[0]

    # joined terms
    for r, cid in joined.items():
        for i in groups[[g[0] for g in groups].index(r)]:
            _attach(reg.concepts[cid], terms[i], lec)
    # the rest: new concepts; terms merge only if every pair said "same"
    clusters: list[list[int]] = []
    for r in reps:
        if r in joined:
            continue
        home = next((cl for cl in clusters if all(answers.get(tt(r, m)) for m in cl)), None)
        (home.append(r) if home is not None else clusters.append([r]))
    for cl in clusters:
        members = sorted((i for r in cl for i in groups[[g[0] for g in groups].index(r)]),
                         key=lambda i: (lec.part_of(terms[i]["sentences"][0]).n, terms[i]["sentences"][0]))
        first = terms[members[0]]
        c = Concept(reg.new_id(), first["name"], [], lec.s(first["sentences"][0]),
                    lec.part_of(first["sentences"][0]).id, lec.pos)
        reg.concepts[c.id] = c
        for i in members:
            _attach(c, terms[i], lec)
        R.decisions.add("same", [c.introduced], "new concept", f"{len(members)} term(s): "
                        + ", ".join(terms[i]["id"] for i in members), concept=c.id, name=c.name)
        R.count("concepts")
    # similar but different: candidates for the edge step
    cid_of = lambda r: terms[r]["concept_id"]
    for p, same in answers.items():
        if same:
            continue
        a, b = (p[2], cid_of(p[1])) if p[0] == "c" else (cid_of(p[1]), cid_of(p[2]))
        if a and b and a != b:
            R.similar_pairs.append((a, b, lec.id))


def _definitions(R: Run, reg: Registry, lec: Lecture, llm):
    """4c: the definition as of this lecture for every concept that got terms here."""
    touched: dict[str, list[dict]] = {}
    for p in lec.parts:
        for t in p.terms:
            if t["concept_id"]:
                touched.setdefault(t["concept_id"], []).append(t)
    model = llm.model
    jobs, order = [], []
    for cid, ts in touched.items():
        c = reg.concepts[cid]
        prev = c.latest()
        new_sources = [lec.s(i) for t in ts for i in t["sentences"]]
        if prev is None and len(ts) == 1:  # one definition, already checked in step 3
            c.definitions.append({"as_of": lec.id, "text": ts[0]["definition"], "sources": new_sources,
                                  "from_terms": [ts[0]["id"]]})
            continue
        defs = ([f"- (lecture {prev['as_of']}) {prev['text']}"] if prev else []) + \
               [f"- (lecture {lec.id}) {t['definition']}" for t in ts]
        sources = list(dict.fromkeys((prev["sources"] if prev else []) + new_sources))
        if len(sources) > MAX_DEF_SENTS:  # keep the newest sentences and the first ones
            sources = sources[:MAX_DEF_SENTS // 3] + sources[-(MAX_DEF_SENTS - MAX_DEF_SENTS // 3):]
        sents = labelled(R, sources)
        jobs.append(_refine_job(R, lec, c, prev, ts, defs, sents, sources, llm))
        order.append(cid)
    for cid, version in zip(order, llm.run_jobs("v2_registry_define", jobs, f"{lec.id}: definitions ({len(jobs)})")):
        c = reg.concepts[cid]
        if version is not None:
            c.definitions.append(version)
        elif c.latest() is None:  # a new concept whose combined definition failed: its first term's definition
            t = touched[cid][0]
            c.definitions.append({"as_of": lec.id, "text": t["definition"],
                                  "sources": [lec.s(i) for i in t["sentences"]], "from_terms": [t["id"]]})
    if touched:
        embs = embed([f"{reg.concepts[c].name}: {reg.concepts[c].latest()['text']}" for c in touched])
        for c, e in zip(touched, embs):
            reg.concepts[c].emb = e


def _refine_job(R, lec, c, prev, ts, defs, sents, sources, llm):
    model = llm.model

    def job(send):
        text, reason = None, ""
        for attempt in range(2):
            extra = P.REWRITE.format(previous=text, reason=reason) if attempt else ""
            o = send(Call(key=f"{lec.id}/refine/{c.id}/{attempt}", lecture_id=lec.id, schema=Define,
                          prompt=P.REFINE[2].format(role=P.ROLE, name=c.name, course=R.course.title,
                                                    defs="\n".join(defs), sents=sents) + extra,
                          prompt_id=P.REFINE[0], prompt_version=P.REFINE[1],
                          check=lambda x: [] if x.definition.strip() else ["the definition is empty"]))
            R.record(o, "refine", llm, o.call.key)
            if o.parsed is None:
                reason = f"no usable definition: {o.errors}"
                break
            text = strip_ids(o.parsed.definition)
            g = send(Call(key=f"{lec.id}/refine_check/{c.id}/{attempt}", lecture_id=lec.id, schema=Grounded,
                          prompt=P.GROUND_ALL[2].format(role=P.ROLE, name=c.name, sents=sents, definition=text,
                                                        where=" in these sentences"),
                          prompt_id=P.GROUND_ALL[0], prompt_version=P.GROUND_ALL[1]))
            R.record(g, "ground", llm, g.call.key)
            if g.parsed is not None and g.parsed.supported:
                R.decisions.add("refine", [c.introduced], "definition", f"as of {lec.id}, from "
                                f"{len(defs)} definition(s)", g, model, concept=c.id)
                return {"as_of": lec.id, "text": text, "sources": sources,
                        "from_terms": [t["id"] for t in ts]}
            reason = g.parsed.reason if g.parsed else f"no usable check: {g.errors}"
            R.decisions.add("refine", [c.introduced], "definition rejected", reason, g, model, concept=c.id,
                            definition=text)
        R.decisions.add("refine", [c.introduced], "kept the previous definition" if prev else "first term's definition",
                        f"no supported combined definition: {reason}", model=model, concept=c.id)
        return None
    return job


def run(R: Run):
    llm = R.llm("same")
    if R.llm("refine") is not llm:
        raise SystemExit("steps same and refine must use the same model")
    reg = Registry()
    R.registry = reg
    for lec in R.lectures:  # course order: lecture k sees the registry as of lecture k-1
        _lecture(R, reg, lec, llm)
        _definitions(R, reg, lec, llm)
        R.log(f"  {lec.id}: {sum(len(p.terms) for p in lec.parts)} terms -> registry has {len(reg.concepts)} concepts")
    R.dump("4_registry", {c.id: {"name": c.name, "aliases": c.aliases, "introduced": c.introduced,
                                 "terms": c.terms, "definitions": c.definitions} for c in reg.concepts.values()})
