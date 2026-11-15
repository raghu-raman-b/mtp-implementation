"""The question-answering tools over the knowledge layer, and what the model sees of them.

Each tool takes the Knowledge and the arguments the model sent, and returns a ToolResult: the text the model reads
(every fact line carries its ID, lecture and time, so the answer can cite it), a one-line summary for the viewer's
steps, and the fact and segment IDs it showed (only those may be cited). The tool descriptions the model sees are in
prompts/qa_tools.json (written apart, as a prompt); TOOLS checks that they name exactly the tools here.

    check_concept(name)                          a concept's card, by name, alias, acronym, plural or a close spelling
    fact_lookup(query, rephrasings=[], lecture)  the facts closest to the query and its other wordings
    lecture_dependencies(lecture)                what is needed before a lecture (the lecture graph)
    lecture_overview(lecture)                    a lecture's goal, objectives, segments and concepts
    course_goals()                               the course goals and the lectures that serve each
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


class ToolError(ValueError):
    """Bad arguments: the message goes back to the model as the tool's result."""


# ---------------------------------------------------------------- shared lines
def fact_line(kb: Knowledge, fid: str, extra: str = "") -> str:
    f = kb.facts[fid]
    return f"[{fid}] lecture {f['lecture']}, {fmt_time(f['start'])}{extra}: {f['text']}"


def lecture_ref(kb: Knowledge, k: str) -> str:
    return f'lecture {k} "{kb.lecture_title(k)}"'


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


def card_text(kb: Knowledge, cid: str, shown: set) -> list[str]:
    c = kb.concepts[cid]
    other = list(dict.fromkeys(c.get("aliases", []) + c.get("acronyms", [])))
    out = [f"CONCEPT {c['name']}" + (f" (also called: {', '.join(other)})" if other else "")]
    if c.get("definition"):
        src = c.get("definition_facts") or c.get("defining_facts") or []
        out.append(f"Definition: {c['definition']}" + (f" [built from {', '.join(src)}]" if src else ""))
        shown.update(f for f in src if f in kb.facts)
    else:
        out.append("Definition: none (the course uses this term but does not define it).")
    if c.get("defined_in"):
        places = [where_defined(kb, d) for d in c["defined_in"]]
        out.append("Defined in: " + "; ".join(f"{lecture_ref(kb, k)} at {fmt_time(t)} [{ref}]" for k, t, ref in places))
        shown.update(ref for _, _, ref in places)
    out.append("Used in lectures: " + ", ".join(c.get("lectures", [])))
    path = (kb.graph.get("concept_paths") or {}).get(cid, {}).get("path") or []
    if len(path) > 1:
        out.append("Lectures that lead up to it, in order: " + " -> ".join(path))
    facts = [f for f in c.get("facts", []) if f in kb.facts]
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


def check_concept(kb: Knowledge, name: str = "", **_) -> ToolResult:
    name = (name or "").strip()
    if not name:
        raise ToolError("Give the concept's name, e.g. {\"name\": \"head-mounted display\"}.")
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
        return ToolResult(text, f"unknown name '{name}'" + (f"; close: {', '.join(sug)}" if sug else "")
                          + (f"; closest fact {best:.2f}" + (" (low)" if best < low else "") if hits else ""),
                          {f for f, _ in hits}, found=bool(hits) and best >= low)
    shown: set = set()
    lines = []
    if how == "close":
        lines.append(f'No concept is named "{name}"; the closest name is "{matched}", shown below.')
    if len(cids) > 1:
        lines.append(f'The name "{matched}" stands for {len(cids)} concepts in this course; each card follows.')
    for cid in cids[:CARDS_PER_NAME]:
        lines += card_text(kb, cid, shown) + [""]
    names = ", ".join(kb.concept_name(c) for c in cids[:CARDS_PER_NAME])
    summary = f"card of {names}" + (f" (matched '{matched}', {how})" if how != "exact" else "") + \
              f"; {sum(1 for s in shown if '/F' in s)} facts"
    return ToolResult("\n".join(lines).strip(), summary, shown, found=True)


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
        return ToolResult("No facts found.", f"no facts for '{query}'", found=False)
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
    return ToolResult("\n".join(lines), summary, {f for f, _ in hits}, found=best >= low)


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
            out.append(f"- {C.get('name', c)} ({uses[c]} uses; first defined in lecture {first(c)}"
                       + (f", also in {', '.join(also)}" if also else "") + "): "
                       + (C.get("definition") or "(no definition written)"))
            for f in [f for f in C.get("defining_facts", []) if f in kb.facts][:2]:
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
    return ToolResult("\n".join(out), summary, shown, found=True)


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
    return ToolResult("\n".join(out), summary, shown, found=True)


# ---------------------------------------------------------------- course_goals
def course_goals(kb: Knowledge, **_) -> ToolResult:
    cg = kb.goals.get("course_goals", {})
    out = [f'COURSE "{kb.title}" ({len(kb.lectures)} lectures)']
    if not cg:
        out.append("No course goals are written.")
    for gid, g in cg.items():
        out.append(f"{gid}: {g['goal']}" + (f" Achieves: {g['achieves']}" if g.get("achieves") else ""))
        out.append("   Lectures: " + "; ".join(f"{j} \"{kb.lecture_title(j)}\"" for j in g.get("lectures", [])))
    return ToolResult("\n".join(out), f"{len(cg)} course goals", found=True)


FUNCS = {"check_concept": check_concept, "fact_lookup": fact_lookup, "lecture_dependencies": lecture_dependencies,
         "lecture_overview": lecture_overview, "course_goals": course_goals}


def tool_specs(path: Path = TOOLS_FILE) -> list[dict]:
    """The OpenAI tools list from prompts/qa_tools.json (its names must be exactly the tools above)."""
    specs = json.loads(Path(path).read_text())
    names = [s["function"]["name"] for s in specs]
    if sorted(names) != sorted(FUNCS):
        raise ValueError(f"{path} names {names}, the code has {sorted(FUNCS)}")
    return specs


def run_tool(kb: Knowledge, name: str, args: dict) -> ToolResult:
    """Run one tool; a bad name or bad arguments come back as a result the model can read and correct."""
    if name not in FUNCS:
        return ToolResult(f"There is no tool {name!r}. The tools are: {', '.join(FUNCS)}.", f"unknown tool {name}")
    if not isinstance(args, dict):
        return ToolResult("The arguments must be a JSON object.", "bad arguments")
    try:
        return FUNCS[name](kb, **args)
    except ToolError as e:
        return ToolResult(str(e), f"error: {e}")
