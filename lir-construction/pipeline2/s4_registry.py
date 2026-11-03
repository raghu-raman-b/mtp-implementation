"""Step 4: the concept registry, built once for the whole course from every judged key term.

    entries   code: term occurrences with the same name (word stems) form one entry
    groups    code: entries that are all similar to each other (embedding of "name: definition" at FLOOR or more, or
              the same abbreviation the lecturer used) form a candidate group, at most MAX_GROUP entries; every member
              must be similar to every other member, so a group cannot grow by chaining through one term
    concepts  one call per group of two or more entries, or per entry explained in more than one place: which entries
              are the same concept (the verifier splits the group), the canonical name, a course-wide definition
              combining the entries' definitions, and the reason. An entry explained once, alone in its group, is a
              concept as it is (its definition was judged in step 3).
    write back  each term occurrence gets its concept ID and canonical name; the lecture keeps its own definition
              (what the learner sees there), the concept keeps the canonical one (used to build the graph).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, Field

from pipeline.embed import embed
from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids
from pipeline.validate import display_name

from . import match as M
from . import prompts as P
from .context import Run
from .flow import CRIT

FLOOR, MAX_GROUP = 0.6, 8
MAX_OCC, MAX_SENTS = 4, 3     # per entry in a registry prompt: occurrences shown, sentences per occurrence


class RegConcept(BaseModel):
    entries: list[int] = Field(min_length=1)
    reason: str
    name: str
    definition: str


class RegAnswer(BaseModel):
    concepts: list[RegConcept] = Field(min_length=1)


@dataclass
class Concept:
    id: str
    name: str
    aliases: list[dict]           # {text, kind: name | abbreviation, said_at}
    introduced: str               # sentence address
    introduced_part: str
    intro_pos: int
    terms: list[str] = field(default_factory=list)          # term occurrence IDs
    definition: str = ""          # canonical, course-wide
    reason: str = ""              # why these terms are one concept
    sources: list[str] = field(default_factory=list)        # the sentences its definitions rest on
    facets: list[dict] = field(default_factory=list)
    emb: np.ndarray | None = None

    def keys(self) -> set[str]:
        return {M.key(self.name)} | {M.key(a["text"]) for a in self.aliases if a["kind"] == "name"}

    def abbrevs(self) -> set[str]:
        return {a["text"] for a in self.aliases if a["kind"] == "abbreviation"}

    def alias_text(self) -> str:
        names = [a["text"] for a in self.aliases][:5]
        return f" (also called {', '.join(names)})" if names else ""


class Registry:
    def __init__(self):
        self.concepts: dict[str, Concept] = {}


def labelled(R: Run, addresses) -> str:
    return "\n".join(f"[{a}] {R.sentence(a)}" for a in addresses)


def _entries(R: Run) -> list[dict]:
    """Term occurrences with the same name, in course order of their first occurrence."""
    by_key: dict[str, dict] = {}
    for lec in R.lectures:
        for p in lec.parts:
            for t in p.terms:
                k = M.key(t["name"]) or t["name"].lower()
                e = by_key.setdefault(k, {"key": k, "name": t["name"], "occ": []})
                e["occ"].append((lec, p, t))
    return list(by_key.values())


def _groups(entries: list[dict]) -> list[list[int]]:
    n = len(entries)
    if n == 0:
        return []
    E = embed([" | ".join(f"{t['name']}: {t['definition']}" for _, _, t in e["occ"][:3]) for e in entries])
    S = E @ E.T
    abbr = [{t["abbreviation"] for _, _, t in e["occ"] if t["abbreviation"]} for e in entries]
    for i in range(n):
        for j in range(i + 1, n):
            if abbr[i] & abbr[j]:
                S[i, j] = S[j, i] = 1.0
    root = list(range(n))
    members = {i: [i] for i in range(n)}
    pairs = sorted(((S[i, j], i, j) for i in range(n) for j in np.nonzero(S[i, i + 1:] >= FLOOR)[0] + i + 1),
                   reverse=True)
    for _, i, j in pairs:
        a, b = root[i], root[j]
        if a == b or len(members[a]) + len(members[b]) > MAX_GROUP:
            continue
        if S[np.ix_(members[a], members[b])].min() < FLOOR:   # complete linkage: everyone similar to everyone
            continue
        for x in members[b]:
            root[x] = a
        members[a] += members.pop(b)
    return sorted(members.values(), key=lambda g: min(g))


def _entry_text(R: Run, k: int, e: dict) -> str:
    occ = e["occ"] if len(e["occ"]) <= MAX_OCC else e["occ"][:MAX_OCC // 2] + e["occ"][-(MAX_OCC // 2):]
    abbrs = sorted({t["abbreviation"] for _, _, t in e["occ"] if t["abbreviation"]})
    lines = [f'E{k}: "{e["name"]}"' + (f" (abbreviation: {', '.join(abbrs)})" if abbrs else "")
             + (f", explained in {len(e['occ'])} places" if len(e["occ"]) > 1 else "")]
    for lec, _, t in occ:
        lines.append(f"  - lecture {lec.id}: {t['definition']}")
        lines += [f"    [{lec.s(i)}] {lec.sentences[i].text}" for i in t["sentences"][:MAX_SENTS]]
    return "\n".join(lines)


def _decide(R: Run, entries: list[dict], g: list[int]) -> list[dict]:
    """One call for a group: concepts as {members: [entry index], name, definition, reason}."""
    if len(g) == 1 and len(entries[g[0]]["occ"]) == 1:
        e = entries[g[0]]
        return [{"members": g, "name": e["name"], "definition": e["occ"][0][2]["definition"],
                 "reason": "a single key term", "call": None}]
    lid = entries[g[0]]["occ"][0][0].id
    text = "\n\n".join(_entry_text(R, k, entries[i]) for k, i in enumerate(g, 1))
    o = R.send("registry", Call(key=f"registry/{entries[g[0]]['key']}", lecture_id=lid, schema=RegAnswer,
                                prompt_id=P.REGISTRY[0], prompt_version=P.REGISTRY[1],
                                prompt=P.REGISTRY[2].format(role=P.ROLE, course=R.course.title, entries=text)))
    out, used = [], set()
    if o.parsed is not None:
        for c in o.parsed.concepts:
            mem = [g[k - 1] for k in dict.fromkeys(c.entries) if 1 <= k <= len(g) and g[k - 1] not in used]
            if not mem:
                continue
            used.update(mem)
            first = entries[mem[0]]
            out.append({"members": mem, "name": display_name(strip_ids(c.name)) or first["name"],
                        "definition": strip_ids(c.definition) or first["occ"][0][2]["definition"],
                        "reason": c.reason, "call": o})
    for i in g:   # an entry the answer left out stands alone with its first definition
        if i not in used:
            e = entries[i]
            out.append({"members": [i], "name": e["name"], "definition": e["occ"][0][2]["definition"],
                        "reason": "not placed by the registry call" if o.parsed is not None
                        else f"no usable registry answer: {o.errors}", "call": o})
    return out


def run(R: Run):
    entries = _entries(R)
    groups = _groups(entries)
    R.count("registry_entries", len(entries))
    R.count("registry_calls", sum(1 for g in groups if len(g) > 1 or len(entries[g[0]]["occ"]) > 1))
    decided = R.flow.map("registry", lambda g: _decide(R, entries, g), groups, prio=CRIT)
    found = [c for cs in decided for c in cs]

    def first_occ(c):
        return min(((lec.pos, t["sentences"][0], lec, p, t) for i in c["members"] for lec, p, t in entries[i]["occ"]),
                   key=lambda x: (x[0], x[1]))
    found.sort(key=lambda c: first_occ(c)[:2])
    reg = Registry()
    R.registry = reg
    model = R.model_of("registry")
    for n, c in enumerate(found, 1):
        _, _, lec, p, t0 = first_occ(c)
        con = Concept(f"C{n:04d}", c["name"], [], lec.s(t0["sentences"][0]), p.id, lec.pos,
                      definition=c["definition"], reason=c["reason"])
        occs = sorted(((l, pp, t) for i in c["members"] for l, pp, t in entries[i]["occ"]),
                      key=lambda x: (x[0].pos, x[2]["sentences"][0]))
        for l, pp, t in occs:
            con.terms.append(t["id"])
            t["concept_id"], t["concept_name"] = con.id, con.name
            at = l.s(t["sentences"][0])
            for nm in (t["name"], t["surface"]):
                if M.key(nm) and M.key(nm) not in con.keys():
                    con.aliases.append({"text": display_name(nm), "kind": "name", "said_at": at})
            if t["abbreviation"] and t["abbreviation"] not in con.abbrevs():
                con.aliases.append({"text": t["abbreviation"], "kind": "abbreviation", "said_at": t["abbreviation_at"]})
            con.sources += [l.s(i) for i in t["sentences"]]
        con.sources = list(dict.fromkeys(con.sources))
        reg.concepts[con.id] = con
        R.decisions.add("registry", [con.introduced], "concept", c["reason"], c["call"], model if c["call"] else None,
                        concept=con.id, name=con.name, terms=con.terms)
    if reg.concepts:
        embs = embed([f"{c.name}: {c.definition}" for c in reg.concepts.values()])
        for c, e in zip(reg.concepts.values(), embs):
            c.emb = e
    R.count("concepts", len(reg.concepts))
    R.log(f"  registry: {sum(len(e['occ']) for e in entries)} key terms, {len(entries)} names, {len(groups)} groups "
          f"-> {len(reg.concepts)} concepts")
    R.dump("4_registry", {c.id: {"name": c.name, "aliases": c.aliases, "introduced": c.introduced,
                                 "terms": c.terms, "definition": c.definition, "reason": c.reason,
                                 "sources": c.sources} for c in reg.concepts.values()})
