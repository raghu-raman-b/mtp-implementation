"""Stage 5: the activities of every lecture, from the knowledge layer (MVP of 2026-11-13).

    python scripts/s5_activities.py nptel_vr --llm configs/qwen38_27b_vllm.json [--only 1-5] [--kinds quiz,recap,...]
    python scripts/s5_activities.py nptel_vr --check            (check an existing activities/ against the contract)

Reads   output/<course>/knowledge/ (stage 4d): index, concepts, relations, facts, lectures/lec_<n>.json,
        lecture_graph.json; input/<course>/input/course.json (the course block of the prompts)
Prompts prompts/activity_<kind>.txt for the model-made kinds
Writes  output/<course>/activities/ (or --out), the contract of schemas/activities.md:
          lec_<n>.json     {"lecture", "activities": [{"id", "kind", "scope", "segment", "title", "data", "facts",
                            "concepts"}]}; activity IDs "<lecture>/A<i>" in the order below
          course.json      {"spaced_review": {"cards": [...]}}
          checks.json      the run, totals, per lecture and kind each unit (segment or lecture) with its status, the
                           retries, the items dropped and the report-only flags; "contract": what the contract check
                           of the whole folder found (empty when all is well)
          activities.txt   a readable view of every activity and its problems
          llm/cache.jsonl, calls.jsonl

The kinds (scope; how each is made). Every activity lists the facts and concepts it is built from.
  recall         lecture (shown before it)  code: the concepts the lecture graph says the lecture needs (met_again:
                 first defined in an earlier lecture), those carried by direct prerequisite links first, then the
                 other strong links, then weak ones; at most 6; prompt "What is <name>?", answer its definition (4a),
                 from_lecture the lecture that first defines it; facts: the definition's facts
  quiz           segment  model, one call: the segment's facts numbered, the sub-goal, and as material for wrong
                 options the concepts related to the segment's concepts and other concepts of the lecture (with a
                 short definition) and other facts of the lecture (nearest segments first, not numbered). The model
                 gives per question the cited facts, the question, the correct option, three wrong ones and an
                 explanation; code shuffles the four options (seeded by the question) and sets "answer"
  recap          segment  model, one call: the segment's facts, its sub-goal and its objective; points with their
                 facts, and a short text
  put_in_order   segment or lecture  model, one call per lecture: the facts by segment; zero to two exercises (the
                 model answers none where no fact gives an order); an exercise whose facts are all in one segment is
                 placed on that segment, others on the lecture
  concept_map    lecture  code: the relationships of the lecture's segments as edges (each with the relationship's
                 facts); nodes their ends and the concepts the lecture introduces; none without a relationship
  complete_map   lecture  code: the concept map with up to 4 blanks (an edge's label, or the concept at one end when
                 it is on no other edge, so the answer is not visible elsewhere), each with 3 to 4 options from the
                 lecture's other labels or concept names (never another right answer); needs two edges
  match_pairs    lecture  code: up to 8 concepts with a definition (those defined in the lecture first), each with
                 the first sentence of its definition, without the leading "<name> is", its names masked "___",
                 capped at 22 words, and the definition's facts; needs 3 pairs
  crossword      lecture  code lays out up to 12 answers (concept names, letters only, 3 to 15 letters) from the
                 concepts the lecture defines (filled up from the other concepts it uses with a definition when it
                 defines fewer than 6), greedy: longest first, each placed where it crosses most, no two letters
                 side by side that do not belong to one word; the best of several first words; at least 4 placed.
                 Then the model writes the clues (one call per lecture) from the definitions; code appends the
                 enumeration "(4-7,7)"; each entry carries its concept's definition facts
  odd_one_out    lecture  model, one call: the lecture's concepts with short definitions, its relationships and its
                 facts; zero to three puzzles (three items of a group the facts state, one odd item, the reason);
                 code shuffles the four options
  open_question  lecture  model, one call: the lecture's facts and the defining facts of the concepts it needs from
                 earlier lectures (numbered together), its relationships with their fact numbers, its goal; 2 to 4
                 questions with a reference answer, key facts (at least two) and concepts (by name, mapped to IDs)
  spaced_review  course.json  code: a card per concept with a definition: front its name (and acronym), back the
                 definition, the lectures that use it
Order of the activities of a lecture: recall; per segment quiz, recap, put_in_order; then concept_map, complete_map,
match_pairs, crossword, odd_one_out, put_in_order (lecture), open_question.

The model-made kinds. One request per unit, all sent at once (generate_many). Facts are numbered [1]..[n] in the
prompt and mapped back to fact IDs through that list. Code checks with retry (the problems are shown to the model,
LLM API feedback, the config's retries): a cited number outside 1..n or none cited (open questions: fewer than two);
an empty text; a count outside its range (quiz 3 to 5 questions, fewer when the segment has fewer facts; recap 2 to
5 points; open questions 2 to 4; crossword: one clue per answer); quiz options not one correct and three wrong, two
options the same, "all/none of the above"; a repeated question; an odd-one-out group not three items or an item
twice; put-in-order steps not 3 to 8 or repeated; a clue with the answer or one of its words (or another name of the
concept), or over 20 words; open-question concepts not in the list. When every attempt fails the client keeps the
attempt with the fewest problems: the unit is "unresolved" (checks.json) and its items that still have a problem
are dropped (a clue with the answer's words is masked "___"; a missing clue is taken from the definition). An
answer that never parses is "no answer": no activity. Report-only flags: quiz correct_longest (the correct option
1.5 times as long as every wrong one), correct_not_in_facts (no content word of the correct option in its cited
facts); recap facts_uncovered; open_question no_earlier_or_relation (no question uses an earlier lecture's fact or a
relationship's fact); odd_one_out not_a_concept (an option that is no concept name or alias of the lecture);
put_in_order order_cue (a step starting with "first", "then", "finally" or a number); crossword small (fewer than 6
answers), filled_from_used, clue_masked, clue_from_definition.

--kinds limits the run to some kinds: the lecture files keep the activities of the other kinds (renumbered in the
order above), checks.json keeps their entries. --only limits it to some lectures; course.json (spaced_review) is
always built from the whole layer. The contract check (also alone, --check) validates every file of the folder
against schemas/activities.md and every fact, concept, relationship, segment and lecture it names against the
layer, the crossword grids (letters that clash, an entry outside the grid or crossing no other) and the answer
indexes; it is written to checks.json "contract" (and makes --check exit 1).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, lectures as lec  # noqa: E402
from scripts import s4a_definitions as s4a  # noqa: E402
from scripts.fact_checks import content_tokens  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPTS = ROOT / "prompts"
KINDS = ("recall", "quiz", "recap", "put_in_order", "concept_map", "complete_map", "match_pairs", "crossword",
         "odd_one_out", "open_question", "spaced_review")
MODEL_KINDS = ("quiz", "recap", "put_in_order", "crossword", "odd_one_out", "open_question")
SEGMENT_ORDER = ("quiz", "recap", "put_in_order")
LECTURE_ORDER = ("concept_map", "complete_map", "match_pairs", "crossword", "odd_one_out", "put_in_order",
                 "open_question")
TITLES = {"recall": "Before you start: recall", "quiz": "Quick quiz", "recap": "Recap",
          "open_question": "Think it through", "concept_map": "Concept map", "complete_map": "Complete the map",
          "crossword": "Crossword", "match_pairs": "Match the terms", "odd_one_out": "Odd one out",
          "put_in_order": "Put in order"}
SCOPES = {"quiz": {"segment"}, "recap": {"segment"}, "put_in_order": {"segment", "lecture"}}
RECALL_CAP, PAIRS_CAP, BLANKS_CAP = 6, 8, 4
CROSS_MAX, CROSS_MIN, CROSS_WANT, CROSS_CANDIDATES = 12, 4, 6, 14
QUIZ_FACTS_CAP, OTHER_FACTS_CAP, RELATED_CAP, LECTURE_FACTS_CAP, EARLIER_CONCEPTS_CAP = 20, 12, 10, 60, 6
CLUE_MAX_WORDS = 15


def knowledge_dir(course: str) -> Path:
    return ROOT / "output" / course / "knowledge"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "activities"


# ---------------------------------------------------------------- the layer
class Layer:
    """The knowledge/ files the stage reads."""

    def __init__(self, kd: Path):
        load = lambda name: json.loads((kd / name).read_text())  # noqa: E731
        self.index = load("index.json")
        self.cards = load("concepts.json")
        self.relations = load("relations.json")
        self.facts = load("facts.json")
        self.graph = load("lecture_graph.json")
        self.keys = list(self.index["lectures"])
        self.lectures = {k: load(f"lectures/{lec.stem_of(k)}.json") for k in self.keys
                         if (kd / "lectures" / f"{lec.stem_of(k)}.json").exists()}

    def lecture_facts(self, k: str) -> list[str]:
        return [f for seg in self.lectures[k]["segments"].values() for f in seg["facts"] if f in self.facts]

    def fact_concepts(self, fids) -> list[str]:
        return list(dict.fromkeys(c for f in fids for c in self.facts.get(f, {}).get("concepts", [])))

    def has_definition(self, cid: str) -> bool:
        c = self.cards.get(cid, {})
        return bool(c.get("defined") and c.get("definition", "").strip())

    def definition_facts(self, cid: str) -> list[str]:
        c = self.cards[cid]
        return [f for f in (c.get("definition_facts") or c.get("defining_facts") or []) if f in self.facts]

    def defined_here(self, cid: str, k: str) -> bool:
        return any(d["lecture"] == k for d in self.cards[cid].get("defined_in", []))

    def names(self, cid: str) -> list[str]:
        c = self.cards[cid]
        return list(dict.fromkeys([c["name"]] + c.get("aliases", []) + c.get("acronyms", [])))


# ---------------------------------------------------------------- text helpers
def norm(s) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(s).lower()).split())


def txt(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def ints(x) -> list[int]:
    return [i for i in x if isinstance(i, int) and not isinstance(i, bool)] if isinstance(x, list) else []


def stable_rng(*parts) -> random.Random:
    return random.Random(int(hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()[:12], 16))


def first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", text.strip(), maxsplit=1)[0]


def cap_words(text: str, n: int) -> str:
    w = text.split()
    return text if len(w) <= n else " ".join(w[:n]).rstrip(",;:") + " …"


def short(text: str, n: int = 25) -> str:
    return cap_words(first_sentence(text), n)


def _name_pattern(name: str) -> str:
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", name.strip()) if p]
    return r"[\s\-]+".join(parts)


def mask_terms(text: str, names: list[str]) -> str:
    """Every name (case, hyphens and a plural ending ignored) replaced by "___"."""
    for name in sorted({n for n in names if n.strip()}, key=len, reverse=True):
        text = re.sub(r"(?i)(?<![A-Za-z0-9])" + _name_pattern(name) + r"(?:e?s)?(?![A-Za-z0-9])", "___", text)
    return text


def short_definition(defn: str, names: list[str], n: int = 22) -> str:
    """The first sentence of a definition, without its leading "<name> (ACR) is", names masked, capped."""
    s = first_sentence(defn)
    alt = "|".join(_name_pattern(x) for x in sorted(names, key=len, reverse=True) if x.strip())
    m = re.match(r"(?i)\s*(?:the |an? )?(?:" + alt + r")(?:\s*\([^)]*\))?\s*,?\s*(?:is|are|refers to|means|denotes|"
                 r"describes)\s+(.+)", s) if alt else None
    if m and m[1].strip():
        s = m[1].strip()
        s = s[0].upper() + s[1:]
    return cap_words(mask_terms(s, names), n)


STOP = set("a an the of and or for in on to with by from as at is are its into".split())


def term_words(names: list[str]) -> set[str]:
    return {w for n in names for w in norm(n).split() if len(w) >= 2 and w not in STOP}


def same_word(t: str, w: str) -> bool:
    """t is the word w or a form of it: "displays" for "display", "stereoscopic" for "stereoscopy"."""
    if t == w or (len(w) >= 4 and t.startswith(w)) or (len(t) >= 5 and w.startswith(t)):
        return True
    n = 0
    while n < min(len(t), len(w)) and t[n] == w[n]:
        n += 1
    return n >= max(5, min(len(t), len(w)) - 3)


def words_in(clue: str, words: set[str]) -> list[str]:
    """The words of a term that a clue writes, in any form (same_word)."""
    toks = norm(clue).split()
    return [w for w in sorted(words) if any(same_word(t, w) for t in toks)]


def mask_words(clue: str, names: list[str], words: set[str]) -> str:
    """The names, then every word that is a form of a term word, replaced by "___"."""
    clue = mask_terms(clue, names)
    return re.sub(r"[A-Za-z0-9]+", lambda m: "___" if any(same_word(m[0].lower(), w) for w in words) else m[0],
                  clue)


def letters(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    return "".join(ch for ch in s.upper() if "A" <= ch <= "Z")


def enumeration(name: str) -> str:
    return "(" + ",".join("-".join(str(len(letters(p))) for p in w.split("-") if letters(p))
                          for w in name.split() if letters(w)) + ")"


def concept_line(layer: Layer, cid: str, words: int = 25) -> str:
    c = layer.cards[cid]
    s = f"- {c['name']}" + (f" ({', '.join(c['aliases'])})" if c.get("aliases") else "")
    return s + (f": {short(c['definition'], words)}" if layer.has_definition(cid) else "")


def numbered(fids: list[str], layer: Layer, k: str | None = None, start: int = 1) -> list[str]:
    """[i] text; a fact of another lecture than k is marked with its lecture."""
    out = []
    for i, f in enumerate(fids, start):
        lk = layer.facts[f]["lecture"]
        mark = f"({s4a.lecture_label(lk)}) " if k is not None and lk != k else ""
        out.append(f"[{i}] {mark}{layer.facts[f]['text']}")
    return out


def relation_lines(layer: Layer, rids: list[str], num: dict | None = None) -> list[str]:
    out = []
    for rid in rids:
        r = layer.relations[rid]
        s, o = layer.cards.get(r["subject"], {}).get("name", r["subject"]), layer.cards.get(r["object"], {}).get(
            "name", r["object"])
        line = f"- {s} -- {r['label']} -- {o}"
        if num is not None:
            ns = sorted({num[f] for f in r["facts"] if f in num})
            line += f" (facts {', '.join(map(str, ns))})" if ns else ""
        out.append(line)
    return out


def count_text(lo: int, hi: int) -> str:
    return f"{lo} to {hi}" if lo < hi else f"exactly {lo}"


def fill(name: str, **values) -> str:
    return s4a.fill((PROMPTS / f"activity_{name}.txt").read_text(), **values)


# ---------------------------------------------------------------- shared checks
ABOVE = re.compile(r"\b(?:all|none|both) of the (?:above|options|answers)\b", re.I)
ORDER_CUE = re.compile(r"^\s*(?:first|firstly|then|next|finally|lastly|step\b|\d)", re.I)
YEAR = re.compile(r"\b(?:1[5-9]\d\d|20\d\d)\b")
PREVIOUS_STEP = re.compile(r"\bprevious step\b", re.I)
TITLE_CUE = re.compile(r"\b(?:first|last)\b|\d", re.I)
ORDER_WORD = re.compile(r"\b(?:first|then|after|before|next|follow\w*|order|steps?|stages?|sequence|finally|"
                        r"subsequently|once|pipeline|phases?|until|later)\b", re.I)
ABSOLUTE = re.compile(r"\b(?:only|always|never|all|none|must|cannot|solely|entirely)\b", re.I)
TWO_QUESTIONS = re.compile(r",? and (how|why|what|which|when|where)\b", re.I)
LIST_PLACE = [re.compile(x, re.I) for x in (
    r"\bone of (?:the )?(?:\w+ )?(?:two|three|four|five|six|seven|eight|\d+)\b",
    r"\b(?:first|second|third|fourth|fifth|sixth|last) (?:of|in) the\b", r"\blisted (?:first|last)\b")]
POINTING = re.compile(r"\b(?:their|these|those|the above)\b", re.I)
SOURCE_TALK = [re.compile(x, re.I) for x in (
    r"\b(?:the|this) (?:segment|lecture|lecturer|instructor|video|transcript)\b",
    r"\bthe facts? (?:state|say|place|show|list)s?\b", r"\baccording to the (?:lecture|segment|facts)\b",
    r"\bas we (?:saw|discussed)\b", r"\bis (?:listed|identified) as\b")]
ODD_STOP = STOP | set("that this with from than their have which what when where also more most other".split())


# Soft checks (review of 2026-11-15, section 7): shown to the model like the others (retry), but an item that still
# has the problem after the last attempt is kept and flagged in checks.json by the check's name (the judge decides).
# They return (check, message) pairs; hard problems stay plain strings and drop the item.
def source_talk(where: str, text: str) -> list[tuple[str, str]]:
    for pat in SOURCE_TALK:
        m = pat.search(text or "")
        if m:
            return [("source_talk", f'{where} has "{m[0]}", which speaks of the lecture or the facts. The learner '
                                    f'never sees them: say it as a statement about the subject.')]
    return []


def sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def flag_soft(flags: dict, soft: list[tuple[str, str]], pos):
    for check, _ in soft:
        lst = flags.setdefault(check, [])
        if pos not in lst:
            lst.append(pos)


def strip_stop(s: str) -> str:
    """One trailing full stop removed (options and clues end alike)."""
    return s[:-1].rstrip() if s.endswith(".") and not s.endswith("..") else s


def fact_problems(nums, n: int, least: int = 1, name: str = "facts") -> list[str]:
    nums = ints(nums)
    out = []
    bad = sorted({i for i in nums if not 1 <= i <= n})
    if bad:
        out.append(f'"{name}" has {bad}, not in the list of facts: use only the numbers 1 to {n}.')
    good = {i for i in nums if 1 <= i <= n}
    need = min(least, n)
    if len(good) < need:
        out.append(f'"{name}" is empty: cite the numbers of the facts it comes from.' if need == 1 and not good else
                   f'"{name}" cites {len(good)} fact(s): cite the at least {need} facts the answer is built from.')
    return out


def repeats(texts: list[str]) -> list[str]:
    seen, out = set(), []
    for t in texts:
        k = norm(t)
        if k and k in seen and t not in out:
            out.append(t)
        seen.add(k)
    return out


def count_problem(items, lo: int, hi: int, what: str) -> list[str]:
    n = len(items) if isinstance(items, list) else 0
    if not lo <= n <= hi:
        return [f"There are {n} {what}: write {count_text(lo, hi)}."]
    return []


def ids_of(nums, shown: list[str]) -> list[str]:
    return list(dict.fromkeys(shown[i - 1] for i in ints(nums) if 1 <= i <= len(shown)))


def items_of(answer, field_: str) -> list:
    x = answer.get(field_) if isinstance(answer, dict) else None
    return x if isinstance(x, list) else []


# ---------------------------------------------------------------- units
@dataclass
class Unit:
    kind: str
    lecture: str
    segment: str | None
    key: str
    ctx: dict = field(default_factory=dict)
    request: Request | None = None


def request(unit: Unit, prompt: str, schema: dict, seed: int | None) -> Request:
    check = lambda a, u=unit: PROBLEMS[u.kind](a, u.ctx)  # noqa: E731
    return Request(prompt=prompt, key=unit.key, schema=schema, check=check, feedback=True,
                   sampling={} if seed is None else {"seed": seed},
                   meta={"kind": unit.kind, "lecture": unit.lecture, "segment": unit.segment})


def nums_schema(n: int, least: int = 1) -> dict:
    return {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": max(n, 1)},
            "minItems": min(least, n)}


def obj(props: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def arr(items: dict, lo: int, hi: int) -> dict:
    return {"type": "array", "items": items, "minItems": lo, "maxItems": hi}


S = {"type": "string"}


# quiz -----------------------------------------------------------------
def quiz_unit(layer: Layer, course: str, k: str, sid: str, seed) -> Unit | None:
    L, seg = layer.lectures[k], layer.lectures[k]["segments"][sid]
    shown = [f for f in seg["facts"] if f in layer.facts][:QUIZ_FACTS_CAP]
    if not shown:
        return None
    n = len(shown)
    lo, hi = min(3, n), min(5, max(min(3, n), 2 * n))
    seg_c = seg["concepts"]
    neigh = [r["concept"] for c in seg_c if c in layer.cards
             for r in layer.cards[c]["relations"]["out"] + layer.cards[c]["relations"]["in"]]
    related = [c for c in dict.fromkeys(neigh + L["concept_map"]["concepts"]) if c not in seg_c and c in layer.cards]
    related = related[:RELATED_CAP]
    order = list(L["segments"])
    i0 = order.index(sid)
    others = sorted((f for s in order if s != sid for f in L["segments"][s]["facts"] if f in layer.facts),
                    key=lambda f: (abs(order.index(layer.facts[f]["segment"]) - i0), s4a.fact_order(f)))
    others = sorted(others[:OTHER_FACTS_CAP], key=s4a.fact_order)
    material = ([concept_line(layer, c) for c in related] or ["(none)"]) + [""] + \
               ([f"- {layer.facts[f]['text']}" for f in others] or ["(no other facts)"])
    blocks = dict(course=course_meta.course_prompt(course), lecture_title=L["title"], subgoal=seg["subgoal"],
                  facts="\n".join(numbered(shown, layer)), related="\n".join(material))
    u = Unit("quiz", k, sid, f"quiz:{sid}", {"shown": shown, "lo": lo, "hi": hi, "blocks": blocks})
    prompt = fill("quiz", **blocks, count=count_text(lo, hi))
    q = obj({"facts": nums_schema(n), "question": S, "correct": S, "wrong": arr(S, 3, 3), "explanation": S})
    u.request = request(u, prompt, obj({"questions": arr(q, lo, hi)}), seed)
    return u


def quiz_item(q, n: int) -> list[str]:
    if not isinstance(q, dict):
        return ["it is not an object"]
    p = []
    if not txt(q.get("question")):
        p.append("the question is empty.")
    elif not txt(q.get("question")).endswith("?"):
        p.append("write one full question that ends with a question mark, not a sentence to complete.")
    correct = txt(q.get("correct"))
    wrong = q.get("wrong") if isinstance(q.get("wrong"), list) else []
    if not correct:
        p.append('"correct" is empty.')
    if len(wrong) != 3:
        p.append(f'"wrong" has {len(wrong)} options: write exactly three wrong options.')
    if any(not txt(w) for w in wrong):
        p.append("a wrong option is empty.")
    opts = [correct] + [txt(w) for w in wrong]
    rep = repeats(opts)
    if rep:
        p.append(f"the options repeat {rep}: the four options must all be different.")
    if any(ABOVE.search(o) for o in opts):
        p.append('an option says "all/none of the above": every option must be an answer of its own.')
    p += fact_problems(q.get("facts"), n)
    if not txt(q.get("explanation")):
        p.append("the explanation is empty.")
    return p


def quiz_soft(q) -> list[tuple[str, str]]:
    if not isinstance(q, dict):
        return []
    correct = txt(q.get("correct"))
    wrong = [txt(w) for w in q.get("wrong")] if isinstance(q.get("wrong"), list) else []
    out = []
    if correct and wrong and all(wrong):
        n, m = len(correct), max(len(w) for w in wrong)
        if n > 1.2 * m and n - m >= 12:
            out.append(("correct_longest", f"the correct option ({n} characters) is clearly longer than every wrong "
                                           f"option (the longest has {m}). Cut it down to what the answer needs, or "
                                           f"rewrite the wrong options to its length and shape: at least one wrong "
                                           f"option must be as long as the correct one."))
        absw = [j for j, w in enumerate(wrong, 1) if ABSOLUTE.search(w)]
        if len(absw) >= 2 and not ABSOLUTE.search(correct):
            out.append(("absolute_wrong", f"the wrong options {', '.join(map(str, absw))} are made false with "
                                          f'"only", "always", "never" or the like, and the correct option has no '
                                          f"such word. Replace them with options that are wrong in substance."))
    for where, t in [("the question", q.get("question")), ("the correct option", correct)] + \
            [(f"wrong option {j}", w) for j, w in enumerate(wrong, 1)] + [("the explanation", q.get("explanation"))]:
        out += source_talk(where, txt(t))
    return out


def longest_share(qs: list[tuple[str, list[str]]]) -> tuple[list[int], int]:
    """Over (correct, wrong options) per question: the questions (1-based) where the correct option is strictly the
    longest, and how many of them must change to get to half; ([], 0) when at most half."""
    longest = [i for i, (c, ws) in enumerate(qs, 1) if ws and len(c) > max(len(w) for w in ws)]
    if len(qs) < 2 or 2 * len(longest) <= len(qs):
        return [], 0
    return longest, len(longest) - len(qs) // 2


def quiz_problems(answer, ctx) -> list[str]:
    qs = items_of(answer, "questions")
    p = count_problem(qs, ctx["lo"], ctx["hi"], "questions")
    rep = repeats([txt(q.get("question")) for q in qs if isinstance(q, dict)])
    if rep:
        p.append(f"Questions repeat: {rep}. Each question asks about a different point.")
    for i, q in enumerate(qs, 1):
        p += [f"Question {i}: {m}" for m in quiz_item(q, len(ctx["shown"]))]
        p += [f"Question {i}: {m}" for _, m in quiz_soft(q)]
    good = [(txt(q["correct"]), [txt(w) for w in q["wrong"]]) for q in qs
            if isinstance(q, dict) and isinstance(q.get("wrong"), list) and txt(q.get("correct"))]
    longest, k = longest_share(good)
    if longest:
        p.append(f"In questions {', '.join(map(str, longest))} the correct option is the longest of the four, so a "
                 f"learner can score by picking the longest. In at least {k} of them make one wrong option as long "
                 f"as the correct one or longer, or shorten the correct one.")
    return p


def quiz_convert(answer, ctx, layer: Layer, unit: Unit):
    shown, out, dropped, flags, src = ctx["shown"], [], [], {}, []
    seen = set()
    for i, q in enumerate(items_of(answer, "questions"), 1):
        p = quiz_item(q, len(shown))
        if not p and norm(q["question"]) in seen:
            p = ["a repeated question"]
        if p:
            dropped.append({"item": i, "problems": p})
            continue
        seen.add(norm(q["question"]))
        opts = [strip_stop(txt(q["correct"]))] + [strip_stop(txt(w)) for w in q["wrong"]]
        order = [0, 1, 2, 3]
        stable_rng(unit.key, q["question"]).shuffle(order)
        facts = ids_of(q["facts"], shown)
        out.append({"question": txt(q["question"]), "options": [opts[j] for j in order], "answer": order.index(0),
                    "explanation": txt(q["explanation"]), "facts": facts})
        src.append(i)
        flag_soft(flags, quiz_soft(q), len(out))
        words = set(content_tokens(opts[0]))
        if words and not words & {w for f in facts for w in content_tokens(layer.facts[f]["text"])}:
            flags.setdefault("correct_not_in_facts", []).append(len(out))
    if not out:
        return [], dropped, flags
    pairs = [(q["options"][q["answer"]], [o for j, o in enumerate(q["options"]) if j != q["answer"]]) for q in out]
    longest, _ = longest_share(pairs)
    if longest:
        flags["correct_longest_share"] = longest
    for i, (_, ws) in enumerate(pairs, 1):           # report: wrong options that are other questions' keys
        others = [set(content_tokens(c)) for j, (c, _) in enumerate(pairs, 1) if j != i]
        hits = sum(1 for w in ws if len(set(content_tokens(w))) >= 5
                   and any(len(o) >= 5 and jaccard(content_tokens(w), o) >= 0.6 for o in others))
        if hits >= 2:
            flags.setdefault("rotated_options", []).append(i)
    ctx["_conv"] = {"src": src}
    facts = list(dict.fromkeys(f for q in out for f in q["facts"]))
    return [{"scope": "segment", "segment": unit.segment, "data": {"questions": out}, "facts": facts,
             "concepts": layer.fact_concepts(facts)}], dropped, flags


# recap ----------------------------------------------------------------
def recap_unit(layer: Layer, course: str, k: str, sid: str, seed) -> Unit | None:
    L, seg = layer.lectures[k], layer.lectures[k]["segments"][sid]
    shown = [f for f in seg["facts"] if f in layer.facts][:QUIZ_FACTS_CAP]
    if not shown:
        return None
    n = len(shown)
    lo, hi = min(2, n), min(5, max(2, n))
    objective = next((o["goal"] for o in L.get("objectives", []) if sid in o["segments"]), None) \
        or (L["goal"]["goal"] if L.get("goal") else "(none)")
    blocks = dict(course=course_meta.course_prompt(course), lecture_title=L["title"], subgoal=seg["subgoal"],
                  objective=objective, facts="\n".join(numbered(shown, layer)))
    u = Unit("recap", k, sid, f"recap:{sid}", {"shown": shown, "lo": lo, "hi": hi, "blocks": blocks})
    prompt = fill("recap", **blocks, count=count_text(lo, hi))
    u.request = request(u, prompt, obj({"points": arr(obj({"facts": nums_schema(n), "point": S}), lo, hi),
                                        "text": S}), seed)
    return u


def recap_item(pt, n: int) -> list[str]:
    if not isinstance(pt, dict):
        return ["it is not an object"]
    return (["the point is empty."] if not txt(pt.get("point")) else []) + fact_problems(pt.get("facts"), n)


def point_soft(pt) -> list[tuple[str, str]]:
    if not isinstance(pt, dict) or not txt(pt.get("point")):
        return []
    point, out = txt(pt["point"]), []
    n = len(point.split())
    if n > 28:
        out.append(("point_long", f"has {n} words: one sentence of about twenty words at most, with one idea."))
    return out + source_talk("the point", point)


def text_soft(text: str, points: list[str]) -> list[tuple[str, str]]:
    if not text:
        return []
    out, sents = [], sentences(text)
    pw = [norm(x).split() for x in points]
    same = [i for i, x in enumerate(sents, 1) if any(jaccard(norm(x).split(), w) >= 0.8 for w in pw)]
    if sents and 2 * len(same) >= len(sents):
        out.append(("text_repeats_points", f"The text repeats the points almost word for word (its sentences "
                                           f"{', '.join(map(str, same))}). The text has another job: say what the "
                                           f"segment is about as a whole and how the points connect."))
    n, m = len(sents), len(text.split())
    if not 2 <= n <= 4 or m > 90:
        out.append(("text_length", f"The text has {n} sentences and {m} words: write two to four sentences."))
    return out + source_talk("The text", text)


def recap_problems(answer, ctx) -> list[str]:
    pts = items_of(answer, "points")
    p = count_problem(pts, ctx["lo"], ctx["hi"], "points")
    text = txt(answer.get("text") if isinstance(answer, dict) else "")
    if not text:
        p.append('"text" is empty: write the summary.')
    for i, pt in enumerate(pts, 1):
        p += [f"Point {i}: {m}" for m in recap_item(pt, len(ctx["shown"]))]
        p += [f"Point {i} {m}" if m.startswith("has ") else f"Point {i}: {m}" for _, m in point_soft(pt)]
    p += [m for _, m in text_soft(text, [txt(pt.get("point")) for pt in pts if isinstance(pt, dict)])]
    return p


def recap_convert(answer, ctx, layer: Layer, unit: Unit):
    shown, pts, facts, dropped, flags, src, pfacts = ctx["shown"], [], [], [], {}, [], []
    for i, pt in enumerate(items_of(answer, "points"), 1):
        p = recap_item(pt, len(shown))
        if p:
            dropped.append({"item": i, "problems": p})
            continue
        pts.append(txt(pt["point"]))
        src.append(i)
        pfacts.append(ids_of(pt["facts"], shown))
        facts += pfacts[-1]
        flag_soft(flags, point_soft(pt), len(pts))
    text = txt(answer.get("text"))
    if not text or not pts:
        return [], dropped, flags
    flag_soft(flags, text_soft(text, pts), 0)       # 0: the text
    dup = [[i, j] for i in range(1, len(pts) + 1) for j in range(i + 1, len(pts) + 1)
           if jaccard(content_tokens(pts[i - 1]), content_tokens(pts[j - 1])) >= 0.6]
    if dup:
        flags["duplicate_points"] = dup
    facts = list(dict.fromkeys(facts))
    left = [f for f in shown if f not in facts]
    if left:
        flags["facts_uncovered"] = left
    ctx["_conv"] = {"src": src, "point_facts": pfacts}
    return [{"scope": "segment", "segment": unit.segment, "data": {"text": text, "points": pts}, "facts": facts,
             "concepts": layer.fact_concepts(facts)}], dropped, flags


# open questions -------------------------------------------------------
def needed_concepts(layer: Layer, k: str) -> list[str]:
    """The concepts lecture k needs from earlier lectures: met_again, those of direct links first, then the other
    strong links, then weak ones; within a rank in course order of the lecture that first defines them."""
    rank = {}
    for link in layer.graph.get("links", []):
        if link["to"] == k:
            r = {"direct": 0, "indirect": 1}.get(link["kind"], 2)
            for c in link["concepts"]:
                rank[c] = min(rank.get(c, 3), r)
    met = [c for c in layer.lectures[k]["concepts"].get("met_again", []) if c in layer.cards]
    fd = lambda c: layer.cards[c].get("first_defined")  # noqa: E731
    met = [c for c in met if fd(c) and lec.order(fd(c)) < lec.order(k)]
    return sorted(met, key=lambda c: (rank.get(c, 3), lec.order(fd(c)), c))


def open_unit(layer: Layer, course: str, k: str, seed) -> Unit | None:
    L = layer.lectures[k]
    own = layer.lecture_facts(k)[:LECTURE_FACTS_CAP]
    if len(own) < 2:
        return None
    earlier_c = [c for c in needed_concepts(layer, k) if layer.definition_facts(c)][:EARLIER_CONCEPTS_CAP]
    earlier = list(dict.fromkeys(f for c in earlier_c for f in layer.definition_facts(c)[:2] if f not in own))
    shown = own + earlier
    num = {f: i for i, f in enumerate(shown, 1)}
    lines = numbered(own, layer, k)
    if earlier:
        lines += ["", "From earlier lectures:"] + numbered(earlier, layer, k, start=len(own) + 1)
    rids = L["concept_map"]["relations"]
    cids = list(dict.fromkeys(L["concept_map"]["concepts"] + earlier_c))
    name_of = {}
    for c in cids:
        name_of.setdefault(layer.cards[c]["name"], c)
    clines = [f"- {n}" + (f" (from {s4a.lecture_label(layer.cards[c]['first_defined'])})" if c in earlier_c else "")
              for n, c in name_of.items()]
    lo, hi = 2, 4
    blocks = dict(course=course_meta.course_prompt(course), lecture_title=L["title"],
                  goal=L["goal"]["goal"] if L.get("goal") else "(none)", facts="\n".join(lines),
                  relations="\n".join(relation_lines(layer, rids, num)) or "(none)", concepts="\n".join(clines))
    u = Unit("open_question", k, None, f"open_question:{k}", {"shown": shown, "lo": lo, "hi": hi,
                                                               "names": name_of, "earlier": earlier, "blocks": blocks})
    prompt = fill("open_question", **blocks, count=count_text(lo, hi))
    cschema = {"type": "array", "items": {"type": "string", "enum": list(name_of)} if name_of else S}
    q = obj({"key_facts": nums_schema(len(shown), 2), "question": S, "reference_answer": S, "concepts": cschema})
    u.request = request(u, prompt, obj({"questions": arr(q, lo, hi)}), seed)
    return u


def open_item(q, ctx) -> list[str]:
    if not isinstance(q, dict):
        return ["it is not an object"]
    p = []
    if not txt(q.get("question")):
        p.append("the question is empty.")
    if not txt(q.get("reference_answer")):
        p.append("the reference answer is empty.")
    p += fact_problems(q.get("key_facts"), len(ctx["shown"]), least=2, name="key_facts")
    bad = [c for c in (q.get("concepts") or []) if c not in ctx["names"]]
    if bad:
        p.append(f'"concepts" has {bad}, not in the list of concepts: use the names exactly as listed.')
    return p


def open_soft(q) -> list[tuple[str, str]]:
    if not isinstance(q, dict):
        return []
    question, ref, out = txt(q.get("question")), txt(q.get("reference_answer")), []
    m = TWO_QUESTIONS.search(question)
    if question.count("?") > 1:
        out.append(("two_questions", f"asks two things (it has {question.count('?')} question marks). Ask one of "
                                     f"them."))
    elif m:
        out.append(("two_questions", f'asks two things ("... and {m[1].lower()} ..."). Ask one of them.'))
    n, ns = len(ref.split()), len(sentences(ref)) if ref else 0
    if n > 100 or ns > 4:
        out.append(("reference_long", f"the reference answer has {n} words. Give the direct answer first and the "
                                      f"support after it, in two to four sentences of about eighty words in all."))
    return out + source_talk("the question", question) + source_talk("the reference answer", ref)


def open_problems(answer, ctx) -> list[str]:
    qs = items_of(answer, "questions")
    p = count_problem(qs, ctx["lo"], ctx["hi"], "questions")
    rep = repeats([txt(q.get("question")) for q in qs if isinstance(q, dict)])
    if rep:
        p.append(f"Questions repeat: {rep}. Each question asks about a different point.")
    for i, q in enumerate(qs, 1):
        p += [f"Question {i}: {m}" for m in open_item(q, ctx)]
        p += [f"Question {i} {m}" if m.startswith("asks ") else f"Question {i}: {m}" for _, m in open_soft(q)]
    return p


def open_convert(answer, ctx, layer: Layer, unit: Unit):
    shown, out, dropped, flags, src = ctx["shown"], [], [], {}, []
    for i, q in enumerate(items_of(answer, "questions"), 1):
        p = open_item(q, ctx)
        if p:
            dropped.append({"item": i, "problems": p})
            continue
        facts = ids_of(q["key_facts"], shown)
        concepts = list(dict.fromkeys(ctx["names"][c] for c in q.get("concepts") or [])) or layer.fact_concepts(facts)
        out.append({"question": txt(q["question"]), "reference_answer": txt(q["reference_answer"]),
                    "key_facts": facts, "concepts": concepts})
        src.append(i)
        flag_soft(flags, open_soft(q), len(out))
        ref = set(content_tokens(out[-1]["reference_answer"]))
        if any(len(set(content_tokens(layer.facts[f]["text"])) & ref) < 3 for f in facts):
            flags.setdefault("key_fact_unused", []).append(len(out))
    ctx["_conv"] = {"src": src}
    if not out:
        return [], dropped, flags
    facts = list(dict.fromkeys(f for q in out for f in q["key_facts"]))
    rel_facts = {f for rid in layer.lectures[unit.lecture]["concept_map"]["relations"]
                 for f in layer.relations[rid]["facts"]}
    if not any(f in rel_facts or f in ctx["earlier"] for f in facts):
        flags["no_earlier_or_relation"] = True
    concepts = list(dict.fromkeys([c for q in out for c in q["concepts"]] + layer.fact_concepts(facts)))
    return [{"scope": "lecture", "segment": None, "data": {"questions": out}, "facts": facts,
             "concepts": concepts}], dropped, flags


# odd one out ----------------------------------------------------------
def odd_unit(layer: Layer, course: str, k: str, seed) -> Unit | None:
    L = layer.lectures[k]
    shown = layer.lecture_facts(k)[:LECTURE_FACTS_CAP]
    if len(shown) < 2:
        return None
    num = {f: i for i, f in enumerate(shown, 1)}
    names = {norm(x) for c in L["concept_map"]["concepts"] if c in layer.cards for x in layer.names(c)}
    blocks = dict(course=course_meta.course_prompt(course), lecture_title=L["title"],
                  concepts="\n".join(concept_line(layer, c, 20) for c in L["concept_map"]["concepts"]
                                     if c in layer.cards) or "(none)",
                  relations="\n".join(relation_lines(layer, L["concept_map"]["relations"], num)) or "(none)",
                  facts="\n".join(numbered(shown, layer)))
    u = Unit("odd_one_out", k, None, f"odd_one_out:{k}", {"shown": shown, "names": names, "blocks": blocks})
    prompt = fill("odd_one_out", **blocks)
    item = obj({"facts": nums_schema(len(shown)), "group": arr(S, 3, 3), "odd": S, "reason": S})
    u.request = request(u, prompt, obj({"items": arr(item, 0, 3)}), seed)
    return u


def odd_item(it, n: int) -> list[str]:
    if not isinstance(it, dict):
        return ["it is not an object"]
    p = []
    group = it.get("group") if isinstance(it.get("group"), list) else []
    if len(group) != 3:
        p.append(f'"group" has {len(group)} items: write exactly three.')
    opts = [txt(g) for g in group] + [txt(it.get("odd"))]
    if any(not o for o in opts):
        p.append("an item is empty.")
    rep = repeats(opts)
    if rep:
        p.append(f"the items repeat {rep}: the odd item and the three of the group must all be different.")
    if not txt(it.get("reason")):
        p.append("the reason is empty.")
    return p + fact_problems(it.get("facts"), n)


def odd_soft(it) -> list[tuple[str, str]]:
    if not isinstance(it, dict) or not isinstance(it.get("group"), list) or len(it["group"]) != 3:
        return []
    group, odd = [txt(g) for g in it["group"]], txt(it.get("odd"))
    out = []
    if all(group) and odd:
        words = lambda x: {w for w in re.findall(r"[a-z]+", x.lower()) if len(w) >= 4 and w not in ODD_STOP}  # noqa
        shared = sorted(words(group[0]) & words(group[1]) & words(group[2]) - words(odd))
        if shared:
            out.append(("shared_word", f'the three group items all contain "{shared[0]}" and the odd item does not, '
                                       f"so its form gives it away. Choose an odd item that carries the word too, or "
                                       f"use another group."))
        hi, lo = max(map(len, group)), min(map(len, group))
        if len(odd) > 1.5 * hi and len(odd) - hi >= 8:
            out.append(("length_tell", "the odd item is much longer than the three others. Write the four items "
                                       "alike."))
        elif len(odd) < 0.5 * lo and lo - len(odd) >= 8:
            out.append(("length_tell", "the odd item is much shorter than the three others. Write the four items "
                                       "alike."))
    return out + source_talk("the reason", txt(it.get("reason")))


def odd_same_items(its: list) -> dict[int, str]:
    """Hard: a later puzzle (1-based) that shares three or four items with an earlier one -> its problem."""
    sets, out = {}, {}
    for j, it in enumerate(its, 1):
        if not isinstance(it, dict) or not isinstance(it.get("group"), list):
            continue
        cur = {norm(txt(x)) for x in it["group"] + [it.get("odd")]} - {""}
        for i, prev in sets.items():
            if len(cur & prev) >= 3:
                out[j] = (f"Puzzles {i} and {j} show the same items with a different odd one. Use another group for "
                          f"puzzle {j}.")
                break
        sets[j] = cur
    return out


def odd_problems(answer, ctx) -> list[str]:
    its = items_of(answer, "items")
    p = count_problem(its, 0, 3, "puzzles")
    for i, it in enumerate(its, 1):
        p += [f"Puzzle {i}: {m}" for m in odd_item(it, len(ctx["shown"]))]
        p += [f"Puzzle {i}: {m}" for _, m in odd_soft(it)]
    return p + list(odd_same_items(its).values())


def capital(s: str) -> str:
    return s[:1].upper() + s[1:]


def odd_convert(answer, ctx, layer: Layer, unit: Unit):
    shown, out, dropped, flags, src = ctx["shown"], [], [], {}, []
    its = items_of(answer, "items")
    same = odd_same_items(its)
    for i, it in enumerate(its, 1):
        p = odd_item(it, len(shown)) + ([same[i]] if i in same else [])
        if p:
            dropped.append({"item": i, "problems": p})
            continue
        opts = [capital(txt(g)) for g in it["group"]] + [capital(txt(it["odd"]))]
        order = [0, 1, 2, 3]
        stable_rng(unit.key, *opts).shuffle(order)
        out.append({"options": [opts[j] for j in order], "odd": order.index(3), "reason": txt(it["reason"]),
                    "facts": ids_of(it["facts"], shown)})
        src.append(i)
        flag_soft(flags, odd_soft(it), len(out))
        unknown = [o for o in opts if norm(o) not in ctx["names"]]
        if unknown:
            flags.setdefault("not_a_concept", []).extend(unknown)
    ctx["_conv"] = {"src": src}
    if not out:
        return [], dropped, flags
    facts = list(dict.fromkeys(f for it in out for f in it["facts"]))
    return [{"scope": "lecture", "segment": None, "data": {"items": out}, "facts": facts,
             "concepts": layer.fact_concepts(facts)}], dropped, flags


# put in order ---------------------------------------------------------
def order_unit(layer: Layer, course: str, k: str, seed) -> Unit | None:
    L = layer.lectures[k]
    shown = layer.lecture_facts(k)[:LECTURE_FACTS_CAP]
    if not shown:
        return None
    lines, i = [], 1
    for j, (sid, seg) in enumerate(L["segments"].items(), 1):
        fs = [f for f in seg["facts"] if f in shown]
        if fs:
            lines += [f"Segment {j}: {seg['subgoal']}"] + numbered(fs, layer, start=i) + [""]
            i += len(fs)
    shown = [f for seg in L["segments"].values() for f in seg["facts"] if f in shown]
    blocks = dict(course=course_meta.course_prompt(course), lecture_title=L["title"], facts="\n".join(lines).strip())
    u = Unit("put_in_order", k, None, f"put_in_order:{k}", {"shown": shown, "blocks": blocks})
    prompt = fill("put_in_order", **blocks)
    item = obj({"facts": nums_schema(len(shown)), "title": S, "steps": arr(S, 3, 8)})
    u.request = request(u, prompt, obj({"items": arr(item, 0, 2)}), seed)
    return u


def order_item(it, n: int) -> list[str]:
    if not isinstance(it, dict):
        return ["it is not an object"]
    p = [] if txt(it.get("title")) else ["the title is empty."]
    steps = it.get("steps") if isinstance(it.get("steps"), list) else []
    if not 3 <= len(steps) <= 8:
        p.append(f"there are {len(steps)} steps: write three to eight.")
    if any(not txt(s) for s in steps):
        p.append("a step is empty.")
    rep = repeats([txt(s) for s in steps])
    if rep:
        p.append(f"the steps repeat {rep}: every step must be different.")
    return p + fact_problems(it.get("facts"), n)


def order_soft(it) -> list[tuple[str, str]]:
    if not isinstance(it, dict):
        return []
    steps = [txt(x) for x in it.get("steps")] if isinstance(it.get("steps"), list) else []
    out = [("order_cue", f'the step "{x}" carries an order word or a year, which sorts it without understanding. Say '
                         f"what happens in the step without it.")
           for x in steps if x and (ORDER_CUE.match(x) or YEAR.search(x) or PREVIOUS_STEP.search(x))]
    out += source_talk("the title", txt(it.get("title")))
    for j, x in enumerate(steps, 1):
        out += source_talk(f"step {j}", x)
    return out


def order_problems(answer, ctx) -> list[str]:
    its = items_of(answer, "items")
    p = count_problem(its, 0, 2, "exercises")
    for i, it in enumerate(its, 1):
        p += [f"Exercise {i}: {m}" for m in order_item(it, len(ctx["shown"]))]
        p += [f"Exercise {i}: {m}" for _, m in order_soft(it)]
    return p


def order_convert(answer, ctx, layer: Layer, unit: Unit):
    shown, groups, dropped, flags = ctx["shown"], {}, [], {}
    for i, it in enumerate(items_of(answer, "items"), 1):
        p = order_item(it, len(shown))
        if p:
            dropped.append({"item": i, "problems": p})
            continue
        facts = ids_of(it["facts"], shown)
        steps = [txt(s) for s in it["steps"]]
        segs = {layer.facts[f]["segment"] for f in facts}
        where = segs.pop() if len(segs) == 1 else None
        groups.setdefault(where, []).append(({"title": txt(it["title"]), "steps": steps, "facts": facts}, i, it))
    out, src = [], []
    for where, items in groups.items():           # judge numbering: the items in this order, 1-based
        for item, i, it in items:
            src.append(i)
            pos = len(src)
            flag_soft(flags, order_soft(it), pos)
            if TITLE_CUE.search(item["title"]):
                flags.setdefault("title_cue", []).append(pos)
            if not any(ORDER_WORD.search(layer.facts[f]["text"]) for f in item["facts"]):
                flags.setdefault("no_order_word", []).append(pos)
            if len(item["steps"]) == 3:
                flags.setdefault("three_steps", []).append(pos)
        items = [x[0] for x in items]
        facts = list(dict.fromkeys(f for it in items for f in it["facts"]))
        out.append({"scope": "segment" if where else "lecture", "segment": where,
                    "title": items[0]["title"] if len(items) == 1 else None,
                    "data": {"items": items}, "facts": facts, "concepts": layer.fact_concepts(facts)})
    ctx["_conv"] = {"src": src}
    return out, dropped, flags


# crossword ------------------------------------------------------------
def crossword_candidates(layer: Layer, k: str) -> tuple[list[tuple[str, str]], bool]:
    """[(answer letters, concept)] in order of preference, and whether concepts the lecture only uses were added."""
    L = layer.lectures[k]
    used = [c for c in L["concept_map"]["concepts"] if c in layer.cards and layer.has_definition(c)]
    here = [c for c in used if layer.defined_here(c, k)]

    def ok(cids):
        out, seen = [], set()
        for c in cids:
            name = layer.cards[c]["name"]
            a = letters(name)
            if re.search(r"\d", name) or not 3 <= len(a) <= 15 or a in seen or not layer.definition_facts(c):
                continue
            seen.add(a)
            out.append((a, c))
        return out
    cands = ok(here)
    filled = False
    if len(cands) < CROSS_WANT:
        more = ok(here + [c for c in used if c not in here])
        filled = len(more) > len(cands)
        cands = more
    return cands[:CROSS_CANDIDATES], filled


def _place(order: list[tuple[str, str]]):
    grid, dirs, placed = {}, {}, []
    D = {"across": (0, 1), "down": (1, 0)}

    def put(word, r, c, d, cid):
        dr, dc = D[d]
        for i, ch in enumerate(word):
            cell = (r + i * dr, c + i * dc)
            grid[cell] = ch
            dirs.setdefault(cell, set()).add(d)
        placed.append((word, r, c, d, cid))

    def fits(word, r, c, d) -> int:
        dr, dc = D[d]
        if (r - dr, c - dc) in grid or (r + len(word) * dr, c + len(word) * dc) in grid:
            return -1
        cross = 0
        for i, ch in enumerate(word):
            cell = (r + i * dr, c + i * dc)
            if cell in grid:
                if grid[cell] != ch or d in dirs[cell]:
                    return -1
                cross += 1
            else:
                side = [(cell[0] + dc, cell[1] + dr), (cell[0] - dc, cell[1] - dr)]
                if any(s in grid for s in side):
                    return -1
        return cross

    word, cid = order[0]
    put(word, 0, 0, "across", cid)
    for word, cid in order[1:]:
        if len(placed) >= CROSS_MAX:
            break
        best = None
        for (r0, c0), ch in list(grid.items()):
            for i, w in enumerate(word):
                if w != ch:
                    continue
                for d in ("across", "down"):
                    dr, dc = D[d]
                    r, c = r0 - i * dr, c0 - i * dc
                    n = fits(word, r, c, d)
                    if n <= 0:
                        continue
                    cells = list(grid) + [(r + j * dr, c + j * dc) for j in range(len(word))]
                    rows, cols = [x[0] for x in cells], [x[1] for x in cells]
                    area = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
                    score = (n, -area, -r, -c, d == "across")
                    if best is None or score > best[0]:
                        best = (score, r, c, d)
        if best:
            put(word, best[1], best[2], best[3], cid)
    rows = [r + (len(w) - 1 if d == "down" else 0) for w, r, c, d, _ in placed] + [r for _, r, _, _, _ in placed]
    cols = [c + (len(w) - 1 if d == "across" else 0) for w, r, c, d, _ in placed] + [c for _, _, c, _, _ in placed]
    area = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
    crossings = sum(len(v) > 1 for v in dirs.values())
    return (len(placed), crossings, -area), placed


def crossword_layout(cands: list[tuple[str, str]]) -> dict | None:
    """The best greedy layout over several first words: {"width", "height", "entries": [{number, answer, row,
    col, direction, concept}]} with 0-based rows and columns, numbered in reading order; None below CROSS_MIN."""
    if len(cands) < CROSS_MIN:
        return None
    best = None
    by_len = sorted(cands, key=lambda x: (-len(x[0]), x[0]))
    for first in by_len[:6]:
        order = [first] + [x for x in by_len if x != first]
        score, placed = _place(order)
        if best is None or score > best[0]:
            best = (score, placed)
    placed = best[1]
    if len(placed) < CROSS_MIN:
        return None
    r0 = min(r for _, r, _, _, _ in placed)
    c0 = min(c for _, _, c, _, _ in placed)
    entries = [{"answer": w, "row": r - r0, "col": c - c0, "direction": d, "concept": cid}
               for w, r, c, d, cid in placed]
    starts = sorted({(e["row"], e["col"]) for e in entries})
    num = {s: i for i, s in enumerate(starts, 1)}
    for e in entries:
        e["number"] = num[(e["row"], e["col"])]
    entries.sort(key=lambda e: (e["direction"] != "across", e["number"]))
    height = max(e["row"] + (len(e["answer"]) if e["direction"] == "down" else 1) for e in entries)
    width = max(e["col"] + (len(e["answer"]) if e["direction"] == "across" else 1) for e in entries)
    return {"width": width, "height": height, "entries": entries}


def crossword_unit(layer: Layer, course: str, k: str, seed) -> Unit | None:
    cands, filled = crossword_candidates(layer, k)
    grid = crossword_layout(cands)
    if grid is None:
        return Unit("crossword", k, None, f"crossword:{k}", {"skip": f"{len(cands)} candidate answers, too few "
                                                                       f"placed (need {CROSS_MIN})"})
    entries = grid["entries"]
    words = [term_words(layer.names(e["concept"])) for e in entries]
    u = Unit("crossword", k, None, f"crossword:{k}", {"grid": grid, "words": words, "filled": filled,
                                                       "candidates": len(cands)})
    lines = []
    for i, e in enumerate(entries, 1):
        c = layer.cards[e["concept"]]
        other = ", ".join(x for x in layer.names(e["concept"]) if x != c["name"]) or "none"
        lines.append(f"[{i}] {c['name']} (other names: {other}). Definition: {c['definition'].strip()}")
    u.ctx["blocks"] = dict(course=course_meta.course_prompt(course), lecture_title=layer.lectures[k]["title"],
                           answers="\n".join(lines))
    prompt = fill("crossword", **u.ctx["blocks"])
    n = len(entries)
    clue = obj({"number": {"type": "integer", "minimum": 1, "maximum": n}, "clue": S})
    u.request = request(u, prompt, obj({"clues": arr(clue, n, n)}), seed)
    return u


def clue_item(cl, ctx) -> list[str]:
    n = len(ctx["grid"]["entries"])
    if not isinstance(cl, dict):
        return ["it is not an object"]
    i = cl.get("number")
    if not isinstance(i, int) or not 1 <= i <= n:
        return [f"the number {i} is not an answer: use 1 to {n}."]
    clue = txt(cl.get("clue"))
    if not clue:
        return ["the clue is empty."]
    p = []
    found = words_in(clue, ctx["words"][i - 1])
    if found:
        p.append(f"the clue writes {found}, words of the answer or its other names: say it in other words.")
    if len(clue.split()) > CLUE_MAX_WORDS:
        p.append(f"the clue has {len(clue.split())} words: at most fifteen.")
    return p


def clue_soft(cl) -> list[tuple[str, str]]:
    clue = txt(cl.get("clue")) if isinstance(cl, dict) else ""
    out = []
    for pat in LIST_PLACE:
        m = pat.search(clue)
        if m:
            out.append(("clue_list_place", f'"{m[0]}" only says where the answer stands in a list. Say what the thing '
                                           f"is or does."))
            break
    return out + source_talk("the clue", clue)


def clue_same(cls: list) -> dict[int, str]:
    """Hard: an answer (its number) whose clue is the same as an earlier answer's -> its problem."""
    seen, out = {}, {}
    for cl in cls:
        if not isinstance(cl, dict) or not isinstance(cl.get("number"), int) or not norm(txt(cl.get("clue"))):
            continue
        key, j = norm(strip_stop(txt(cl["clue"]))), cl["number"]
        if key in seen and seen[key] != j:
            out.setdefault(j, f"Answers {seen[key]} and {j} have the same clue. Give each the detail that tells it "
                              f"apart from the other.")
        seen.setdefault(key, j)
    return out


