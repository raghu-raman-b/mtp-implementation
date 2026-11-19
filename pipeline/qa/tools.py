"""The question-answering tools over the knowledge layer, and what the model sees of them.

Each tool takes the Knowledge and the arguments the model sent, and returns a ToolResult: the text the model reads
(every fact line carries its ID, lecture and time, so the answer can cite it), a one-line summary for the viewer's
steps (developer view), the fact and segment IDs it showed (only those may be cited), and for the chat screen a
display line ("label", plain words, no IDs) and "detail" (the same in fields: names, counts, lecture numbers; the
fields per tool are in schemas/qa_stream.md). The tool descriptions the model sees are in
prompts/qa_tools.json (written apart, as a prompt); TOOLS checks that they name exactly the tools here.

    check_concept(names)                         a card per name (alias, acronym, plural or close spelling), one call
    fact_lookup(query, rephrasings=[], lecture)  the facts closest to the query and its other wordings
    lecture_dependencies(lecture)                what is needed before a lecture (the lecture graph)
    lecture_overview(lecture)                    a lecture's goal, objectives, segments and concepts
    course_goals()                               the course goals and the lectures that serve each
    course_structure(lecture=None)               the course page (instructor, prerequisites, syllabus) and the lecturers' own statements about the course itself, verbatim
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .knowledge import Knowledge, fmt_time, lecture_key

ROOT = Path(__file__).resolve().parent.parent
TOOLS_FILE = ROOT / "prompts" / "qa_tools.json"

CARD_FACTS = 10          # facts shown on a card (defining facts first, as the card orders them)
CARD_RELATIONS = 10
CARDS_PER_NAME = 3       # a name shared by several concepts shows each card, up to this many
LOOKUP_K = 8             # facts fact_lookup returns
MAX_REPHRASINGS = 4
LOW_SCORE = {"fake": 0.3}   # best score under this: "no close match" (per embedding model)
# Qwen3-Embedding-0.6B with the query instruction, calibrated on nptel_vr (analysis/qa/calibration.json): 38 in-course
# queries 0.63-0.86, 3 partly taught 0.60-0.69, 39 out-of-course 0.21-0.72 (unrelated 0.21-0.48, neighbouring fields
# 0.43-0.72); AUC 0.99. 0.55 is 0.05 under the lowest in-course or partly score and flags 27 of the 39.
LOW_SCORE_DEFAULT = 0.55
UNKNOWN_K = 5            # facts closest to an unknown name, shown with the "unknown" answer
DEP_CONCEPTS = 8         # concepts listed by lecture_dependencies with their definition and up to 2 defining facts
DEP_MIN_USES = 2         # a concept fewer of the lecture's facts are about is "mentioned in passing"
DEP_ASSUMED = 10         # assumed concepts named (those the lecture relies on most)
DEP_INTRODUCED = 12      # concepts the lecture introduces, named (most used first)
STOP = set("a an the of to in on for and or is are was were be been what which who whom how why when where does do "
           "did can could would should will shall i me my we you your it its this that these those there here with "
           "about from by as at into than then please tell explain mean means meant difference between versus vs "
           "between kind kinds type types example examples".split())


@dataclass
class ToolResult:
    text: str
    summary: str
    shown: set = field(default_factory=set)     # fact and segment IDs the text shows
    found: bool | None = None   # False: the course has nothing close (unknown name, no close fact); None: not a search
    label: str = ""             # what was done, for the learner's screen ('Looked up "HMD": definition found, ...')
    detail: dict = field(default_factory=dict)   # the same as fields (schemas/qa_stream.md)


class ToolError(ValueError):
    """Bad arguments: the message goes back to the model as the tool's result."""


# ---------------------------------------------------------------- shared lines
def fact_line(kb: Knowledge, fid: str, extra: str = "") -> str:
    f = kb.facts[fid]
    return f"[{fid}] lecture {f['lecture']}, {fmt_time(f['start'])}{extra}: {f['text']}"


