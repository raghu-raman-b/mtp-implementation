"""Code checks on the facts of one segment (no LLM). Used by 2a (on the extraction) and 2b (on the final facts).

    collapse(facts)                 exact repeats become one fact that cites all their sentences
    flags(facts, sentences)         per fact, what looks wrong:
        pointing      a pointing word left in the text ("this", "the slide", a leading "It")        -> 2b rewrites it
        acronym       an acronym in brackets that the segment never uses ("extended reality (ER)")  -> 2b rewrites it
        bare_acronym  an acronym the segment uses, written without its full term                    report only
        same_evidence cites exactly the sentences another fact cites (one point split in two?)      report only
        similar       reads almost like another fact (one list split member by member?)             report only
        long          more than LONG words (several points in one fact?)                            report only
    coverage(facts, n)              the share of the segment's sentences that some fact cites
    report(facts, sentences)        all of it for one segment, for checks/lec_<n>.json

Only exact repeats are collapsed. Near-repeats are reported, not collapsed: a list split member by member ("...the
healthcare industry... 15 percent", "...the engineering industry... 14 percent") reads as near-duplicates, and
dropping one would lose its member. The judge decides those (property "Whole"). A fact is {"evidence": [...],
"text": ...}; evidence may be local numbers or sentence IDs, the checks only compare them.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

REWRITE = ("pointing", "acronym")       # the kinds 2b sends to the rewrite even when the judge passed the fact
SIMILAR = 0.8                           # token-sequence similarity from which two facts are reported as similar
LONG = 60                               # words from which a fact is reported as long

WORD = re.compile(r"[a-z0-9]+(?:[.'-][a-z0-9]+)*")
FUNCTION_WORDS = frozenset("a an the of in on at to for by with and or as is are was were be been that which its "
                           "their from into than then so such can may".split())
LEADING = re.compile(r"(It|This|That|These|Those|They|Here)\b")
POINTING = re.compile(r"\bthis\b|\bas shown\b|\bthe (?:slide|figure|picture|above|lecturer|instructor|professor)\b|"
                      r"\b(?:mentioned|shown|seen|discussed) (?:earlier|above|before|previously)\b", re.I)
BRACKETED = re.compile(r"\(([A-Za-z0-9][A-Za-z0-9./&-]{0,9})\)")
CAPS = re.compile(r"\b[A-Z][A-Z0-9]{1,5}s?\b")


def content_tokens(text: str) -> list[str]:
    """The text's words without function words, lowercased, a plural "s" dropped."""
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
            for w in WORD.findall(text.lower()) if w not in FUNCTION_WORDS]


def collapse(facts: list[dict]) -> tuple[list[dict], list[tuple[int, int]]]:
    """Facts with exact repeats (the same content words in the same order) merged into the first, which then cites
    the sentences of all. Returns the facts kept (each with "index": its place in the input) and (kept, dropped)."""
    kept, seen, dropped = [], {}, []
    for i, f in enumerate(facts):
        key = tuple(content_tokens(f["text"]))
        if key in seen:
            first = kept[seen[key]]
            first["evidence"] = sorted(set(first["evidence"]) | set(f["evidence"]), key=_evidence_order)
            dropped.append((first["index"], i))
        else:
            seen[key] = len(kept)
            kept.append({**f, "index": i, "evidence": list(f["evidence"])})
    return kept, dropped


def _evidence_order(e):
    """Sentence numbers in order: 3, or "1/3" by its number."""
    return int(str(e).rsplit("/", 1)[-1])


def _is_acronym(s: str) -> bool:
    return sum(c.isupper() for c in s) >= 2 and " " not in s


def _used(acronym: str, segment_text: str) -> bool:
    """The acronym appears in the segment as a word (XR, or XRs for XR)."""
    forms = {acronym, acronym.rstrip("s"), acronym + "s"}
    return any(re.search(rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])", segment_text) for a in forms if a)


def flags(facts: list[dict], sentences: list[str]) -> list[list[dict]]:
    """For each fact, its flags: [{"kind": ..., "note": ...}]."""
    segment_text = "\n".join(sentences)
    toks = [content_tokens(f["text"]) for f in facts]
    out = []
    for i, f in enumerate(facts):
        text, fl = f["text"], []
        lead = LEADING.match(text)
        words = sorted({m.group(0).lower() for m in POINTING.finditer(text)}
                       | ({lead.group(1).lower()} if lead else set()))
        if words:
            fl.append({"kind": "pointing", "note": "The text has a pointing word that a reader cannot resolve: "
                       + ", ".join(f'"{w}"' for w in words) + ". Name what it refers to."})
        bracketed = [a for a in BRACKETED.findall(text) if _is_acronym(a)]
        absent = [a for a in bracketed if not _used(a, segment_text)]
        if absent:
            fl.append({"kind": "acronym", "note": "The lecturer does not use " + ", ".join(f'"{a}"' for a in absent)
                       + " in the segment. Write the term in full without it."})
        bare = sorted({a for a in CAPS.findall(BRACKETED.sub("", text)) if _used(a, segment_text)
                       and a not in bracketed})
        if bare:
            fl.append({"kind": "bare_acronym", "note": "Written without the full term: " + ", ".join(bare)})
        same = [j for j, g in enumerate(facts) if j != i and set(g["evidence"]) == set(f["evidence"])]
        if same:
            fl.append({"kind": "same_evidence", "with": same, "note": "Cites exactly the sentences of another fact."})
        similar = [j for j in range(len(facts)) if j != i
                   and SequenceMatcher(None, toks[i], toks[j], autojunk=False).ratio() >= SIMILAR]
        if similar:
            fl.append({"kind": "similar", "with": similar, "note": "Reads almost like another fact."})
        n_words = len(text.split())
        if n_words > LONG:
            fl.append({"kind": "long", "note": f"{n_words} words: several points in one fact?"})
        out.append(fl)
    return out


def coverage(facts: list[dict], n_sentences: int) -> float:
    """The share of the segment's sentences cited by at least one fact."""
    return round(len({e for f in facts for e in f["evidence"]}) / n_sentences, 3) if n_sentences else 0.0


def rewrite_notes(fact_flags: list[dict]) -> list[str]:
    """The notes of the flags that send a fact to the rewrite."""
    return [fl["note"] for fl in fact_flags if fl["kind"] in REWRITE]


def report(facts: list[dict], sentences: list[str], ids: list[str], collapsed: list | None = None) -> dict:
    """One segment's checks: counts, coverage, the exact repeats collapsed, and the flags per fact ID
    ("with" lists are fact IDs)."""
    per_fact = flags(facts, sentences)
    named = {}
    for fid, fl in zip(ids, per_fact):
        if fl:
            named[fid] = [{**x, "with": [ids[j] for j in x["with"]]} if "with" in x else x for x in fl]
    counts: dict[str, int] = {}
    for fl in per_fact:
        for x in fl:
            counts[x["kind"]] = counts.get(x["kind"], 0) + 1
    return {"sentences": len(sentences), "facts": len(facts), "coverage": coverage(facts, len(sentences)),
            "collapsed": collapsed or [], "flag_counts": counts, "flags": named}