def crossword_problems(answer, ctx) -> list[str]:
    cls = items_of(answer, "clues")
    n = len(ctx["grid"]["entries"])
    nums = [c.get("number") for c in cls if isinstance(c, dict)]
    p = []
    missing = [i for i in range(1, n + 1) if i not in nums]
    twice = sorted({i for i in nums if nums.count(i) > 1})
    if missing:
        p.append(f"No clue for the answers {missing}: write one clue per answer.")
    if twice:
        p.append(f"The answers {twice} have more than one clue: write one clue per answer.")
    for j, cl in enumerate(cls, 1):
        w = f"Clue {cl.get('number', j) if isinstance(cl, dict) else j}"
        p += [f"{w}: {m}" for m in clue_item(cl, ctx)]
        p += [f"{w}: {m}" for _, m in clue_soft(cl)]
    return p + list(clue_same(cls).values())


def mask_name(clue: str, name: str) -> str:
    """The answer's own name and its plain forms (plural, "-ed", "-ing") replaced by "___"; not its other names and
    not longer words built on a word of it (the code check rejects those, the judge reads the clue)."""
    clue = mask_terms(clue, [name])
    for w in sorted({w for w in norm(name).split() if w not in STOP}, key=len, reverse=True):
        clue = re.sub(r"(?i)(?<![A-Za-z0-9])" + re.escape(w) + r"(?:s|es|d|ed|ing)?(?![A-Za-z0-9])", "___", clue)
    return clue