def lecture_ref(kb: Knowledge, k: str) -> str:
    return f'lecture {k} "{kb.lecture_title(k)}"'


def lectures_of(kb: Knowledge, ids) -> list[str]:
    """The lectures of these fact or segment IDs, in course order."""
    ks = {kb.facts[i]["lecture"] if i in kb.facts else i.split("/")[0] for i in ids}
    return [k for k in kb.lectures if k in ks] + sorted(ks - set(kb.lectures))


def in_lectures(ks: list[str], most: int = 6) -> str:
    """"lecture 4" / "lectures 4, 9 and 13" / "lectures 4, 9, 13, 20, 21, 22 and 2 more"."""
    if not ks:
        return ""
    if len(ks) == 1:
        return f"lecture {ks[0]}"
    if len(ks) > most:
        return f"lectures {', '.join(ks[:most])} and {len(ks) - most} more"
    return f"lectures {', '.join(ks[:-1])} and {ks[-1]}"


def known_lecture(kb: Knowledge, raw) -> str:
    if raw is None or str(raw).strip() == "":
        raise ToolError("Give the lecture number, e.g. {\"lecture\": \"4\"}.")
    k = lecture_key(raw)
    if k not in kb.lectures:
        ks = list(kb.lectures)
        raise ToolError(f"There is no lecture {raw!s} in this course. Its lectures are "
                        f"{', '.join(ks[:80])}{' ...' if len(ks) > 80 else ''}.")
    return k


# ---------------------------------------------------------------- check_concept
def where_defined(kb: Knowledge, d: dict) -> tuple[str, float, str]:
    """(lecture, time, ID) of one "defined_in" place: its first defining fact, so that the time the card shows is
    the time the citation shows (a segment's citation shows the segment's start, often minutes earlier)."""
    facts = sorted((f for f in d.get("facts", []) if f in kb.facts), key=lambda f: kb.facts[f]["start"])
    if facts:
        return d["lecture"], kb.facts[facts[0]]["start"], facts[0]
    seg = (kb.lectures.get(d["lecture"]) or {}).get("segments", {}).get(d["segment"]) or {}
    return d["lecture"], seg.get("start", d.get("start", 0)), d["segment"]


def is_defined(c: dict) -> bool:
    """True only for a concept the course defines (the "defined" field); a connecting concept's definition text
    is model-written and is never shown to the answering model or the learner."""
    return bool(c.get("defined")) and bool(c.get("definition"))


def card_text(kb: Knowledge, cid: str, shown: set) -> list[str]:
    c = kb.concepts[cid]
    other = list(dict.fromkeys(c.get("aliases", []) + c.get("acronyms", [])))
    out = [f"CONCEPT {c['name']}" + (f" (also called: {', '.join(other)})" if other else "")]
    if is_defined(c):
        src = c.get("definition_facts") or c.get("defining_facts") or []
        out.append(f"Definition: {c['definition']}" + (f" [built from {', '.join(src)}]" if src else ""))
        shown.update(f for f in src if f in kb.facts)
    else:   # a connecting concept: its model-written definition never leaves the knowledge layer
        out.append("Definition: none (the course uses this term but does not define it; its facts follow).")
    if is_defined(c) and c.get("defined_in"):
        places = [where_defined(kb, d) for d in c["defined_in"]]
        out.append("Defined in: " + "; ".join(f"{lecture_ref(kb, k)} at {fmt_time(t)} [{ref}]" for k, t, ref in places))
        shown.update(ref for _, _, ref in places)
    out.append("Used in lectures: " + ", ".join(c.get("lectures", [])))
    path = (kb.graph.get("concept_paths") or {}).get(cid, {}).get("path") or []
    if len(path) > 1:
        out.append("Lectures that lead up to it, in order: " + " -> ".join(path))
    facts = [f for f in c.get("facts", []) if f in kb.facts]
    if not is_defined(c):       # the facts that speak of it most directly come first
        lead = [f for f in c.get("defining_facts", []) if f in facts]
        facts = lead + [f for f in facts if f not in lead]
    rels = c.get("relations", {})
    rel_lines, rel_facts = [], []
    for direction in ("out", "in"):
        for r in rels.get(direction, []):
            rf = [f for f in (kb.relations.get(r["relation"], {}).get("facts") or []) if f in kb.facts]
            a, b = (c["name"], r["name"]) if direction == "out" else (r["name"], c["name"])
            rel_lines.append(f"{a} -- {r['label']} --> {b}" + (f" [{', '.join(rf)}]" if rf else ""))
            rel_facts += rf
    show = facts[:CARD_FACTS]
    show += [f for f in dict.fromkeys(rel_facts) if f not in show][:CARD_RELATIONS]
    out.append("Facts:")
    out += [fact_line(kb, f) for f in show]
    if len(facts) > CARD_FACTS:
        out.append(f"({len(facts) - CARD_FACTS} more facts not shown; fact_lookup finds them by content)")
    shown.update(show)
    if rel_lines:
        out.append("Relationships:")
        out += rel_lines[:CARD_RELATIONS]
    return out


