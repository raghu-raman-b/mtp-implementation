"""Stage 4: course knowledge state.

1. Canonicalize terms against the registry: normalized name / alias match, then embedding similarity
   (high band = same concept, middle band = yes/no LLM call, below = new concept).
2. Extract typed edges, one LLM call per lecture.
3. Snapshot state[k] for every lecture k: concepts, mentions, definitions and edges as of lecture k.

The LLM calls of steps 1 and 2 are batched over the whole course; the registry itself is then built by code,
walking the lectures in order, so nothing in state[k] depends on a later lecture.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

import numpy as np

from . import prompts as P
from . import validate as V
from .context import Lec, Run
from .embed import embed
from .llm import Call

HIGH, MID = 0.93, 0.78     # cosine bands for same / ask / new
MAX_LECTURE_CONCEPTS, MAX_EARLIER = 30, 15
RELATIONS = ["prerequisite_of", "part_of", "example_of", "contrasts_with", "leads_to", "used_in"]


def norm(name: str) -> str:
    t = re.sub(r"[-_/]+", " ", name.lower())
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    words = []
    for w in t.split():
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
        words.append(w)
    return " ".join(words)


def split_alias(name: str) -> tuple[str, str | None]:
    """'Augmented Reality (AR)' -> ('Augmented Reality', 'AR'); 'XR (Extended Reality)' -> ('Extended Reality', 'XR')."""
    m = re.match(r"^\s*(.+?)\s*\(([^)]+)\)\s*$", name)
    if not m:
        return name.strip(), None
    a, b = m.group(1).strip(), m.group(2).strip()
    if is_acronym(b):
        return a, b
    if is_acronym(a):
        return b, a
    return name.strip(), None  # e.g. "X (in XR)": not an alias


def is_acronym(name: str) -> bool:
    t = name.replace(".", "").strip()
    return 2 <= len(t) <= 6 and t.isalnum() and sum(c.isupper() for c in t) >= 2 and " " not in t


def initials(name: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", name) if w.lower() not in {"of", "the", "and", "a", "an"}).lower()


def same_by_rule(a: "Group", b: "Group") -> bool:
    """Abbreviation rules: shared alias, or an acronym that spells the other name's initials."""
    if a.norms & b.norms:
        return True
    for x, y in ((a, b), (b, a)):
        for n in x.names:
            if is_acronym(n) and any(initials(m) == n.lower().replace(".", "") and len(m.split()) >= 2 for m in y.names):
                return True
    return False


@dataclass
class Group:
    """All occurrences of one normalized term within one lecture."""
    idx: int
    pos: int                      # lecture position in the run (1-based)
    lecture_id: str
    norm: str
    names: list[str]
    definition: str | None
    occs: list[dict]              # {segment_id, sentence_ids, defined}
    emb: np.ndarray | None = None
    norms: set = field(default_factory=set)   # normalized name plus aliases ("(AR)")
    definitions: list = field(default_factory=list)  # every definition given in this lecture, in order


@dataclass
class Concept:
    id: str
    name: str
    aliases: list[str]
    definitions: list[tuple]      # (pos, lecture_id, text)
    introduced: dict
    intro_pos: int
    mentions: list[dict]          # {lecture_id, segment_id, sentence_ids, pos}
    emb: np.ndarray
    dropped: bool = False         # every definition was rejected by the judge: not a concept worth learning