def crossword_convert(answer, ctx, layer: Layer, unit: Unit):
    grid, dropped, flags = ctx["grid"], [], {}
    clues = {}
    cls = items_of(answer, "clues")
    same = clue_same(cls)
    for j, cl in enumerate(cls, 1):
        p = clue_item(cl, ctx)
        i = cl.get("number") if isinstance(cl, dict) else None
        if isinstance(i, int) and i in same:
            p.append(same[i])
        if p and isinstance(i, int) and 1 <= i <= len(grid["entries"]) and txt(cl.get("clue")) \
                and all(m.startswith("the clue writes") or m.startswith("the clue has") for m in p):
            name = layer.cards[grid["entries"][i - 1]["concept"]]["name"]
            masked = cap_words(mask_name(strip_stop(txt(cl["clue"])), name), CLUE_MAX_WORDS)
            if i not in clues:
                clues[i] = masked
                flag_soft(flags, clue_soft(cl), i)
            flags.setdefault("clue_masked", []).append(i)
        elif p:
            dropped.append({"item": j, "problems": p})
        elif i not in clues:
            clues[i] = strip_stop(txt(cl["clue"]))
            flag_soft(flags, clue_soft(cl), i)
    entries = []
    for i, e in enumerate(grid["entries"], 1):
        c = layer.cards[e["concept"]]
        clue = clues.get(i)
        if clue is None:
            clue = strip_stop(short_definition(c["definition"], layer.names(e["concept"]), 15))
            flags.setdefault("clue_from_definition", []).append(i)
        if POINTING.search(clue):
            flags.setdefault("clue_points", []).append(i)
        entries.append({"number": e["number"], "answer": e["answer"], "clue": f"{clue} {enumeration(c['name'])}",
                        "row": e["row"], "col": e["col"], "direction": e["direction"], "concept": e["concept"],
                        "facts": layer.definition_facts(e["concept"])})
    if len(entries) < CROSS_WANT:
        flags["small"] = len(entries)
    if ctx["filled"]:
        flags["filled_from_used"] = True
    ctx["_conv"] = {"src": list(range(1, len(entries) + 1))}
    concepts = [e["concept"] for e in entries]
    facts = list(dict.fromkeys(f for c in concepts for f in layer.definition_facts(c)))
    return [{"scope": "lecture", "segment": None, "data": {"width": grid["width"], "height": grid["height"],
                                                           "entries": entries},
             "facts": facts, "concepts": concepts}], dropped, flags