def one_card(kb: Knowledge, name: str) -> ToolResult:
    """The card of one name (an unknown name: its closest facts), as check_concept shows each name of its list."""
    cids, how, matched = kb.lookup_name(name)
    if not cids:
        sug = kb.suggestions(name)
        text = (f'"{name}" is not the name of a concept in this course (unknown). Call fact_lookup with the '
                f"learner's question in your own words to search the course's facts.")
        if sug:
            text += f" Concept names close to it: {', '.join(sug)} (call check_concept with one of them only if it " \
                    f"is clearly what the learner means)."
        # The facts closest to the name come with the answer, so that a name the course words differently is
        # answered without another round, and a name the course does not teach is seen to be so at once.
        hits = kb.search(list(dict.fromkeys([name, kb.expand_acronyms(name)])), k=UNKNOWN_K)
        low = LOW_SCORE.get(kb.embed_model, LOW_SCORE_DEFAULT)
        best = hits[0][1] if hits else 0.0
        if hits:
            text += f'\nThe facts closest to "{name}", best first (score 0 to 1):\n' + "\n".join(
                fact_line(kb, f, f" (score {s:.2f})") for f, s in hits)
            if best < low:
                text += f"\nNone of these is a close match (best score {best:.2f}): the course may not cover this."
        ks = lectures_of(kb, [f for f, _ in hits])
        close = bool(hits) and best >= low
        label = f'"{name}" is not a concept of the course' + (
            f"; the closest facts are in {in_lectures(ks)}" if close else "; nothing in the course comes close")
        return ToolResult(text, f"unknown name '{name}'" + (f"; close: {', '.join(sug)}" if sug else "")
                          + (f"; closest fact {best:.2f}" + (" (low)" if best < low else "") if hits else ""),
                          {f for f, _ in hits}, found=close, label=label,
                          detail={"name": name, "known": False, "suggestions": sug, "facts": len(hits),
                                  "lectures": ks, "best_score": round(best, 2), "close": close, "lecture": None})
    shown: set = set()
    lines = []
    if how == "close":
        lines.append(f'No concept is named "{name}"; the closest name is "{matched}", shown below.')
    if len(cids) > 1:
        lines.append(f'The name "{matched}" stands for {len(cids)} concepts in this course; each card follows.')
    for cid in cids[:CARDS_PER_NAME]:
        lines += card_text(kb, cid, shown) + [""]
    names = ", ".join(kb.concept_name(c) for c in cids[:CARDS_PER_NAME])
    n_facts = sum(1 for s in shown if '/F' in s)
    summary = f"card of {names}" + (f" (matched '{matched}', {how})" if how != "exact" else "") + \
              f"; {n_facts} facts"
    cards = [{"id": c, "name": kb.concept_name(c), "defined": is_defined(kb.concepts[c]),
              "defined_in": list(dict.fromkeys(d["lecture"] for d in kb.concepts[c].get("defined_in", [])))
              if is_defined(kb.concepts[c]) else []}
             for c in cids[:CARDS_PER_NAME]]
    ks = lectures_of(kb, [s for s in shown if "/F" in s])
    defined = [c["defined"] for c in cards]
    label = f'Looked up "{" / ".join(c["name"] for c in cards)}": ' + (
        "definition found" if all(defined) else "a definition found" if any(defined)
        else "facts found") + (f", {n_facts} facts from {in_lectures(ks)}" if n_facts else "")
    return ToolResult("\n".join(lines).strip(), summary, shown, found=True, label=label,
                      detail={"name": name, "known": True, "matched": matched, "how": how, "concepts": cards,
                              "facts": n_facts, "lectures": ks,
                              "lecture": next((k for c in cards for k in c["defined_in"]), None)
                              or next((k for c in cids[:CARDS_PER_NAME] for k in kb.concepts[c].get("lectures", [])),
                                      None)})