@dataclass
class CourseState:
    concepts: dict[str, Concept] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)          # {src, rel, dst, label, evidence, pos}
    pos_of: dict[str, int] = field(default_factory=dict)     # lecture_id -> position
    snapshots: dict[int, dict] = field(default_factory=dict)

    def snapshot(self, k: int) -> dict:
        """state[k]: everything known after lecture k (k = 0 is the empty state before the first lecture)."""
        if k in self.snapshots:
            return self.snapshots[k]
        concepts = {}
        for c in self.concepts.values():
            if c.intro_pos > k or c.dropped:
                continue
            # the definition shown: from the earliest lecture, one that passes the definition checks, about 25 words
            defs = sorted((d for d in c.definitions if d[0] <= k),
                          key=lambda d: (d[0], bool(V.check_definition(c.name, d[2], "")), abs(len(d[2].split()) - 25)))
            mentions = [{kk: v for kk, v in m.items() if kk != "pos"} for m in c.mentions if m["pos"] <= k]
            concepts[c.id] = {"id": c.id, "name": c.name, "aliases": c.aliases,
                              "definition": defs[0][2] if defs else None, "introduced": c.introduced,
                              "intro_pos": c.intro_pos, "mentions": mentions}
        edges = [e for e in self.edges if e["pos"] <= k and e["src"] in concepts and e["dst"] in concepts]
        degree = {cid: 0 for cid in concepts}
        for e in edges:
            for end in (e["src"], e["dst"]):
                if end in degree:
                    degree[end] += 1
        raw = {}
        for cid, c in concepts.items():
            segs = {(m["lecture_id"], m["segment_id"]) for m in c["mentions"]}
            raw[cid] = math.log1p(len(segs)) + (1.0 if c["definition"] else 0.0) + 0.5 * math.log1p(degree[cid])
        top = max(raw.values(), default=1.0) or 1.0
        for cid, c in concepts.items():
            c["salience"] = round(raw[cid] / top, 3)
            c["degree"] = degree[cid]
        snap = {"k": k, "concepts": concepts, "edges": edges}
        self.snapshots[k] = snap
        return snap


def _occurrences(lec: Lec):
    """Key terms (defined) and used concepts (not defined), in segment order."""
    out = []
    for seg in lec.segments:
        for t in seg.key_terms:
            out.append((t["term"], t["definition"], seg.id, t["sentence_ids"], True))
        for u in seg.used_concepts:
            sids = [s.id for s in lec.sentences[seg.a:seg.b + 1] if V.fuzzy_in(u, s.text)][:3]
            out.append((u, None, seg.id, sids, False))
    return out


def _groups(R: Run) -> list[Group]:
    groups: list[Group] = []
    for pos, lec in enumerate(R.lectures, 1):
        local: dict[str, Group] = {}
        for raw, definition, sid, sids, defined in _occurrences(lec):
            name, alias = split_alias(raw)
            n = norm(name)
            if not n or len(n) < 2:
                continue
            g = local.get(n)
            if g is None:
                g = local[n] = Group(len(groups), pos, lec.id, n, [], None, [])
                groups.append(g)
            g.norms.add(n)
            for nm in (name, alias):
                if nm and nm not in g.names:
                    g.names.insert(0, nm) if (defined and not g.definition and nm == name) else g.names.append(nm)
            if alias:
                g.norms.add(norm(alias))
            if defined and not g.definition:
                g.definition = definition
            if defined and definition not in g.definitions:
                g.definitions.append(definition)
            g.occs.append({"segment_id": sid, "sentence_ids": sids, "defined": defined})
    if groups:
        embs = embed([g.names[0] for g in groups])
        for g, e in zip(groups, embs):
            g.emb = e
    return groups


def _canonicalize(R: Run, groups: list[Group]) -> dict[int, int]:
    """Return a parent map group -> earlier group it is the same concept as (or itself)."""
    if not groups:
        return {}
    E = np.stack([g.emb for g in groups])
    sims = E @ E.T
    first_by_norm: dict[str, int] = {}
    decision: dict[int, tuple] = {}   # g -> ("exact"|"high"|"ask", [candidates])
    asks = []
    for g in groups:
        if g.norm in first_by_norm:
            decision[g.idx] = ("exact", [first_by_norm[g.norm]])
            continue
        first_by_norm[g.norm] = g.idx
        rule = [h for h in range(g.idx) if same_by_rule(g, groups[h])]
        if rule:  # alias or acronym: same concept, no LLM call needed
            decision[g.idx] = ("exact", rule[:1])
            continue
        earlier = [(sims[g.idx, h], h) for h in range(g.idx) if groups[h].norm != g.norm]
        earlier.sort(reverse=True)
        high = [h for s, h in earlier if s >= HIGH]
        if high:
            decision[g.idx] = ("high", high[:1])
            continue
        mid = [h for s, h in earlier[:3] if MID <= s < HIGH]
        if mid:
            decision[g.idx] = ("ask", mid)
            for h in mid:
                asks.append((g.idx, h))

    def where(gr: Group):
        return f"lecture {gr.lecture_id}"

    calls = []
    for gi, hi in asks:
        g, h = groups[gi], groups[hi]
        prompt = P.SAME_CONCEPT[2].format(a=h.names[0], a_where=where(h), a_def=h.definition or "(not defined)",
                                          b=g.names[0], b_where=where(g), b_def=g.definition or "(not defined)")
        calls.append(Call(key=f"{g.lecture_id}/same/{h.names[0]}|{g.names[0]}", lecture_id=g.lecture_id,
                          prompt=prompt, schema={"type": "object", "additionalProperties": False,
                                                 "required": ["same"], "properties": {"same": {"type": "boolean"}}},
                          prompt_id=P.SAME_CONCEPT[0], prompt_version=P.SAME_CONCEPT[1], max_tokens=4096,
                          required=False, ctx={"pair": (gi, hi)}))
    same = set()
    for o in R.llm.run("stage4_canonicalize", calls, f"same-concept checks ({len(calls)})"):
        R.record(o, "stage4_canonicalize")
        if o.parsed and o.parsed.get("same"):
            same.add(o.call.ctx["pair"])

    parent = {}

    def root(i):
        while parent.get(i, i) != i:
            i = parent[i]
        return i

    for g in groups:  # in course order
        kind, cands = decision.get(g.idx, (None, []))
        if kind == "ask":
            cands = [h for h in cands if (g.idx, h) in same]
        cands = [h for h in cands if root(h) != -1]
        if cands:
            parent[g.idx] = root(cands[0])
        elif g.definition:
            parent[g.idx] = g.idx
        else:
            parent[g.idx] = -1  # a concept that is only used, never defined, joins an existing one or is dropped
    return {g.idx: root(g.idx) for g in groups}


