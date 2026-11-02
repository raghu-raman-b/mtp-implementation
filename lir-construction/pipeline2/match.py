"""Finding a term in transcript text. Used only for sources (is the term in its cited sentences?) and for finding
mentions; never to decide meaning.

    phrase   word stems in order, ignoring a few function words: "head-mounted displays" matches
             "a head mounted display"
    abbrev   case-sensitive whole word, with an optional plural "s": "VR" matches "VRs", not "very" or "vr"
"""
from __future__ import annotations

import re
from collections import defaultdict

from pipeline.validate import fuzzy_in, norm_words

MAX_NGRAM = 8


def key(text: str) -> str:
    """Normalized form of a name: lower case, stems, no function words. Equal keys = the same name."""
    return " ".join(norm_words(text))


def term_in(term: str, text: str) -> bool:
    """The term (or a close spelling of it) occurs in the text: for checking cited sentences."""
    return fuzzy_in(term, text)


def abbrev_in(abbrev: str, text: str) -> bool:
    a = abbrev.strip()
    if not a:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(a)}s?(?![A-Za-z0-9])", text) is not None


def phrase_in(name: str, text: str) -> bool:
    k = norm_words(name)
    if not k:
        return False
    t = norm_words(text)
    n = len(k)
    return any(t[i:i + n] == k for i in range(len(t) - n + 1))


class SentenceIndex:
    """All sentences of a run, indexed by word-stem n-grams and by raw words, for fast mention lookups."""

    def __init__(self):
        self.ngrams: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self.words: dict[str, list[tuple[str, int]]] = defaultdict(list)

    def add(self, lid: str, i: int, text: str):
        w = norm_words(text)
        seen = set()
        for n in range(1, MAX_NGRAM + 1):
            for j in range(len(w) - n + 1):
                g = " ".join(w[j:j + n])
                if g not in seen:
                    seen.add(g)
                    self.ngrams[g].append((lid, i))
        for tok in set(re.findall(r"[A-Za-z0-9]+", text)):
            self.words[tok].append((lid, i))
            if tok.endswith("s") and len(tok) > 2:
                self.words[tok[:-1]].append((lid, i))

    def find_phrase(self, name: str) -> list[tuple[str, int]]:
        k = key(name)
        if not k or len(k.split()) > MAX_NGRAM:
            return []
        return self.ngrams.get(k, [])

    def find_abbrev(self, abbrev: str) -> list[tuple[str, int]]:
        return self.words.get(abbrev.strip(), [])


class ConceptMatcher:
    """Which registry concepts a text names (name, other names, abbreviations), for tagging items with concepts."""

    def __init__(self, concepts):
        self.concepts = list(concepts)
        self.keys = {c.id: [key(c.name)] + [key(a["text"]) for a in c.aliases if a["kind"] == "name"]
                     for c in self.concepts}
        self.abbrs = {c.id: list(c.abbrevs()) for c in self.concepts}

    def find(self, text: str, max_pos: int | None = None) -> list[str]:
        w = norm_words(text)
        grams = {" ".join(w[i:i + n]) for n in range(1, MAX_NGRAM + 1) for i in range(len(w) - n + 1)}
        words = set(re.findall(r"[A-Za-z0-9]+", text))
        words |= {x[:-1] for x in words if x.endswith("s") and len(x) > 2}
        out = []
        for c in self.concepts:
            if max_pos is not None and c.intro_pos > max_pos:
                continue
            if any(k and k in grams for k in self.keys[c.id]) or any(a in words for a in self.abbrs[c.id]):
                out.append(c.id)
        return out