def check_concept(kb: Knowledge, names=None, name=None, **_) -> ToolResult:
    """One card per name, in order, each as one_card gives it, separated by a blank line. Its label names each
    concept with the lecture that defines it ("Concepts loaded: immersion (lecture 4), presence (lecture 4)"; "not in
    the course" for an unknown name). found is False only when every name found nothing close."""
    if isinstance(names, str):
        names = [names]
    names = [str(n).strip() for n in (names if isinstance(names, list) else [name] if name else [])
             if n is not None and str(n).strip()]
    names = list(dict.fromkeys(names))
    if not names:
        raise ToolError("Give the terms as a list, e.g. {\"names\": [\"head-mounted display\", \"field of view\"]}.")
    rs = [one_card(kb, n) for n in names]
    items = [{**r.detail, "label": r.label} for r in rs]
    order = {k: i for i, k in enumerate(kb.lectures)}
    ks = sorted({k for r in rs for k in r.detail.get("lectures", [])}, key=lambda k: order.get(k, 1e9))
    part = lambda d: (f"{d['name']} (not in the course)" if not d["known"]  # noqa: E731
                      else f"{d['concepts'][0]['name']}" + (f" (lecture {d['lecture']})" if d.get("lecture") else ""))
    label = ("Concept loaded: " if len(rs) == 1 else "Concepts loaded: ") + ", ".join(part(d) for d in items)
    shown = set().union(*(r.shown for r in rs))
    found = not all(r.found is False for r in rs)
    return ToolResult("\n\n".join(r.text for r in rs), " | ".join(r.summary for r in rs), shown, found=found,
                      label=label, detail={"names": names, "items": items, "known": sum(d["known"] for d in items),
                                           "facts": sum(d["facts"] for d in items), "lectures": ks})