def _build_registry(R: Run, groups: list[Group], roots: dict[int, int]) -> CourseState:
    st = CourseState(pos_of={l.id: p for p, l in enumerate(R.lectures, 1)})
    cid_of_root: dict[int, str] = {}
    for g in groups:
        r = roots[g.idx]
        if r == -1:
            continue
        lec = R.lec(g.lecture_id)
        if r not in cid_of_root:
            cid = f"C{len(cid_of_root) + 1:03d}"
            cid_of_root[r] = cid
            occ = next((o for o in g.occs if o["defined"]), g.occs[0])
            seg = lec.seg(occ["segment_id"])
            sid = occ["sentence_ids"][0] if occ["sentence_ids"] else seg.a
            st.concepts[cid] = Concept(cid, V.display_name(g.names[0]), [], [], {
                "lecture_id": lec.id, "segment_id": seg.id, "sentence_id": sid, "t": lec.sentences[sid].start},
                g.pos, [], g.emb)
        c = st.concepts[cid_of_root[r]]
        for n in g.names:
            if n != c.name and n not in c.aliases and norm(n) != norm(c.name):
                c.aliases.append(n)
        for d in g.definitions:  # all of them: if the judge rejects one, another can take its place
            c.definitions.append((g.pos, g.lecture_id, d))
        for o in g.occs:
            c.mentions.append({"lecture_id": g.lecture_id, "segment_id": o["segment_id"],
                               "sentence_ids": o["sentence_ids"], "pos": g.pos})
            seg = lec.seg(o["segment_id"])
            if c.id not in seg.concept_ids:
                seg.concept_ids.append(c.id)
        for seg in lec.segments:
            for t in seg.key_terms:
                if norm(split_alias(t["term"])[0]) == g.norm or norm(t["term"]) == g.norm:
                    t["concept_id"] = c.id
    return st