UNITS = {"quiz": quiz_unit, "recap": recap_unit}
LECTURE_UNITS = {"put_in_order": order_unit, "crossword": crossword_unit, "odd_one_out": odd_unit,
                 "open_question": open_unit}
PROBLEMS = {"quiz": quiz_problems, "recap": recap_problems, "open_question": open_problems,
            "odd_one_out": odd_problems, "put_in_order": order_problems, "crossword": crossword_problems}
CONVERT = {"quiz": quiz_convert, "recap": recap_convert, "open_question": open_convert, "odd_one_out": odd_convert,
           "put_in_order": order_convert, "crossword": crossword_convert}


# ---------------------------------------------------------------- the judge (--judge, --judge-rewrite)
# One call per unit (the writer's units) after the code checks, with prompts/activity_judge_<kind>.txt: the writer's
# blocks (same fact numbers) and the items as they came out of *_convert, numbered 1.. in that order (recap: the
# points, and 0 for the text). On a fail and with --judge-rewrite: one rewrite (the writer's conversation goes on with
# its kept answer and prompts/activity_rewrite.txt, {problems} one line per failed item with the judge's reason, in the
# writer's numbering), the code checks again (the client's retry loop), the judge once more; the rewrite is kept only
# when it is judged with strictly fewer failed items. Nothing is dropped on a verdict: items that still fail are kept
# and flagged "judge_failed" (the judge is to be measured first, review section 8).
JUDGE_CRITERIA = {
    "quiz": ["answerable", "one_answer", "no_giveaway", "worth_asking", "clear", "no_source_talk"],
    "recap": ["supported", "faithful", "stands_alone", "clear", "no_source_talk", "one_idea", "summary", "coverage"],
    "put_in_order": ["in_facts", "real_sequence", "one_order", "no_giveaway", "worth_doing", "clear", "no_source_talk"],
    "odd_one_out": ["in_facts", "real_group", "near_miss", "one_answer", "no_giveaway", "clear", "no_source_talk"],
    "open_question": ["answerable", "answers_question", "open", "one_thread", "no_giveaway", "clear",
                      "no_source_talk"],
    "crossword": ["from_text", "leads_to_answer", "unique", "no_giveaway", "readable", "no_source_talk"]}