# ---------------------------------------------------------------- fact_lookup
def keywords(q: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", q)
    return " ".join(w for w in words if w.lower() not in STOP)


def fact_lookup(kb: Knowledge, query: str = "", rephrasings=None, lecture=None, **_) -> ToolResult:
    query = (query or "").strip()
    if not query:
        raise ToolError("Give the query, e.g. {\"query\": \"how does tracking work\"}.")
    if isinstance(rephrasings, str):
        rephrasings = [rephrasings]
    alts = [str(r).strip() for r in (rephrasings or []) if str(r).strip()][:MAX_REPHRASINGS]
    variants = list(dict.fromkeys([query, *alts, kb.expand_acronyms(query), keywords(query)]))
    variants = [v for v in variants if v]
    k = known_lecture(kb, lecture) if lecture not in (None, "") else None
    hits = kb.search(variants, k=LOOKUP_K, lecture=k)
    if not hits:
        return ToolResult("No facts found.", f"no facts for '{query}'", found=False,
                          label=f'Searched the course for "{query}": nothing found',
                          detail={"query": query, "wordings": len(variants), "lecture": k, "facts": 0, "lectures": [],
                                  "best_score": None, "close": False})
    low = LOW_SCORE.get(kb.embed_model, LOW_SCORE_DEFAULT)
    best = hits[0][1]
    lines = [f'Facts closest to "{query}"' + (f" in lecture {k}" if k else "") + ", best first (score 0 to 1):"]
    for fid, s in hits:
        cs = ", ".join(kb.concept_name(c) for c in kb.facts[fid].get("concepts", [])[:4])
        lines.append(fact_line(kb, fid, f" (score {s:.2f}" + (f"; concepts: {cs}" if cs else "") + ")"))
    if best < low:
        lines.append(f"None of these is a close match (best score {best:.2f}): the course may not cover this. "
                     "Use a fact only if it really answers the question.")
    summary = f"{len(hits)} facts for '{query}'" + (f" (+{len(variants) - 1} wordings)" if len(variants) > 1 else "") \
              + f"; best {best:.2f}" + (" (low)" if best < low else "")
    ks = lectures_of(kb, [f for f, _ in hits])
    label = f'Searched the course for "{query}"' + (f" in lecture {k}" if k else "") + \
        (f": {len(hits)} facts from {in_lectures(ks)}" if best >= low else ": nothing close")
    return ToolResult("\n".join(lines), summary, {f for f, _ in hits}, found=best >= low, label=label,
                      detail={"query": query, "wordings": len(variants), "lecture": k, "facts": len(hits),
                              "lectures": ks, "best_score": round(best, 2), "close": best >= low})


# ---------------------------------------------------------------- lecture_dependencies
def lecture_dependencies(kb: Knowledge, lecture=None, **_) -> ToolResult:
    """What lecture k needs, from the concepts it relies on rather than from every concept it names.

    The lecture graph links K -> L when L names any concept K defines, so one passing mention of a concept makes K a
    prerequisite, and the graph's met_again list is in concept order. Here the concepts lecture k takes from earlier
    lectures are ranked by how many of its facts are about them (kb.concept_uses): those with at least DEP_MIN_USES
    facts are what it relies on (shown with definition and defining facts, most used first); hub concepts (used
    across the course) are named apart; the rest are named as mentioned in passing. The lectures to revise are where
    the relied-on concepts are first defined, ranked by those uses.
    """
    k = known_lecture(kb, lecture)
    kinds = (kb.graph.get("concept_kinds") or {}).get(k) or kb.lectures[k].get("concepts", {})
    uses = kb.concept_uses(k)
    rank = lambda ids: sorted(ids, key=lambda c: (-uses.get(c, 0), kb.concept_name(c).lower()))  # noqa: E731
    again = rank(kinds.get("met_again", []))
    hubs = [c for c in again if kb.is_hub(c) and uses.get(c, 0) >= DEP_MIN_USES]
    key = [c for c in again if not kb.is_hub(c) and uses.get(c, 0) >= DEP_MIN_USES]
    passing = [c for c in again if uses.get(c, 0) < DEP_MIN_USES]
    first = lambda c: (kb.concepts.get(c) or {}).get("first_defined") or \
        ((kb.graph.get("concept_paths") or {}).get(c) or {}).get("first_defined")  # noqa: E731
    order = {j: i for i, j in enumerate(kb.lectures)}
    earlier = lambda c: [j for j in ((kb.graph.get("concepts") or {}).get(c) or {}).get("defined_in", [])  # noqa: E731
                         if order.get(j, 1e9) < order[k]]
    names = lambda ids: ", ".join(kb.concept_name(c) for c in ids)  # noqa: E731
    shown: set = set()
    out = [f"BEFORE {lecture_ref(kb, k)}"]
    if key:
        out.append(f"Concepts from earlier lectures that lecture {k} relies on, most used first (uses: how many of "
                   f"its facts are about the concept):")
        for c in key[:DEP_CONCEPTS]:
            C = kb.concepts.get(c, {})
            also = [j for j in earlier(c) if j != first(c)]
            out.append(f"- {C.get('name', c)} ({uses[c]} uses; {'first defined' if is_defined(C) else 'first met'} in lecture {first(c)}"
                       + (f", also in {', '.join(also)}" if also else "") + ")"
                       + (": " + C["definition"] if is_defined(C) else ""))
            dfs = [f for f in C.get("defining_facts", []) if f in kb.facts]
            if not is_defined(C):   # no definition to show: its facts stand in, defining ones first
                dfs += [f for f in C.get("facts", []) if f in kb.facts and f not in dfs]
            for f in dfs[:2]:
                out.append("    " + fact_line(kb, f))
                shown.add(f)
        if len(key) > DEP_CONCEPTS:
            out.append(f"  (also relied on: {names(key[DEP_CONCEPTS:])})")
        score: dict[str, int] = {}
        carried: dict[str, list] = {}
        for c in key:
            j = first(c)
            if j:
                score[j] = score.get(j, 0) + uses[c]
                carried.setdefault(j, []).append(c)
        revise = sorted(score, key=lambda j: (-score[j], order.get(j, 0)))
        out.append("Lectures to revise first, by how much lecture " + k + " relies on what they teach: " + "; ".join(
            f"{lecture_ref(kb, j)} ({names(carried[j])})" for j in revise))
    else:
        revise = []
        out.append(f"Lecture {k} relies on no concept from an earlier lecture (none of its facts is about one more "
                   f"than once).")
    if hubs:
        out.append("General concepts of the course it also uses (taught early, used throughout): " + ", ".join(
            f"{kb.concept_name(c)} (lecture {first(c)})" for c in hubs))
    if passing:
        out.append("Concepts from earlier lectures it only mentions in passing (not needed beforehand): "
                   + names(passing))
    assumed = [c for c in rank(kinds.get("assumed", [])) if uses.get(c, 0) >= DEP_MIN_USES]
    if assumed:
        rest = len(kinds.get("assumed", [])) - min(len(assumed), DEP_ASSUMED)
        out.append(f"Concepts lecture {k} relies on that the course never defines (assumed knowledge): "
                   + names(assumed[:DEP_ASSUMED]) + (f" (and {rest} more it names)" if rest > 0 else ""))
    if kinds.get("introduced"):
        intro = rank(kinds["introduced"])
        out.append(f"Concepts lecture {k} itself introduces (most used first): " + names(intro[:DEP_INTRODUCED])
                   + (f" (and {len(intro) - DEP_INTRODUCED} more)" if len(intro) > DEP_INTRODUCED else ""))
    summary = f"lecture {k}: revise {', '.join(revise) or 'none'}; relies on {len(key)} earlier concepts, " \
              f"{len(hubs)} general, {len(passing)} in passing, {len(assumed)} assumed"
    label = f"Checked what lecture {k} builds on: " + (
        f"revise {in_lectures(revise, 8)}" if revise else "nothing from earlier lectures")
    return ToolResult("\n".join(out), summary, shown, found=True, label=label,
                      detail={"lecture": k, "title": kb.lecture_title(k), "revise": revise,
                              "relies_on": [kb.concept_name(c) for c in key[:DEP_CONCEPTS]],
                              "general": [kb.concept_name(c) for c in hubs], "in_passing": len(passing),
                              "assumed": len(assumed)})


# ---------------------------------------------------------------- lecture_overview
def lecture_overview(kb: Knowledge, lecture=None, **_) -> ToolResult:
    k = known_lecture(kb, lecture)
    L = kb.lectures[k]
    out = [f"OVERVIEW OF {lecture_ref(kb, k)}"]
    if L.get("goal"):
        out.append(f"Goal: {L['goal']['goal']}")
        if L["goal"].get("achieves"):
            out.append(f"Achieves: {L['goal']['achieves']}")
    if L.get("objectives"):
        out.append("Objectives:")
        out += [f"- {o['goal']} [{', '.join(o['segments'])}]" for o in L["objectives"]]
    out.append("Segments, in order:")
    shown = set()
    for sid, s in L.get("segments", {}).items():
        out.append(f"[{sid}] {fmt_time(s['start'])}-{fmt_time(s['end'])}: {s.get('subgoal', '')}")
        shown.add(sid)
    names = lambda ids: ", ".join(kb.concept_name(c) for c in ids)  # noqa: E731
    kinds = L.get("concepts", {})
    for kind, label in (("introduced", "Concepts it introduces"), ("met_again", "Concepts from earlier lectures"),
                        ("defined_later", "Concepts it uses that a later lecture defines"),
                        ("assumed", "Concepts it assumes (never defined in the course)")):
        if kinds.get(kind):
            out.append(f"{label}: {names(kinds[kind])}")
    if L.get("course_goals"):
        cg = kb.goals.get("course_goals", {})
        out.append("Course goals it serves: " + "; ".join(f"{g}: {cg.get(g, {}).get('goal', '')}"
                                                         for g in L["course_goals"]))
    pre = L.get("prerequisites") or {}
    if pre.get("direct"):
        out.append("Direct prerequisites: " + ", ".join(f"lecture {j}" for j in pre["direct"]))
    summary = f"lecture {k}: {len(L.get('segments', {}))} segments, {len(L.get('objectives', []))} objectives, " \
              f"{len(kinds.get('introduced', []))} concepts introduced"
    n_seg = len(L.get("segments", {}))
    return ToolResult("\n".join(out), summary, shown, found=True,
                      label=f'Read the outline of lecture {k} "{kb.lecture_title(k)}": {n_seg} parts',
                      detail={"lecture": k, "title": kb.lecture_title(k), "segments": n_seg,
                              "objectives": len(L.get("objectives", [])),
                              "introduced": len(kinds.get("introduced", []))})


# ---------------------------------------------------------------- course_goals
def course_goals(kb: Knowledge, **_) -> ToolResult:
    cg = kb.goals.get("course_goals", {})
    out = [f'COURSE "{kb.title}" ({len(kb.lectures)} lectures)']
    if not cg:
        out.append("No course goals are written.")
    for gid, g in cg.items():
        out.append(f"{gid}: {g['goal']}" + (f" Achieves: {g['achieves']}" if g.get("achieves") else ""))
        out.append("   Lectures: " + "; ".join(f"{j} \"{kb.lecture_title(j)}\"" for j in g.get("lectures", [])))
    return ToolResult("\n".join(out), f"{len(cg)} course goals", found=True, label=f"Read the {len(cg)} course goals",
                      detail={"goals": len(cg)})


# ---------------------------------------------------------------- course_structure
def course_page(kb: Knowledge) -> dict | None:
    """The official course page (input/<course>/input/course.json, scripts/course_meta.py), or None when missing."""
    from scripts import course_meta
    try:
        d = course_meta.load(kb.course)
    except (OSError, ValueError, KeyError):
        return None
    return d if isinstance(d, dict) else None


def course_page_items(kb: Knowledge) -> list[dict]:
    """The course page as citable items [{"id": "CP01", "label", "text"}]: CP01 instructor, CP02 prerequisites,
    CP03 intended audience, CP04 outline, CP11, CP12, ... one per syllabus entry (in order). Empty without the file."""
    d = course_page(kb)
    if not d:
        return []
    items = []
    ins = d.get("instructor")
    if isinstance(ins, dict) and ins.get("name"):
        txt = ins["name"] + (f", {ins['department']}" if ins.get("department") else "") \
            + (f", {d['institution']}" if d.get("institution") else "") + "."
        if ins.get("about"):
            txt += " " + ins["about"].strip()
        items.append({"id": "CP01", "label": "Instructor", "text": txt})
    for cid, key, label in (("CP02", "prerequisites", "Prerequisites"), ("CP03", "intended_audience", "Intended audience"),
                            ("CP04", "outline", "Course outline")):
        if str(d.get(key) or "").strip():
            items.append({"id": cid, "label": label, "text": str(d[key]).strip()})
    for i, w in enumerate(d.get("syllabus") or []):
        if not isinstance(w, dict) or not w.get("topics"):
            continue
        head = (f"Week {w['week']}" if w.get("week") is not None else f"Part {i + 1}") + (f" \u2014 {w['theme']}" if w.get("theme") else "")
        items.append({"id": f"CP{11 + i}", "label": head, "text": "; ".join(w["topics"]) + "."})
    return items


def course_structure(kb: Knowledge, lecture=None, **_) -> ToolResult:
    """The official course page (instructor, prerequisites, audience, weekly syllabus; IDs CP01...) and the lecturers'
    own statements about the course itself (stage 4f), verbatim, each with its ID (CS0001: the answer cites it like a
    fact), lecture and start time; only one lecture's statements when `lecture` is given (the course page is then
    left out). Either part may be missing; both missing: not available."""
    st = kb.course_structure()
    k = lecture_key(lecture) if lecture not in (None, "") else None
    page = [] if k is not None else course_page_items(kb)
    if st is None and not course_page_items(kb):
        return ToolResult("The course structure is not available.", "course structure not available", found=False,
                          label="The course structure is not available",
                          detail={"statements": 0, "lectures": [], "lecture": None, "available": False})
    st = st or []
    if k is not None:
        st = [x for x in st if str(x.get("lecture")) == k]
    have = {str(x["lecture"]) for x in st}
    ks = [j for j in kb.lectures if j in have] + sorted(have - set(kb.lectures))
    if not st and not page:
        return ToolResult("The lecturers say nothing about the course itself" + (f" in lecture {k}" if k else "")
                          + ".", "no statements", found=False,
                          label="The lecturers say nothing about the course structure" + (f" in lecture {k}" if k else ""),
                          detail={"statements": 0, "lectures": [], "lecture": k, "available": True})
    out = []
    if page:
        d = course_page(kb)
        out.append("OFFICIAL COURSE PAGE (" + ", ".join(str(d[x]) for x in ("title", "platform", "institution") if d.get(x))
                   + "), cite the ID:")
        out += [f"[{x['id']}] {x['label']}: {x['text']}" for x in page]
        out.append("")
    if st:
        out.append("WHAT THE LECTURERS SAY ABOUT THE COURSE ITSELF" + (f" (lecture {k})" if k else "")
                   + ", in their words (cite the ID):")
        out += [f"[{x['id']}] lecture {x['lecture']}, {fmt_time(x['start'])}: {x['text']}" for x in st]
    parts = ([f"{len(page)} course page items"] if page else []) + ([f"{len(st)} statements from {in_lectures(ks)}"] if st else [])
    return ToolResult("\n".join(out), ", ".join(parts), {x["id"] for x in st} | {x["id"] for x in page}, found=True,
                      label="Course structure read: " + " and ".join(parts),
                      detail={"statements": len(st), "lectures": ks, "lecture": k, "available": True,
                              "course_page": len(page)})


FUNCS = {"check_concept": check_concept, "fact_lookup": fact_lookup, "lecture_dependencies": lecture_dependencies,
         "lecture_overview": lecture_overview, "course_goals": course_goals,
         "course_structure": course_structure}


def tool_specs(path: Path = TOOLS_FILE) -> list[dict]:
    """The OpenAI tools list from prompts/qa_tools.json (its names must be exactly the tools above)."""
    specs = json.loads(Path(path).read_text(encoding="utf-8"))
    names = [s["function"]["name"] for s in specs]
    if sorted(names) != sorted(FUNCS):
        raise ValueError(f"{path} names {names}, the code has {sorted(FUNCS)}")
    return specs


def run_tool(kb: Knowledge, name: str, args: dict) -> ToolResult:
    """Run one tool; a bad name or bad arguments come back as a result the model can read and correct."""
    oops = "A lookup went wrong; trying again"
    if name not in FUNCS:
        return ToolResult(f"There is no tool {name!r}. The tools are: {', '.join(FUNCS)}.", f"unknown tool {name}",
                          label=oops, detail={"error": f"unknown tool {name}"})
    if not isinstance(args, dict):
        return ToolResult("The arguments must be a JSON object.", "bad arguments", label=oops,
                          detail={"error": "bad arguments"})
    try:
        return FUNCS[name](kb, **args)
    except ToolError as e:
        return ToolResult(str(e), f"error: {e}", label=oops, detail={"error": str(e)})