def _edges(R: Run, st: CourseState):
    calls = []
    for pos, lec in enumerate(R.lectures, 1):
        here = [c for c in st.concepts.values() if any(m["lecture_id"] == lec.id for m in c.mentions)]
        if len(here) < 2:
            continue
        here.sort(key=lambda c: (-any(d[1] == lec.id for d in c.definitions),
                                 -len({m["segment_id"] for m in c.mentions if m["lecture_id"] == lec.id})))
        here = here[:MAX_LECTURE_CONCEPTS]
        here_ids = {c.id for c in here}
        before = [c for c in st.concepts.values() if c.intro_pos < pos and c.id not in here_ids]
        if before:
            H = np.stack([c.emb for c in here])
            here_segs = {(m["lecture_id"], m["segment_id"]) for c in here for m in c.mentions if m["pos"] < pos}
            scored = []
            for c in before:
                co = len({(m["lecture_id"], m["segment_id"]) for m in c.mentions if m["pos"] < pos} & here_segs)
                scored.append((float((H @ c.emb).max()) + 0.05 * min(co, 4), c))
            scored.sort(key=lambda t: -t[0])
            before = [c for _, c in scored[:MAX_EARLIER]]

        def line(c, earlier=False):
            defs = [d for d in c.definitions if d[0] <= pos]
            d = defs[0][2] if defs else "(no definition given)"
            return f"- {c.name}" + (f" (lecture {c.introduced['lecture_id']})" if earlier else "") + f": {d}"

        evidence = []
        for seg in lec.segments:
            evidence += [f"[{', '.join(map(str, kp['sentence_ids']))}] {kp['text']}" for kp in seg.key_points]
            evidence += [f"[{', '.join(map(str, t['sentence_ids']))}] {t['term']}: {t['definition']}"
                         for t in seg.key_terms]
        names = [c.name for c in here] + [c.name for c in before]
        here_names = {c.name for c in here}
        n_sent = len(lec.sentences)
        schema = {"type": "object", "additionalProperties": False, "required": ["edges"], "properties": {
            "edges": {"type": "array", "maxItems": 20, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["src", "rel", "dst", "label", "evidence"], "properties": {
                    "src": {"type": "string", "enum": names}, "rel": {"type": "string", "enum": RELATIONS},
                    "dst": {"type": "string", "enum": names}, "label": {"type": "string", "maxLength": 60},
                    "evidence": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "integer"}}}}}}}

        def bad(e, here_names=here_names, n_sent=n_sent):
            errs = []
            if len(e["label"].split()) > 6:
                errs.append(f'edge {e["src"]} -> {e["dst"]}: the label "{e["label"]}" is too long; use 2 to 5 words')
            errs += V.check_label(e["label"], f'edge {e["src"]} -> {e["dst"]}')
            if e["src"] == e["dst"]:
                errs.append(f'edge {e["src"]} -> {e["dst"]} links a concept to itself')
            if e["src"] not in here_names and e["dst"] not in here_names:
                errs.append(f'edge {e["src"]} -> {e["dst"]}: at least one end must be a concept from this lecture')
            if any(not 0 <= i < n_sent for i in e["evidence"]):
                errs.append(f'edge {e["src"]} -> {e["dst"]} cites sentence IDs outside this lecture')
            return errs

        prompt = P.EDGES[2].format(role=P.ROLE, course=R.course.title, lecture_id=lec.id, title=lec.inp.title,
                                   concepts="\n".join(line(c) for c in here),
                                   earlier="\n".join(line(c, True) for c in before) or "(none)",
                                   evidence="\n".join(evidence))
        calls.append(Call(key=f"{lec.id}/edges", lecture_id=lec.id, prompt=prompt, schema=schema,
                          prompt_id=P.EDGES[0], prompt_version=P.EDGES[1], required=False,
                          check=lambda x, bad=bad: [m for e in x["edges"] for m in bad(e)],
                          ctx={"pos": pos, "bad": bad, "by_name": {c.name: c.id for c in here + before}}))
    seen = set()
    for o in sorted(R.llm.run("stage4_edges", calls, "edge extraction"), key=lambda o: o.call.ctx["pos"]):
        R.record(o, "stage4_edges", f"{o.call.lecture_id}.edges")
        if not o.parsed:
            continue
        kept = 0
        for e in o.parsed["edges"]:
            if o.call.ctx["bad"](e):
                continue  # optional items: invalid edges are dropped
            by = o.call.ctx["by_name"]
            src, dst = by[e["src"]], by[e["dst"]]
            key = (src, e["rel"], dst) if e["rel"] != "contrasts_with" else (min(src, dst), e["rel"], max(src, dst))
            if key in seen:
                continue
            seen.add(key)
            st.edges.append({"src": src, "rel": e["rel"], "dst": dst, "label": e["label"].strip(),
                             "evidence": {"lecture_id": o.call.lecture_id, "sentence_ids": sorted(set(e["evidence"]))},
                             "pos": o.call.ctx["pos"]})
            kept += 1
        R.log(f"  {o.call.lecture_id}: {kept} edges")


def run(R: Run):
    groups = _groups(R)
    roots = _canonicalize(R, groups)
    st = _build_registry(R, groups, roots)
    R.log(f"  {len(groups)} term groups -> {len(st.concepts)} concepts")
    _edges(R, st)
    R.state = st
    sdir = R.out / "state"
    sdir.mkdir(parents=True, exist_ok=True)
    for pos, lec in enumerate(R.lectures, 1):
        snap = st.snapshot(pos)
        (sdir / f"state_{lec.id}.json").write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
    st.snapshot(0)