JUDGE_ITEMS = {"quiz": "questions", "recap": "recap", "put_in_order": "exercises", "odd_one_out": "puzzles",
               "open_question": "questions", "crossword": "clues"}
JUDGE_LABEL = {"quiz": "Question", "recap": "Point", "put_in_order": "Exercise", "odd_one_out": "Puzzle",
               "open_question": "Question", "crossword": "Clue"}


def _nums(fids: list[str], shown: list[str]) -> str:
    num = {f: i for i, f in enumerate(shown, 1)}
    return ", ".join(str(num[f]) for f in fids if f in num)


def judge_items(unit: Unit, acts: list[dict], conv: dict, layer: Layer) -> list[tuple[int, str, str]]:
    """[(item number, its block for the judge prompt, a short text for checks.json)] in judge order."""
    shown, kind, out = unit.ctx.get("shown", []), unit.kind, []
    if kind == "quiz":
        for j, q in enumerate(acts[0]["data"]["questions"], 1):
            lines = [f"Question {j} (cites facts {_nums(q['facts'], shown)})", q["question"]]
            lines += [f"{'ABCD'[x]}. {o}" for x, o in enumerate(q["options"])]
            lines += [f"Marked correct: {'ABCD'[q['answer']]}", f"Explanation: {q['explanation']}"]
            out.append((j, "\n".join(lines), q["question"]))
    elif kind == "recap":
        d, pf = acts[0]["data"], conv.get("point_facts") or []
        for j, pt in enumerate(d["points"], 1):
            fs = pf[j - 1] if j - 1 < len(pf) else []
            out.append((j, f"Point {j} (cites facts {_nums(fs, shown)}): {pt}", pt))
        out.append((0, f"Text: {d['text']}", d["text"]))
    elif kind == "put_in_order":
        j = 0
        for a in acts:
            for it in a["data"]["items"]:
                j += 1
                lines = [f"Exercise {j} (cites facts {_nums(it['facts'], shown)})", f"Title: {it['title']}"]
                lines += [f"{x}. {st}" for x, st in enumerate(it["steps"], 1)]
                out.append((j, "\n".join(lines), it["title"]))
    elif kind == "odd_one_out":
        for j, it in enumerate(acts[0]["data"]["items"], 1):
            lines = [f"Puzzle {j} (cites facts {_nums(it['facts'], shown)})"] + [f"- {o}" for o in it["options"]]
            lines += [f"Marked as odd: {it['options'][it['odd']]}", f"Reason: {it['reason']}"]
            out.append((j, "\n".join(lines), " | ".join(it["options"])))
    elif kind == "open_question":
        for j, q in enumerate(acts[0]["data"]["questions"], 1):
            lines = [f"Question {j} (key facts {_nums(q['key_facts'], shown)})", f"Question: {q['question']}",
                     f"Reference answer: {q['reference_answer']}"]
            out.append((j, "\n".join(lines), q["question"]))
    elif kind == "crossword":
        for j, e in enumerate(acts[0]["data"]["entries"], 1):
            name = layer.cards[e["concept"]]["name"]
            enum = enumeration(name)
            clue = e["clue"][:-len(enum) - 1] if e["clue"].endswith(" " + enum) else e["clue"]
            out.append((j, f"[{j}] {name} {enum}: {clue}", f"{name}: {clue}"))
    return out


def judge_problems(answer, expect: list[int], crit: list[str]) -> list[str]:
    vs = items_of(answer, "verdicts")
    got = [v.get("item") for v in vs if isinstance(v, dict)]
    p = []
    missing = [i for i in expect if i not in got]
    extra = sorted({i for i in got if i not in expect}, key=str)
    twice = sorted({i for i in got if got.count(i) > 1 and i in expect})
    if missing:
        p.append(f"No verdict for the items {missing}: give one verdict per item.")
    if extra:
        p.append(f"Verdicts for {extra}, which are not items: use the item numbers given.")
    if twice:
        p.append(f"The items {twice} have more than one verdict: give one verdict per item.")
    for v in vs:
        if not isinstance(v, dict):
            p.append("A verdict is not an object.")
            continue
        i, failed = v.get("item"), v.get("failed") if isinstance(v.get("failed"), list) else []
        bad = [c for c in failed if c not in crit]
        if bad:
            p.append(f'Item {i}: "failed" has {bad}, not criteria: use only {", ".join(crit)}.')
        if v.get("pass") is not (not failed):
            p.append(f'Item {i}: "pass" is {json.dumps(v.get("pass"))} and "failed" is {json.dumps(failed)}: '
                     f'"pass" is true exactly when "failed" is empty.')
        if failed and not txt(v.get("reason")):
            p.append(f'Item {i}: it fails {failed} but "reason" is empty: say what is wrong.')
    return p


def judge_request(unit: Unit, items: list[tuple[int, str, str]], rnd: int, seed) -> Request:
    template = (PROMPTS / f"activity_judge_{unit.kind}.txt").read_text()
    values = {k: v for k, v in unit.ctx["blocks"].items() if "{" + k + "}" in template}
    values[JUDGE_ITEMS[unit.kind]] = "\n\n".join(b for _, b, _ in items)
    prompt = s4a.fill(template, **values)
    expect, crit = [i for i, _, _ in items], JUDGE_CRITERIA[unit.kind]
    v = obj({"item": {"type": "integer", "minimum": min(expect), "maximum": max(expect)}, "check": S, "reason": S,
             "failed": {"type": "array", "items": {"type": "string", "enum": crit}}, "pass": {"type": "boolean"}})
    return Request(prompt=prompt, key=f"judge{rnd}:{unit.key}", schema=obj({"verdicts": arr(v, len(items), len(items))}),
                   check=lambda a, e=expect, c=crit: judge_problems(a, e, c), feedback=True,
                   sampling={} if seed is None else {"seed": seed},
                   meta={"kind": unit.kind, "lecture": unit.lecture, "segment": unit.segment, "judge": rnd})


def judge_round(res, items: list[tuple[int, str, str]]) -> dict:
    """The judge's answer as recorded in checks.json: status, verdicts in item order, the failed items."""
    rnd = {}
    if res.history:
        rnd["retry"] = {"attempts": res.attempts, "problems": [h["errors"] for h in res.history]}
    if not s4a.answered(res):
        rnd.update(status="no_answer", problems=res.errors)
        return rnd
    rnd["status"] = "ok" if res.ok else "unresolved"
    if not res.ok:
        rnd["problems"] = res.errors
    by = {}
    for v in items_of(res.parsed, "verdicts"):
        if isinstance(v, dict):
            by.setdefault(v.get("item"), v)
    verdicts = []
    for i, _, about in items:
        v = by.get(i)
        if v is None:
            verdicts.append({"item": i, "about": short(about, 14), "missing": True})
            continue
        failed = [c for c in v.get("failed") or [] if isinstance(c, str)]
        ok = not failed and v.get("pass") is not False
        verdicts.append({"item": i, "about": short(about, 14), "pass": ok, "failed": failed,
                         "check": txt(v.get("check")), "reason": txt(v.get("reason"))})
    rnd["verdicts"] = verdicts
    rnd["failed_items"] = [v["item"] for v in verdicts if v.get("pass") is False]
    return rnd


