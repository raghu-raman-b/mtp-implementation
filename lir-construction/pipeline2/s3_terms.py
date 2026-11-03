"""Step 3: key terms, per part.

    window   one call per window of about WINDOW sentences inside the part (OVERLAP shared): every term the lecturer
             explains, kept or dropped with a reason; for kept ones the glossary name, the abbreviation if the
             lecturer uses one, and the definition. Code checks, per term: the term is in its cited sentences, the
             sentences are in the window, the abbreviation is written in its sentence (otherwise only the
             abbreviation is dropped).
    judge    one call per part, on the whole part: every kept term (deduplicated across windows): worth a glossary
             entry, name right, definition supported? Failed terms are rewritten once and judged again, then dropped.

A term occurrence: {id, surface, name, abbreviation, abbreviation_at, definition, sentences, concept_id, concept_name}.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids
from pipeline.validate import check_ids, display_name

from . import match as M
from . import prompts as P
from .context import Lecture, Part, Run
from .judge import Item, judge_unit, rewrite_items
from .s2_parts import prefix

WINDOW, OVERLAP, SINGLE_MAX = 40, 10, 50


class Term(BaseModel):
    term: str
    sentence_ids: list[int] = Field(min_length=1, max_length=12)
    reason: str
    keep: bool
    name: str
    abbreviation: str
    abbreviation_sentence: int
    definition: str


class Terms(BaseModel):
    terms: list[Term] = Field(max_length=40)


def windows(a: int, b: int) -> list[tuple[int, int]]:
    """Windows of WINDOW sentences with OVERLAP inside one part; a part of up to SINGLE_MAX is one window."""
    if b - a + 1 <= SINGLE_MAX:
        return [(a, b)]
    out, s = [], a
    while True:
        e = min(s + WINDOW - 1, b)
        if b - e < WINDOW // 4:  # absorb a short tail
            e = b
        out.append((s, e))
        if e == b:
            return out
        s = e + 1 - OVERLAP


def window_block(R: Run, lec: Lecture, a: int, b: int) -> str:
    return P.excerpt_block(R.course.title, lec.inp.title, lec.numbered(a, b), "an excerpt of the lecture")


def _window(R: Run, lec: Lecture, p: Part, w: tuple[int, int]) -> list[dict]:
    a, b = w
    o = R.send("terms", Call(key=f"{p.id}/terms/{a}-{b}", lecture_id=lec.id, schema=Terms, prompt_id=P.TERMS[0],
                             prompt_version=P.TERMS[1],
                             prompt=window_block(R, lec, a, b) + P.objective_line(p.objective)
                             + P.TERMS[2].format(course=R.course.title)))
    model = R.model_of("terms")
    if o.parsed is None:
        R.flag(lec.id, f"{p.id}: key terms unusable for sentences {a}-{b} ({o.errors})")
        return []
    out = []
    for t in o.parsed.terms:
        subj = [lec.s(i) for i in t.sentence_ids if 0 <= i < len(lec.sentences)] or [p.id]
        errs = check_ids(t.sentence_ids, a, b, f'term "{t.term}"')
        if not errs and not M.term_in(t.term, lec.text(t.sentence_ids)):
            errs = [f'"{t.term}" is not in its cited sentences']
        if errs:
            R.decisions.add("terms", subj, "candidate dropped", "; ".join(errs), o, model, term=t.term)
            R.count("terms_dropped_sources")
            continue
        R.count("term_candidates")
        if not t.keep:
            R.decisions.add("terms", subj, "dropped", t.reason, o, model, term=t.term)
            R.count("terms_dropped_keep")
            continue
        if not t.definition.strip() or not t.name.strip():
            R.decisions.add("terms", subj, "dropped", "kept but no name or definition given", o, model, term=t.term)
            continue
        abbr, abbr_at = None, None
        if t.abbreviation.strip():
            j = t.abbreviation_sentence
            if a <= j <= b and M.abbrev_in(t.abbreviation, lec.sentences[j].text):
                abbr, abbr_at = t.abbreviation.strip(), lec.s(j)
            else:
                R.decisions.add("terms", subj, "abbreviation rejected",
                                f'"{t.abbreviation}" is not written in sentence {j} of the excerpt', o, model,
                                term=t.term)
        R.decisions.add("terms", subj, "kept", t.reason, o, model, term=t.term)
        out.append({"surface": t.term.strip(), "name": display_name(strip_ids(t.name)), "abbreviation": abbr,
                    "abbreviation_at": abbr_at, "definition": strip_ids(t.definition),
                    "sentences": sorted(set(t.sentence_ids)), "window": (a, b), "concept_id": None,
                    "concept_name": None})
    return out


CRIT = ("ok only if all hold: (1) the term deserves an entry in the glossary of key terms of this course: it names a "
        "concept of the subject, or a specific system, device, product, method or person the subject studies, that "
        "this part explains (not a generic word, not a phrase about the lecture, not course logistics); (2) the name "
        "is a noun phrase in the singular, in the lecturer's words; (3) every claim in the definition is stated or "
        "clearly implied in this part, and the definition starts with the term and says what kind of thing it is.")


def run_part(R: Run, lec: Lecture, p: Part):
    """All windows of the part (in parallel), then one judge call for the part's terms."""
    ws = windows(p.a, p.b)
    found = [_window(R, lec, p, ws[0])] if len(ws) == 1 else R.flow.map("terms window",
                                                                         lambda w: _window(R, lec, p, w), ws)
    terms, seen = [], {}
    for ts in found:   # overlapping windows: keep the first occurrence of a name
        for t in ts:
            k = M.key(t["name"])
            if k in seen:
                first = seen[k]
                first["sentences"] = sorted(set(first["sentences"]) | set(t["sentences"]))
                continue
            seen[k] = t
            terms.append(t)
    pre = prefix(R, lec, p)

    def show(it: Item) -> str:
        t = it.obj
        ab = f' (abbreviation "{t["abbreviation"]}")' if t["abbreviation"] else ""
        return (f'Key term "{t["name"]}"{ab}, said as "{t["surface"]}" in sentences {t["sentences"]}.\n'
                f'Definition: "{t["definition"]}"')

    def rewrite(failed):
        r = rewrite_items(R, key=f"{p.id}/terms", lid=lec.id, prefix=pre, failed=failed, show=show,
                          item_schema={"properties": {"name": {"type": "string"}, "definition": {"type": "string"}}},
                          rules="Give the glossary name (a noun phrase in the singular, in the lecturer's words) and a "
                                "definition of one or two sentences that starts with the term, says what kind of "
                                "thing it is and what sets it apart, and claims only what this part says.",
                          check=lambda it, x: [] if x["name"].strip() and x["definition"].strip() else ["empty"])
        return {k: {**failed[k].obj, "name": display_name(strip_ids(x["name"])),
                    "definition": strip_ids(x["definition"])} for k, x in r.items()}

    items = judge_unit(R, key=f"{p.id}/terms", lid=lec.id, prefix=pre, show=show, criteria=CRIT, rewrite=rewrite,
                       items=[Item(t, "key_term", [lec.s(i) for i in t["sentences"]]) for t in terms])
    kept = []
    for it in items:
        if it.ok:
            kept.append(it.obj)
        else:
            R.decisions.add("judge", it.subject, "key term dropped", "failed the judge after a rewrite",
                            term=it.obj["name"])
    kept.sort(key=lambda t: t["sentences"][0])
    for k, t in enumerate(kept, 1):
        t["id"] = f"{p.id}/T{k}"
        t.pop("window", None)
    p.terms = kept
    R.count("terms_kept", len(kept))
