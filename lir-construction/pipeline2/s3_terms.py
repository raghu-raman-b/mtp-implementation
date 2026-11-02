"""Step 3: key terms, per lecture.

    3a candidates   windows of about WINDOW sentences inside each part; every term the lecturer explains, no cap
                    (code: the term occurs in its cited sentences)
    3b keep         one decision per candidate, with a reason
    3c name         glossary name; abbreviation only if the lecturer says it (code: it is in the cited sentence)
    3d define       definition from the cited sentences
    3e grounded     every claim supported? if not: one rewrite with the reason, then dropped

3b-3e for one window run one after another on one server slot: they all start with the window's transcript.
A term occurrence: {id, surface, name, abbreviation, abbreviation_at, definition, sentences, window, concept_id}.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids
from pipeline.validate import check_ids, display_name

from . import match as M
from . import prompts as P
from .context import Lecture, Part, Run

WINDOW, OVERLAP, SINGLE_MAX = 40, 10, 50


class Cand(BaseModel):
    term: str
    sentence_ids: list[int] = Field(min_length=1, max_length=12)


class Cands(BaseModel):
    terms: list[Cand] = Field(max_length=40)


class Keep(BaseModel):
    reason: str
    keep: bool


class Name(BaseModel):
    name: str
    abbreviation: str
    abbreviation_sentence: int


class Define(BaseModel):
    definition: str


class Grounded(BaseModel):
    reason: str
    supported: bool


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


def _cand_errors(lec: Lecture, a: int, b: int, c: Cand) -> list[str]:
    e = check_ids(c.sentence_ids, a, b, f'term "{c.term}"')
    if not e and not M.term_in(c.term, lec.text(c.sentence_ids)):
        e = [f'term "{c.term}" does not occur in its cited sentences {c.sentence_ids}; cite the sentences where it is '
             f'said, or leave it out']
    return e


# ------------------------------------------------------------------ 3a
def candidates(R: Run) -> dict[tuple, list[dict]]:
    """window (lecture id, part id, a, b) -> candidates {term, sentences}, deduplicated within each part."""
    llm = R.llm("candidates")
    calls = []
    for lec in R.lectures:
        for p in lec.parts:
            for a, b in windows(p.a, p.b):
                calls.append(Call(key=f"{p.id}/candidates/{a}-{b}", lecture_id=lec.id,
                                  prompt=window_block(R, lec, a, b) + P.CANDIDATES[2], schema=Cands,
                                  prompt_id=P.CANDIDATES[0], prompt_version=P.CANDIDATES[1],
                                  check=lambda x, lec=lec, a=a, b=b: [m for c in x.terms for m in _cand_errors(lec, a, b, c)],
                                  ctx={"lec": lec, "part": p, "w": (a, b)}))
    by_window: dict[tuple, list[dict]] = {}
    seen: dict[tuple, dict] = {}   # (part id, name key) -> candidate
    for o in llm.run("v2_term_candidates", calls, "find term candidates"):
        lec, p, (a, b) = o.call.ctx["lec"], o.call.ctx["part"], o.call.ctx["w"]
        R.record(o, "candidates", llm, o.call.key)
        wkey = (lec.id, p.id, a, b)
        by_window.setdefault(wkey, [])
        if o.parsed is None:
            R.flag(lec.id, f"{p.id}: term candidates unusable for sentences {a}-{b} ({o.errors})")
            continue
        for c in o.parsed.terms:
            if _cand_errors(lec, a, b, c):  # still failing after the retries: this candidate only is dropped
                R.decisions.add("candidates", [lec.s(i) for i in c.sentence_ids if 0 <= i < len(lec.sentences)] or [p.id],
                                "candidate dropped", "the term is not in its cited sentences (or they are outside "
                                "the excerpt)", o, llm.model, term=c.term)
                continue
            k = (p.id, M.key(c.term))
            if k in seen:  # overlapping windows: keep the first, add its sentences from the same window
                first = seen[k]
                if first["window"] == (a, b):
                    first["sentences"] = sorted(set(first["sentences"]) | set(c.sentence_ids))
                continue
            cand = {"surface": c.term.strip(), "sentences": sorted(set(c.sentence_ids)), "window": (a, b), "part": p.id}
            seen[k] = cand
            by_window[wkey].append(cand)
            R.count("term_candidates")
    return by_window


# ------------------------------------------------------------------ 3b-3e
def _job(R: Run, lec: Lecture, p: Part, a: int, b: int, cands: list[dict], llm):
    pre = window_block(R, lec, a, b) + P.objective_line(p.objective)
    model = llm.model

    def call(key, prompt_spec, text, schema, check=None):
        return Call(key=f"{p.id}/{a}-{b}/{key}", lecture_id=lec.id, prompt=pre + text, schema=schema,
                    prompt_id=prompt_spec[0], prompt_version=prompt_spec[1], check=check)

    def job(send):
        kept = []
        for c in cands:
            term, ids = c["surface"], c["sentences"]
            subj = [lec.s(i) for i in ids]
            # 3b keep or drop
            o = send(call(f"keep/{term}", P.KEEP, P.KEEP[2].format(term=term, ids=ids, course=R.course.title), Keep))
            R.record(o, "keep", llm, o.call.key)
            if o.parsed is None or not o.parsed.keep:
                why = o.parsed.reason if o.parsed else f"no usable answer: {o.errors}"
                R.decisions.add("keep", subj, "dropped", why, o, model, term=term)
                R.count("terms_dropped_keep")
                continue
            R.decisions.add("keep", subj, "kept", o.parsed.reason, o, model, term=term)

            # 3c name and abbreviation
            def name_check(x: Name):
                errs = [] if x.name.strip() else ["the name is empty"]
                if x.abbreviation.strip():
                    j = x.abbreviation_sentence
                    if not a <= j <= b:
                        errs.append(f"abbreviation_sentence {j} is not in this excerpt ({a} to {b})")
                    elif not M.abbrev_in(x.abbreviation, lec.sentences[j].text):
                        errs.append(f'"{x.abbreviation}" is not written in sentence {j}; give the abbreviation exactly '
                                    f'as it appears there, or "" and -1 if the lecturer uses none')
                return errs
            o = send(call(f"name/{term}", P.NAME, P.NAME[2].format(term=term, ids=ids), Name, name_check))
            R.record(o, "name", llm, o.call.key)
            name, abbr, abbr_at = term, None, None
            if o.parsed is not None and o.parsed.name.strip():
                name = o.parsed.name.strip()
                if o.ok and o.parsed.abbreviation.strip():
                    abbr, abbr_at = o.parsed.abbreviation.strip(), lec.s(o.parsed.abbreviation_sentence)
                elif o.parsed.abbreviation.strip():
                    R.decisions.add("name", subj, "abbreviation rejected", "; ".join(o.errors), o, model,
                                    term=term, abbreviation=o.parsed.abbreviation)
            name = display_name(strip_ids(name))

            # 3d define, 3e grounded (one rewrite)
            dtext = P.DEFINE[2].format(name=name, ids=ids)
            definition, reason, ok = None, "", False
            for attempt in range(2):
                extra = P.REWRITE.format(previous=definition, reason=reason) if attempt else ""
                o = send(call(f"define/{term}/{attempt}", P.DEFINE, dtext + extra, Define,
                              lambda x: [] if x.definition.strip() else ["the definition is empty"]))
                R.record(o, "define", llm, o.call.key)
                if o.parsed is None:
                    reason = f"no usable definition: {o.errors}"
                    break
                definition = strip_ids(o.parsed.definition)
                g = send(call(f"ground/{term}/{attempt}", P.GROUND,
                              P.GROUND[2].format(name=name, definition=definition, where=f" (sentences {ids})"), Grounded))
                R.record(g, "ground", llm, g.call.key)
                if g.parsed is not None and g.parsed.supported:
                    ok = True
                    break
                reason = g.parsed.reason if g.parsed else f"no usable check: {g.errors}"
                R.decisions.add("ground", subj, "definition rejected", reason, g, model, term=name, definition=definition)
            if not ok:
                R.decisions.add("ground", subj, "dropped", f"no supported definition after a rewrite: {reason}",
                                model=model, term=name)
                R.count("terms_dropped_ground")
                continue
            kept.append({"surface": term, "name": name, "abbreviation": abbr, "abbreviation_at": abbr_at,
                         "definition": definition, "sentences": ids, "window": (a, b), "concept_id": None})
        return kept
    return job


def run(R: Run, by_window: dict | None = None):
    """3b-3e. `by_window` is the result of candidates(R) (run earlier, on the generator)."""
    if by_window is None:
        by_window = candidates(R)
    llm = R.llm("keep")
    for step in ("name", "define", "ground"):
        if R.llm(step) is not llm:
            raise SystemExit("steps keep, name, define and ground must use the same model (they share a prompt start)")
    keys = [k for k, v in by_window.items() if v]
    jobs = []
    for lid, pid, a, b in keys:
        lec = R.lec(lid)
        jobs.append(_job(R, lec, lec.part(pid), a, b, by_window[(lid, pid, a, b)], llm))
    results = llm.run_jobs("v2_terms", jobs, f"keep, name, define, check ({sum(len(by_window[k]) for k in keys)} candidates)")
    for (lid, pid, a, b), kept in zip(keys, results):
        R.lec(lid).part(pid).terms.extend(kept)
    for lec in R.lectures:  # number the occurrences in part order (windows were finished in any order)
        for p in lec.parts:
            p.terms.sort(key=lambda t: (t["window"][0], t["sentences"][0]))
            for k, t in enumerate(p.terms, 1):
                t["id"] = f"{p.id}/T{k}"
            R.count("terms_kept", len(p.terms))
    R.dump("3_terms", {l.id: {p.id: p.terms for p in l.parts} for l in R.lectures})