def rewrite_request(unit: Unit, res, rnd: dict, conv: dict) -> Request:
    src, label = conv.get("src") or [], JUDGE_LABEL[unit.kind]
    lines = []
    for v in rnd["verdicts"]:
        if v.get("pass") is not False:
            continue
        i = v["item"]
        who = "The text" if unit.kind == "recap" and i == 0 else \
            f"{label} {src[i - 1] if 0 < i <= len(src) else i}"
        lines.append(f"{who} ({', '.join(v['failed']) or 'failed'}): {v['reason'] or 'no reason given'}")
    msg = s4a.fill((PROMPTS / "activity_rewrite.txt").read_text(), problems="\n".join(lines))
    r0 = unit.request
    return Request(prompt=r0.prompt, key=f"rewrite:{unit.key}", schema=r0.schema, check=r0.check, feedback=True,
                   sampling=dict(r0.sampling), meta={**r0.meta, "rewrite": True},
                   followup=[{"role": "assistant", "content": res.content}, {"role": "user", "content": msg}])


# ---------------------------------------------------------------- code-made kinds
def make_recall(layer: Layer, k: str):
    items, facts = [], []
    for c in needed_concepts(layer, k):
        if len(items) >= RECALL_CAP:
            break
        df = layer.definition_facts(c)
        if not layer.has_definition(c) or not df:
            continue
        card = layer.cards[c]
        acr = [a for a in card.get("acronyms", []) if a.lower() not in card["name"].lower()]
        items.append({"concept": c, "prompt": f"What is {card['name']}" + (f" ({acr[0]})" if acr else "") + "?",
                      "answer": card["definition"].strip(), "from_lecture": card["first_defined"]})
        facts += df
    if not items:
        return None, "no concept needed from an earlier lecture with a definition"
    return {"scope": "lecture", "segment": None, "data": {"items": items}, "facts": list(dict.fromkeys(facts)),
            "concepts": [i["concept"] for i in items]}, None


def map_parts(layer: Layer, k: str):
    L = layer.lectures[k]
    rids = [r for r in L["concept_map"]["relations"] if r in layer.relations
            and layer.relations[r]["subject"] in layer.cards and layer.relations[r]["object"] in layer.cards]
    ends = [c for r in rids for c in (layer.relations[r]["subject"], layer.relations[r]["object"])]
    intro = [c for c in L["concepts"].get("introduced", []) if c in layer.cards]
    nodes = [{"id": c, "label": layer.cards[c]["name"]} for c in dict.fromkeys(ends + intro)]
    edges = [{"from": layer.relations[r]["subject"], "to": layer.relations[r]["object"],
              "label": layer.relations[r]["label"], "relation": r,
              "facts": [f for f in layer.relations[r]["facts"] if f in layer.facts]} for r in rids]
    facts = list(dict.fromkeys(f for r in rids for f in layer.relations[r]["facts"] if f in layer.facts))
    return nodes, edges, facts


def make_concept_map(layer: Layer, k: str):
    nodes, edges, facts = map_parts(layer, k)
    if not edges:
        return None, "the lecture has no relationship"
    return {"scope": "lecture", "segment": None, "data": {"nodes": nodes, "edges": edges}, "facts": facts,
            "concepts": [n["id"] for n in nodes]}, None


def make_complete_map(layer: Layer, k: str):
    nodes, edges, facts = map_parts(layer, k)
    if len(edges) < 2:
        return None, f"{len(edges)} relationship(s): a map to complete needs two"
    label_of = {n["id"]: n["label"] for n in nodes}
    pool = list(dict.fromkeys([n["label"] for n in nodes] + [layer.cards[c]["name"] for c in
                                                             layer.lectures[k]["concept_map"]["concepts"]
                                                             if c in layer.cards]))
    labels = list(dict.fromkeys(e["label"] for e in edges))
    rng = stable_rng("complete_map", k)
    order = list(range(len(edges)))
    rng.shuffle(order)
    blanks = []
    for n_, i in enumerate(order):
        if len(blanks) >= BLANKS_CAP:
            break
        e = edges[i]
        tries = ["label", "to", "from"] if n_ % 2 == 0 else ["to", "from", "label"]
        for hide in tries:
            if hide == "label":
                same_pair = {x["label"] for x in edges if {x["from"], x["to"]} == {e["from"], e["to"]}}
                answer, wrong = e["label"], [x for x in labels if x not in same_pair]
            else:
                if sum(e[hide] in (x["from"], x["to"]) for x in edges) > 1:
                    continue                       # the concept would be visible on another edge
                other = "from" if hide == "to" else "to"
                right = {label_of[x[hide]] for x in edges if x[other] == e[other] and x["label"] == e["label"]}
                answer, wrong = label_of[e[hide]], [x for x in pool if x not in right]
            wrong = [w for w in wrong if norm(w) != norm(answer)]
            if len(wrong) < 2:
                continue
            rng.shuffle(wrong)
            options = [answer] + wrong[:3]
            rng.shuffle(options)
            blanks.append({"edge": i, "hide": hide, "answer": answer, "options": options})
            break
    if not blanks:
        return None, "no blank with enough wrong options"
    blanks.sort(key=lambda b: b["edge"])
    return {"scope": "lecture", "segment": None, "data": {"nodes": nodes, "edges": edges, "blanks": blanks},
            "facts": facts, "concepts": [n["id"] for n in nodes]}, None


def make_match_pairs(layer: Layer, k: str):
    L = layer.lectures[k]
    used = [c for c in L["concept_map"]["concepts"] if c in layer.cards and layer.has_definition(c)
            and layer.definition_facts(c)]
    order = [c for c in used if layer.defined_here(c, k)] + [c for c in used if not layer.defined_here(c, k)]
    pairs, lefts, rights = [], set(), set()
    for c in order:
        if len(pairs) >= PAIRS_CAP:
            break
        left = layer.cards[c]["name"]
        right = short_definition(layer.cards[c]["definition"], layer.names(c))
        if norm(left) in lefts or norm(right) in rights or not norm(right.replace("___", "")):
            continue
        lefts.add(norm(left))
        rights.add(norm(right))
        pairs.append({"left": left, "right": right, "concept": c, "facts": layer.definition_facts(c)})
    if len(pairs) < 3:
        return None, f"{len(pairs)} concept(s) with a definition: match pairs needs three"
    concepts = [p["concept"] for p in pairs]
    return {"scope": "lecture", "segment": None, "data": {"pairs": pairs},
            "facts": list(dict.fromkeys(f for c in concepts for f in layer.definition_facts(c))),
            "concepts": concepts}, None


CODE_MAKERS = {"recall": make_recall, "concept_map": make_concept_map, "complete_map": make_complete_map,
               "match_pairs": make_match_pairs}


def spaced_review(layer: Layer) -> dict:
    cards = []
    cids = [c for c in layer.cards if layer.has_definition(c)]
    first = lambda c: layer.cards[c].get("first_defined") or (layer.cards[c].get("lectures") or [None])[0]  # noqa
    cids.sort(key=lambda c: (lec.order(first(c)) if first(c) else (9,), c))
    for c in cids:
        card = layer.cards[c]
        acr = [a for a in card.get("acronyms", []) if a.lower() not in card["name"].lower()]
        cards.append({"concept": c, "front": card["name"] + (f" ({acr[0]})" if acr else ""),
                      "back": card["definition"].strip(),
                      "lectures": sorted([k for k in card.get("lectures", []) if k in layer.keys], key=lec.order)})
    return {"spaced_review": {"cards": cards}}


# ---------------------------------------------------------------- the contract check
ACT_FIELDS = ["id", "kind", "scope", "segment", "title", "data", "facts", "concepts"]


def validate(od: Path, layer: Layer) -> list[str]:
    """Every file of an activities/ folder against schemas/activities.md and the layer; [] when all is well."""
    P: list[str] = []
    files = sorted(od.glob("lec_*.json")) + sorted(od.glob("tut_*.json"))
    for p in files:
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            P.append(f"{p.name}: not JSON ({e})")
            continue
        k = lec.key_of(p.stem)
        if not isinstance(d, dict) or set(d) != {"lecture", "activities"} or d.get("lecture") != k \
                or not isinstance(d.get("activities"), list):
            P.append(f"{p.name}: not {{'lecture': '{k}', 'activities': [...]}}")
            continue
        segs = layer.lectures.get(k, {}).get("segments", {})
        ids = []
        for j, a in enumerate(d["activities"]):
            where = f"{p.name} #{j}"
            if not isinstance(a, dict) or list(a) != ACT_FIELDS:
                P.append(f"{where}: fields {list(a) if isinstance(a, dict) else type(a).__name__}, not {ACT_FIELDS}")
                continue
            where = f"{p.name} {a['id']}"
            ids.append(a["id"])
            if a["id"] != f"{k}/A{j}":
                P.append(f"{where}: id not {k}/A{j}")
            kind = a["kind"]
            if kind not in KINDS or kind == "spaced_review":
                P.append(f"{where}: unknown kind {kind!r}")
                continue
            scopes = SCOPES.get(kind, {"lecture"})
            if a["scope"] not in scopes:
                P.append(f"{where}: scope {a['scope']!r} for {kind}")
            if a["scope"] == "segment" and a["segment"] not in segs:
                P.append(f"{where}: segment {a['segment']!r} not a segment of lecture {k}")
            if a["scope"] == "lecture" and a["segment"] is not None:
                P.append(f"{where}: lecture scope with segment {a['segment']!r}")
            if not txt(a["title"]):
                P.append(f"{where}: empty title")
            for name in ("facts", "concepts"):
                if not isinstance(a[name], list) or not all(isinstance(x, str) for x in a[name]):
                    P.append(f"{where}: {name} not a list of IDs")
            if not isinstance(a["facts"], list) or not isinstance(a["concepts"], list):
                continue
            P += [f"{where}: unknown fact {f}" for f in a["facts"] if f not in layer.facts]
            P += [f"{where}: unknown concept {c}" for c in a["concepts"] if c not in layer.cards]
            if not a["facts"]:
                P.append(f"{where}: no facts (every activity is built from facts)")
            if not a["concepts"]:
                P.append(f"{where}: no concepts")
            try:
                P += [f"{where}: {m}" for m in validate_data(kind, a["data"], set(a["facts"]), layer, k)]
            except (KeyError, TypeError, AttributeError, IndexError, ValueError) as e:
                P.append(f"{where}: malformed data ({type(e).__name__}: {e})")
        if len(set(ids)) != len(ids):
            P.append(f"{p.name}: repeated activity IDs")
    cp = od / "course.json"
    if cp.exists():
        try:
            d = json.loads(cp.read_text())
            cards = d["spaced_review"]["cards"]
            if set(d) != {"spaced_review"} or set(d["spaced_review"]) != {"cards"}:
                P.append("course.json: fields other than spaced_review.cards")
            for c in cards:
                if set(c) != {"concept", "front", "back", "lectures"}:
                    P.append(f"course.json: card fields {sorted(c)}")
                if c.get("concept") not in layer.cards:
                    P.append(f"course.json: unknown concept {c.get('concept')}")
                if not txt(c.get("front")) or not txt(c.get("back")):
                    P.append(f"course.json: card {c.get('concept')} with an empty side")
                if not isinstance(c.get("lectures"), list) or any(x not in layer.keys for x in c["lectures"]):
                    P.append(f"course.json: card {c.get('concept')} with lectures {c.get('lectures')}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            P.append(f"course.json: malformed ({type(e).__name__}: {e})")
    return P


def _fact_list(x, allowed: set, layer: Layer, what: str) -> list[str]:
    if not isinstance(x, list) or not x:
        return [f"{what}: no facts"]
    return [f"{what}: fact {f} not in the activity's facts" for f in x if f not in allowed] + \
           [f"{what}: unknown fact {f}" for f in x if f not in layer.facts]


def _strings(xs, n=None) -> bool:
    return isinstance(xs, list) and all(txt(x) for x in xs) and (n is None or len(xs) == n)


def validate_data(kind: str, d: dict, facts: set, layer: Layer, k: str) -> list[str]:
    P = []
    keys = {"quiz": {"questions"}, "recap": {"text", "points"}, "recall": {"items"}, "open_question": {"questions"},
            "concept_map": {"nodes", "edges"}, "complete_map": {"nodes", "edges", "blanks"},
            "crossword": {"width", "height", "entries"}, "match_pairs": {"pairs"}, "odd_one_out": {"items"},
            "put_in_order": {"items"}}[kind]
    if not isinstance(d, dict) or set(d) != keys:
        return [f"data fields {sorted(d) if isinstance(d, dict) else d!r}, not {sorted(keys)}"]
    if kind == "quiz":
        if not d["questions"]:
            P.append("no questions")
        for i, q in enumerate(d["questions"]):
            w = f"question {i}"
            if set(q) != {"question", "options", "answer", "explanation", "facts"}:
                P.append(f"{w}: fields {sorted(q)}")
            if not txt(q["question"]) or not txt(q["explanation"]):
                P.append(f"{w}: empty text")
            if not _strings(q["options"], 4) or len({norm(o) for o in q["options"]}) != 4:
                P.append(f"{w}: options not 4 different texts")
            if not isinstance(q["answer"], int) or isinstance(q["answer"], bool) or not 0 <= q["answer"] < 4:
                P.append(f"{w}: answer {q['answer']!r} not an index 0..3")
            P += _fact_list(q["facts"], facts, layer, w)
    elif kind == "recap":
        if not txt(d["text"]) or not d["points"] or not _strings(d["points"]):
            P.append("empty text or points")
    elif kind == "recall":
        if not d["items"]:
            P.append("no items")
        for i, it in enumerate(d["items"]):
            if set(it) != {"concept", "prompt", "answer", "from_lecture"}:
                P.append(f"item {i}: fields {sorted(it)}")
            if it["concept"] not in layer.cards or not txt(it["prompt"]) or not txt(it["answer"]):
                P.append(f"item {i}: unknown concept or empty text")
            if it["from_lecture"] not in layer.keys or lec.order(it["from_lecture"]) >= lec.order(k):
                P.append(f"item {i}: from_lecture {it['from_lecture']!r} not an earlier lecture")
    elif kind == "open_question":
        if not d["questions"]:
            P.append("no questions")
        for i, q in enumerate(d["questions"]):
            w = f"question {i}"
            if set(q) != {"question", "reference_answer", "key_facts", "concepts"}:
                P.append(f"{w}: fields {sorted(q)}")
            if not txt(q["question"]) or not txt(q["reference_answer"]):
                P.append(f"{w}: empty text")
            P += _fact_list(q["key_facts"], facts, layer, w)
            P += [f"{w}: unknown concept {c}" for c in q["concepts"] if c not in layer.cards]
    elif kind in ("concept_map", "complete_map"):
        ids = [n["id"] for n in d["nodes"]]
        if len(set(ids)) != len(ids) or any(set(n) != {"id", "label"} or not txt(n["label"]) for n in d["nodes"]):
            P.append("nodes: repeated IDs, other fields or an empty label")
        P += [f"node {c}: unknown concept" for c in ids if c not in layer.cards]
        if not d["edges"]:
            P.append("no edges")
        for i, e in enumerate(d["edges"]):
            if set(e) - {"facts"} != {"from", "to", "label", "relation"} or e["from"] not in ids \
                    or e["to"] not in ids or e["relation"] not in layer.relations or not txt(e["label"]):
                P.append(f"edge {i}: bad fields, an end not a node, or an unknown relationship")
            if "facts" in e:
                P += _fact_list(e["facts"], facts, layer, f"edge {i}")
        if kind == "complete_map":
            label = {n["id"]: n["label"] for n in d["nodes"]}
            if not d["blanks"]:
                P.append("no blanks")
            for i, b in enumerate(d["blanks"]):
                if set(b) != {"edge", "hide", "answer", "options"} or not 0 <= b["edge"] < len(d["edges"]) \
                        or b["hide"] not in ("label", "from", "to"):
                    P.append(f"blank {i}: bad fields, edge or hide")
                    continue
                e = d["edges"][b["edge"]]
                right = e["label"] if b["hide"] == "label" else label[e[b["hide"]]]
                if b["answer"] != right or b["answer"] not in b["options"] or not _strings(b["options"]) \
                        or len({norm(o) for o in b["options"]}) != len(b["options"]) or len(b["options"]) < 3:
                    P.append(f"blank {i}: answer not the hidden value, not among 3+ different options")
                if b["hide"] != "label" and sum(e[b["hide"]] in (x["from"], x["to"]) for x in d["edges"]) > 1:
                    P.append(f"blank {i}: the hidden concept is on another edge too")
    elif kind == "crossword":
        W, H = d["width"], d["height"]
        grid, starts = {}, {}
        if not d["entries"]:
            P.append("no entries")
        cells_of = []
        for i, e in enumerate(d["entries"]):
            w = f"entry {i}"
            if set(e) - {"facts"} != {"number", "answer", "clue", "row", "col", "direction", "concept"}:
                P.append(f"{w}: fields {sorted(e)}")
            if "facts" in e:
                P += _fact_list(e["facts"], facts, layer, w)
            if not re.fullmatch(r"[A-Z]+", e["answer"] or ""):
                P.append(f"{w}: answer {e['answer']!r} not uppercase letters only")
            if not txt(e["clue"]) or e["concept"] not in layer.cards:
                P.append(f"{w}: empty clue or unknown concept")
            elif writes_answer(e["clue"], e["answer"]):
                P.append(f"{w}: the clue writes the answer")
            dr, dc = {"across": (0, 1), "down": (1, 0)}.get(e["direction"], (None, None))
            if dr is None:
                P.append(f"{w}: direction {e['direction']!r}")
                continue
            if starts.setdefault((e["row"], e["col"]), e["number"]) != e["number"]:
                P.append(f"{w}: another number at the same start cell")
            cells = []
            for j, ch in enumerate(e["answer"]):
                cell = (e["row"] + j * dr, e["col"] + j * dc)
                if not (0 <= cell[0] < H and 0 <= cell[1] < W):
                    P.append(f"{w}: outside the {W}x{H} grid")
                    break
                if grid.setdefault(cell, ch) != ch:
                    P.append(f"{w}: letter {ch} clashes with {grid[cell]} at {cell}")
                cells.append(cell)
            cells_of.append(set(cells))
        if len({n for n in starts.values()}) != len(starts):
            P.append("two start cells share a number")
        for i, cs in enumerate(cells_of):
            if len(cells_of) > 1 and not any(cs & o for j, o in enumerate(cells_of) if j != i):
                P.append(f"entry {i}: crosses no other entry")
    elif kind == "match_pairs":
        if len(d["pairs"]) < 2:
            P.append("fewer than two pairs")
        for i, pr in enumerate(d["pairs"]):
            if set(pr) - {"facts"} != {"left", "right", "concept"} or not txt(pr["left"]) or not txt(pr["right"]) \
                    or pr["concept"] not in layer.cards:
                P.append(f"pair {i}: bad fields, empty text or unknown concept")
            if "facts" in pr:
                P += _fact_list(pr["facts"], facts, layer, f"pair {i}")
        if len({norm(p["left"]) for p in d["pairs"]}) != len(d["pairs"]) \
                or len({norm(p["right"]) for p in d["pairs"]}) != len(d["pairs"]):
            P.append("repeated left or right")
    elif kind == "odd_one_out":
        if not d["items"]:
            P.append("no items")
        for i, it in enumerate(d["items"]):
            w = f"item {i}"
            if set(it) != {"options", "odd", "reason", "facts"} or not _strings(it["options"], 4) \
                    or len({norm(o) for o in it["options"]}) != 4 or not txt(it["reason"]):
                P.append(f"{w}: bad fields, not 4 different options, or no reason")
            if not isinstance(it["odd"], int) or isinstance(it["odd"], bool) or not 0 <= it["odd"] < 4:
                P.append(f"{w}: odd {it['odd']!r} not an index 0..3")
            P += _fact_list(it["facts"], facts, layer, w)
    elif kind == "put_in_order":
        if not d["items"]:
            P.append("no items")
        for i, it in enumerate(d["items"]):
            w = f"item {i}"
            if set(it) != {"title", "steps", "facts"} or not txt(it["title"]) or not _strings(it["steps"]) \
                    or len(it["steps"]) < 2 or len({norm(s) for s in it["steps"]}) != len(it["steps"]):
                P.append(f"{w}: bad fields, empty title, or fewer than 2 different steps")
            P += _fact_list(it["facts"], facts, layer, w)
    return P


def writes_answer(clue: str, answer: str) -> bool:
    """The clue writes the answer: one word or a run of consecutive words whose letters are the answer
    ("frame buffer" or "frame-buffer" for FRAMEBUFFER)."""
    toks = [letters(w) for w in re.split(r"[\s\-/]+", clue) if letters(w)]
    for i in range(len(toks)):
        s = ""
        for t in toks[i:]:
            s += t
            if s == answer:
                return True
            if len(s) >= len(answer):
                break
    return False


# ---------------------------------------------------------------- the text view
def render(a: dict, layer: Layer) -> list[str]:
    d, out = a["data"], []
    name = lambda c: layer.cards.get(c, {}).get("name", c)  # noqa: E731
    k = a["kind"]
    if k == "quiz":
        for q in d["questions"]:
            out.append(f"  Q {q['question']}  [{', '.join(q['facts'])}]")
            out += [f"    {'*' if i == q['answer'] else '-'} {o}" for i, o in enumerate(q["options"])]
            out.append(f"    because: {q['explanation']}")
    elif k == "recap":
        out += [f"  {d['text']}"] + [f"  - {p}" for p in d["points"]]
    elif k == "recall":
        out += [f"  {i['prompt']} (lecture {i['from_lecture']}) -> {i['answer']}" for i in d["items"]]
    elif k == "open_question":
        for q in d["questions"]:
            out += [f"  Q {q['question']}  [{', '.join(q['key_facts'])}; {', '.join(map(name, q['concepts']))}]",
                    f"    A {q['reference_answer']}"]
    elif k in ("concept_map", "complete_map"):
        hidden = {b["edge"]: b for b in d.get("blanks", [])}
        for i, e in enumerate(d["edges"]):
            parts = [name(e["from"]), e["label"], name(e["to"])]
            if i in hidden:
                b = hidden[i]
                j = {"from": 0, "label": 1, "to": 2}[b["hide"]]
                parts[j] = f"[___: {' / '.join(b['options'])}]"
            out.append(f"  {parts[0]} -- {parts[1]} -- {parts[2]}  ({e['relation']})")
        out.append("  nodes: " + ", ".join(n["label"] for n in d["nodes"]))
    elif k == "crossword":
        grid = {}
        for e in d["entries"]:
            dr, dc = (0, 1) if e["direction"] == "across" else (1, 0)
            for j, ch in enumerate(e["answer"]):
                grid[(e["row"] + j * dr, e["col"] + j * dc)] = ch
        out += ["    " + "".join(grid.get((r, c), ".") for c in range(d["width"])) for r in range(d["height"])]
        out += [f"  {e['number']} {e['direction']}: {e['clue']} = {e['answer']}" for e in d["entries"]]
    elif k == "match_pairs":
        out += [f"  {p['left']} = {p['right']}" for p in d["pairs"]]
    elif k == "odd_one_out":
        for it in d["items"]:
            out.append("  " + " | ".join(("*" if i == it["odd"] else "") + o for i, o in enumerate(it["options"]))
                       + f"  ({it['reason']})  [{', '.join(it['facts'])}]")
    elif k == "put_in_order":
        for it in d["items"]:
            out.append(f"  {it['title']}: " + " > ".join(it["steps"]) + f"  [{', '.join(it['facts'])}]")
    return out


def judge_lines(j: dict | None) -> list[str]:
    """The judge's verdicts under the activity: every round, each item with its check and reason."""
    if not j:
        return []
    out = []
    for r, rnd in enumerate(j["rounds"], 1):
        head = f"  judge round {r}" + (f" (rewrite, {j['rewrite']['status']})" if r == 2 else "")
        if rnd["status"] == "no_answer":
            out.append(f"{head}: no answer")
            continue
        out.append(f"{head}: {len(rnd['failed_items'])} of {len(rnd['verdicts'])} failed"
                   + (f"; unresolved: {' | '.join(rnd['problems'])}" if rnd.get("problems") else ""))
        for v in rnd["verdicts"]:
            if v.get("missing"):
                out.append(f"    {v['item']} no verdict  ({v['about']})")
                continue
            out.append(f"    {v['item']} {'pass' if v['pass'] else 'FAIL ' + ','.join(v['failed'])}  ({v['about']})")
            out.append(f"      check: {v['check']}")
            out.append(f"      reason: {v['reason']}")
    if "rewrite" in j and len(j["rounds"]) == 1:
        out.append(f"  rewrite: {j['rewrite']['status']} (not judged again)")
    out.append(f"  judge kept: {j['kept']}" + (f"; still failing: {j['failed_items']}" if j.get("failed_items") else ""))
    return out


def write_text(od: Path, layer: Layer, checks: dict):
    lines = []
    for p in lec.files(od):
        k = lec.key_of(p.stem)
        d = json.loads(p.read_text())
        lines += [f"===== lecture {k}: {layer.lectures.get(k, {}).get('title', '')}", ""]
        judged = {info["activity"]: info["judge"] for units in checks.get("lectures", {}).get(k, {}).values()
                  for info in units.values() if info.get("judge") and info.get("activity")}
        for a in d["activities"]:
            lines.append(f"{a['id']}  {a['kind']}  {a['segment'] or 'lecture'}  \"{a['title']}\"  "
                         f"({len(a['facts'])} facts, {len(a['concepts'])} concepts)")
            lines += render(a, layer)
            lines += judge_lines(judged.get(a["id"]))
            lines.append("")
        for kind, units in checks.get("lectures", {}).get(k, {}).items():
            for key, info in units.items():
                if info.get("status") not in ("ok",) or info.get("dropped") or info.get("flags") or info.get("retry"):
                    bits = [info["status"]]
                    if info.get("reason"):
                        bits.append(info["reason"])
                    if info.get("retry"):
                        bits.append(f"retried, {info['retry']['attempts']} attempts")
                    if info.get("problems"):
                        bits.append("unresolved: " + " | ".join(info["problems"]))
                    if info.get("dropped"):
                        bits.append(f"{len(info['dropped'])} item(s) dropped")
                    if info.get("flags"):
                        bits.append("flags: " + ", ".join(info["flags"]))
                    lines.append(f"  check {key}: " + "; ".join(bits))
        lines.append("")
    (od / "activities.txt").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- run
def sort_key(a: dict, segs: list[str]) -> tuple:
    if a["kind"] == "recall":
        return (0, 0, 0)
    if a["scope"] == "segment":
        return (1, segs.index(a["segment"]) if a["segment"] in segs else 99, SEGMENT_ORDER.index(a["kind"]))
    return (2, 0, LECTURE_ORDER.index(a["kind"]))


def run(course: str, llm: LLM | None, only: list[str] | None = None, kinds: list[str] | None = None,
        seed: int | None = None, out: Path | None = None, kd: Path | None = None, judge: bool = False,
        rewrite: bool = False, judge_llm: LLM | None = None) -> dict:
    judge = judge or rewrite
    layer = Layer(Path(kd) if kd else knowledge_dir(course))
    kinds = list(kinds or KINDS)
    keys = [k for k in layer.keys if k in layer.lectures and (not only or k in only)]
    od = Path(out) if out else out_dir(course)
    (od / "llm").mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    units: list[Unit] = []
    for k in keys:
        for kind in ("quiz", "recap"):
            if kind in kinds:
                units += [u for sid in layer.lectures[k]["segments"]
                          if (u := UNITS[kind](layer, course, k, sid, seed)) is not None]
        for kind, make in LECTURE_UNITS.items():
            if kind in kinds and (u := make(layer, course, k, seed)) is not None:
                units.append(u)
    reqs = [u.request for u in units if u.request is not None]
    results = {}
    if reqs:
        if llm is None:
            sys.exit("model-made kinds need --llm")
        print(f"5: {len(reqs)} calls ({', '.join(f'{x} {sum(u.kind == x for u in units if u.request)}' for x in MODEL_KINDS if x in kinds)}) "
              f"for {len(keys)} lectures with {llm.model}", flush=True)
        results = {r.key: r for r in llm.generate_many(reqs, cache_file=od / "llm" / "cache.jsonl",
                                                       log_file=od / "llm" / "calls.jsonl")}

    prev_checks = json.loads((od / "checks.json").read_text()) if (od / "checks.json").exists() else {}
    lecture_checks = prev_checks.get("lectures", {})
    new: dict[str, list] = {k: [] for k in keys}
    infos: dict[str, dict] = {k: {} for k in keys}
    done: dict[str, tuple] = {}                       # unit key -> (acts, conv) of the writer's kept answer
    for u in units:
        info = {}
        if u.request is None:
            info = {"status": "skipped", "reason": u.ctx.get("skip", "")}
        else:
            res = results[u.key]
            if res.history:
                info["retry"] = {"attempts": res.attempts, "problems": [h["errors"] for h in res.history]}
            if not s4a.answered(res):
                info.update(status="no_answer", problems=res.errors)
            else:
                acts, dropped, flags = CONVERT[u.kind](res.parsed, u.ctx, layer, u)
                conv = u.ctx.pop("_conv", {})
                info["status"] = "ok" if res.ok else "unresolved"
                if not res.ok:
                    info["problems"] = res.errors
                if dropped:
                    info["dropped"] = dropped
                if flags:
                    info["flags"] = flags
                if not acts:
                    info["status"] = info["status"] + "_empty" if info["status"] != "ok" else "empty"
                done[u.key] = (acts, conv)
        infos[u.lecture].setdefault(u.kind, {})[u.key] = info

    n_judge = 0
    if judge and done:
        jl = judge_llm or llm
        live = {u.key: u for u in units if u.key in done and done[u.key][0]}
        items = {k_: judge_items(u, done[k_][0], done[k_][1], layer) for k_, u in live.items()}
        jreqs = [judge_request(u, items[k_], 1, seed) for k_, u in live.items() if items[k_]]
        n_judge += len(jreqs)
        print(f"5: judge, {len(jreqs)} calls with {jl.model}", flush=True)
        j1 = {r.key: r for r in jl.generate_many(jreqs, cache_file=od / "llm" / "cache.jsonl",
                                                 log_file=od / "llm" / "calls.jsonl")}
        rounds = {k_: judge_round(j1[f"judge1:{k_}"], items[k_]) for k_ in live if f"judge1:{k_}" in j1}
        for k_, rnd in rounds.items():
            infos[live[k_].lecture][live[k_].kind][k_]["judge"] = {"rounds": [rnd], "kept": "original"}
        failing = [k_ for k_, rnd in rounds.items() if rnd.get("failed_items")]
        if rewrite and failing:
            wreqs = [rewrite_request(live[k_], results[k_], rounds[k_], done[k_][1]) for k_ in failing]
            n_judge += len(wreqs)
            print(f"5: rewrite, {len(wreqs)} calls with {llm.model}", flush=True)
            rw = {r.key: r for r in llm.generate_many(wreqs, cache_file=od / "llm" / "cache.jsonl",
                                                      log_file=od / "llm" / "calls.jsonl")}
            second, j2reqs = {}, []
            for k_ in failing:
                u, res = live[k_], rw[f"rewrite:{k_}"]
                jinfo = infos[u.lecture][u.kind][k_]["judge"]
                rinfo = {"status": "ok" if res.ok else ("unresolved" if s4a.answered(res) else "no_answer")}
                if res.history:
                    rinfo["retry"] = {"attempts": res.attempts, "problems": [h["errors"] for h in res.history]}
                if not res.ok:
                    rinfo["problems"] = res.errors
                jinfo["rewrite"] = rinfo
                if not s4a.answered(res):
                    continue
                acts2, dropped2, flags2 = CONVERT[u.kind](res.parsed, u.ctx, layer, u)
                conv2 = u.ctx.pop("_conv", {})
                if not acts2:
                    rinfo["status"] += "_empty"
                    continue
                items2 = judge_items(u, acts2, conv2, layer)
                if not items2:
                    continue
                second[k_] = (res, acts2, dropped2, flags2, conv2, items2)
                j2reqs.append(judge_request(u, items2, 2, seed))
            n_judge += len(j2reqs)
            j2 = {r.key: r for r in jl.generate_many(j2reqs, cache_file=od / "llm" / "cache.jsonl",
                                                     log_file=od / "llm" / "calls.jsonl")} if j2reqs else {}
            for k_, (res, acts2, dropped2, flags2, conv2, items2) in second.items():
                u = live[k_]
                info = infos[u.lecture][u.kind][k_]
                rnd2 = judge_round(j2[f"judge2:{k_}"], items2)
                info["judge"]["rounds"].append(rnd2)
                if rnd2["status"] != "no_answer" and len(rnd2["failed_items"]) < len(rounds[k_]["failed_items"]):
                    info["judge"]["kept"] = "rewrite"
                    info["judge"]["original"] = {x: info.pop(x) for x in ("status", "problems", "dropped", "flags")
                                                 if x in info}
                    info["status"] = "ok" if res.ok else "unresolved"
                    if not res.ok:
                        info["problems"] = res.errors
                    if dropped2:
                        info["dropped"] = dropped2
                    if flags2:
                        info["flags"] = flags2
                    done[k_] = (acts2, conv2)
        for k_ in rounds:                             # what still fails in the version kept
            u = live[k_]
            info = infos[u.lecture][u.kind][k_]
            jr = info["judge"]["rounds"]
            last = jr[-1] if info["judge"]["kept"] == "rewrite" else jr[0]
            if last.get("failed_items"):
                info.setdefault("flags", {})["judge_failed"] = last["failed_items"]
            info["judge"]["failed_items"] = last.get("failed_items", [])
    for u in units:
        if u.key not in done:
            continue
        info = infos[u.lecture][u.kind][u.key]
        for a in done[u.key][0]:
            a = {"kind": u.kind, "title": a.pop("title", None) or TITLES[u.kind], **a}
            a["_info"] = info
            new[u.lecture].append(a)
    for k in keys:
        for kind, make in CODE_MAKERS.items():
            if kind not in kinds:
                continue
            a, why = make(layer, k)
            info = {"status": "ok"} if a else {"status": "skipped", "reason": why}
            if a:
                a = {"kind": kind, "title": TITLES[kind], **a, "_info": info}
                new[k].append(a)
            infos[k].setdefault(kind, {})[f"{kind}:{k}"] = info

    for k in keys:
        p = od / f"{lec.stem_of(k)}.json"
        kept = []
        if p.exists() and set(kinds) != set(KINDS):
            kept = [a for a in json.loads(p.read_text())["activities"] if a["kind"] not in kinds]
        segs = list(layer.lectures[k]["segments"])
        acts = sorted(kept + new[k], key=lambda a: sort_key(a, segs))
        final = []
        for i, a in enumerate(acts):
            info = a.pop("_info", None)
            a = {"id": f"{k}/A{i}", **{f: a[f] for f in ACT_FIELDS[1:]}}
            if info is not None:
                info["activity"] = a["id"]
            final.append(a)
        old_ids = {a["id"]: a for a in kept}
        lc = lecture_checks.get(k, {}) if set(kinds) != set(KINDS) else {}
        for kind in list(lc):                      # kept kinds: their activity IDs may have moved
            if kind in kinds:
                del lc[kind]
        remap = {}
        for a_old in kept:
            for a in final:
                if a["kind"] == a_old["kind"] and a["data"] == a_old["data"] and a["segment"] == a_old["segment"]:
                    remap[a_old["id"]] = a["id"]
        for units_ in lc.values():
            for info in units_.values():
                if info.get("activity") in old_ids:
                    info["activity"] = remap.get(info["activity"], info["activity"])
        lc.update(infos[k])
        lecture_checks[k] = {kind: lc[kind] for kind in KINDS if kind in lc}
        p.write_text(json.dumps({"lecture": k, "activities": final}, indent=1, ensure_ascii=False) + "\n")
    if "spaced_review" in kinds:
        (od / "course.json").write_text(json.dumps(spaced_review(layer), indent=1, ensure_ascii=False) + "\n")

    lecture_checks = {k: lecture_checks[k] for k in sorted(lecture_checks, key=lec.order)}
    contract = validate(od, layer)
    totals = {"activities": {}, "units": {}, "retried": 0, "unresolved": [], "no_answer": [], "dropped_items": 0,
              "flags": {}}
    jt = {"units": 0, "items": 0, "failed_items": 0, "failed": {}, "no_answer": 0, "rewritten": 0,
          "rewrite_kept": 0, "still_failed_items": 0}
    for p in lec.files(od):
        for a in json.loads(p.read_text())["activities"]:
            totals["activities"][a["kind"]] = totals["activities"].get(a["kind"], 0) + 1
    if (od / "course.json").exists():
        totals["activities"]["spaced_review_cards"] = len(json.loads((od / "course.json").read_text())
                                                          ["spaced_review"]["cards"])
    for k, lc in lecture_checks.items():
        for kind, units_ in lc.items():
            for key, info in units_.items():
                st = totals["units"].setdefault(kind, {})
                st[info["status"]] = st.get(info["status"], 0) + 1
                totals["retried"] += "retry" in info
                if info["status"].startswith("unresolved"):
                    totals["unresolved"].append(key)
                if info["status"] == "no_answer":
                    totals["no_answer"].append(key)
                totals["dropped_items"] += len(info.get("dropped", []))
                for f in info.get("flags", {}):
                    totals["flags"][f"{kind}.{f}"] = totals["flags"].get(f"{kind}.{f}", 0) + 1
                j = info.get("judge")
                if j:
                    r1 = j["rounds"][0]
                    jt["units"] += 1
                    jt["no_answer"] += r1["status"] == "no_answer"
                    jt["items"] += len(r1.get("verdicts", []))
                    jt["failed_items"] += len(r1.get("failed_items", []))
                    for v in r1.get("verdicts", []):
                        for c in v.get("failed", []):
                            jt["failed"][f"{kind}.{c}"] = jt["failed"].get(f"{kind}.{c}", 0) + 1
                    jt["rewritten"] += "rewrite" in j
                    jt["rewrite_kept"] += j["kept"] == "rewrite"
                    jt["still_failed_items"] += len(j.get("failed_items", []))
    if jt["units"]:
        totals["judge"] = jt
    checks = {"run": {"lectures": keys, "kinds": kinds, "model": llm.model if (llm and reqs) else None,
                      "calls": len(reqs), "seconds": round(time.time() - t0, 1),
                      **({"judge": True, "judge_rewrite": rewrite, "judge_model": (judge_llm or llm).model,
                          "judge_calls": n_judge} if judge and llm else {})},
              "totals": totals, "contract": contract, "lectures": lecture_checks}
    (od / "checks.json").write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
    write_text(od, layer, checks)
    print(f"5: {sum(v for k_, v in totals['activities'].items() if k_ != 'spaced_review_cards')} activities in "
          f"{len(lec.files(od))} lecture files ({', '.join(f'{k_} {v}' for k_, v in totals['activities'].items())}); "
          f"{totals['retried']} retried, {len(totals['unresolved'])} unresolved, {len(totals['no_answer'])} no answer, "
          f"{totals['dropped_items']} items dropped; {round(time.time() - t0, 1)} s")
    print(f"contract: {'all good' if not contract else f'{len(contract)} problems'}")
    for m in contract[:10]:
        print(f"  {m}")
    return checks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", help="LLMConfig file (.json or .toml); needed for the model-made kinds")
    ap.add_argument("--only", help="lectures, e.g. 1-5,16")
    ap.add_argument("--kinds", help=f"kinds to build (default all): {','.join(KINDS)}")
    ap.add_argument("--seed", type=int, help="sampling seed (default: the config's); for repeat runs")
    ap.add_argument("--out", help="output folder (default: output/<course>/activities)")
    ap.add_argument("--check", action="store_true", help="only check the existing activities folder")
    ap.add_argument("--judge", action="store_true", help="judge every model-made unit after the code checks "
                    "(prompts/activity_judge_<kind>.txt); verdicts go to checks.json and activities.txt")
    ap.add_argument("--judge-rewrite", action="store_true", help="on a judge fail, one rewrite and one more judge "
                    "call (implies --judge)")
    ap.add_argument("--judge-llm", help="LLMConfig file of the judge (default: the --llm model judges)")
    a = ap.parse_args()
    od = Path(a.out) if a.out else out_dir(a.course)
    if a.check:
        problems = validate(od, Layer(knowledge_dir(a.course)))
        print(f"contract: {'all good' if not problems else f'{len(problems)} problems'}")
        for m in problems:
            print(f"  {m}")
        sys.exit(1 if problems else 0)
    kinds = [x.strip() for x in a.kinds.split(",")] if a.kinds else list(KINDS)
    bad = [x for x in kinds if x not in KINDS]
    if bad:
        sys.exit(f"unknown kinds {bad}; known: {', '.join(KINDS)}")
    only = lec.parse_only(a.only) if a.only else None
    if any(x in MODEL_KINDS for x in kinds):
        if not a.llm:
            sys.exit("the model-made kinds need --llm")
        judge = a.judge or a.judge_rewrite
        with LLM(LLMConfig.load(a.llm)) as llm:
            if judge and a.judge_llm:
                with LLM(LLMConfig.load(a.judge_llm)) as jllm:
                    checks = run(a.course, llm, only, kinds, a.seed, od, judge=judge, rewrite=a.judge_rewrite,
                                 judge_llm=jllm)
            else:
                checks = run(a.course, llm, only, kinds, a.seed, od, judge=judge, rewrite=a.judge_rewrite)
    else:
        checks = run(a.course, None, only, kinds, a.seed, od)
    sys.exit(1 if checks["contract"] else 0)


if __name__ == "__main__":
    main()
