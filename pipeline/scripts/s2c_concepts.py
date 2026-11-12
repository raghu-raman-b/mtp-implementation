"""Stage 2c: the concepts of each segment and the relationships between them, from its verified facts.

    python scripts/s2c_concepts.py nptel_vr --llm configs/qwen38_27b_vllm.json [--only 1,4,16] [--seed 1 --out DIR]

Reads   output/<course>/stage_2b_verify_facts/fact_maps/lec_<n>.json      the verified facts
        output/<course>/stage_1b_verify_segments/segment_maps/lec_<n>.json (sub-goals), course.json, titles.tsv
Prompts prompts/concept_extraction.txt (turn 1): {course_title}, {course}, {lecture_title}, {subgoal}, {facts}
        prompts/concept_relations.txt (turn 2): {concepts}
Writes  output/<course>/stage_2c_concepts/ (or --out)
          concept_maps/lec_<n>.json  {"4/S1/C0": {"name", "aliases", "facts": [fact IDs], "defined"}, ...}
          relations/lec_<n>.json     {"4/S1/R0": {"subject": "4/S1/C0", "label", "object": "4/S1/C3",
                                                  "facts": [fact IDs]}, ...}
          text/lec_<n>.txt           both, readable: per segment its concepts, then its triples with names, its
                                     checks, its retries and what is unresolved
          checks/lec_<n>.json        per segment: counts, the code checks (below), "retries" and "unresolved"
          checks/summary.json        the run's totals (the lectures of this run)
          llm/cache.jsonl, calls.jsonl

One conversation per segment with facts (segments without facts are skipped):
1. Turn 1: the segment's verified facts, numbered [1]..[n], in; concepts out: name, aliases, facts (numbers),
   defined. The fact numbers are mapped back to fact IDs in code.
2. Code checks on the answer. An answer with a retry problem (RETRY_1, below) is sent back to the model with the
   problems listed (LLM API feedback: the answer, then "Your answer has these problems: ..."), up to the config's
   retries. The answer kept is the first that passes, or, when none passes, the one with the fewest problems (the
   latest on a tie): it is kept, repaired as any answer, and its remaining problems are listed under "unresolved".
   Only a segment where no attempt gave a parseable answer of the schema's form has no answer (no concepts).
   The repairs code makes: concepts with the same name (case and spacing ignored) are merged into the first
   (aliases and facts joined, defined if either is); fact numbers out of range are dropped.
3. Turn 2: the conversation continued from turn 1's prompt and its kept answer only (as the model gave it; the
   retries of turn 1 are not shown), then the relations prompt with the checked concept list; triples out: facts,
   subject, label, object. The answer schema limits subject and object to the checked concept names. Checked and
   retried as in step 2 (RETRY_2); the answer kept is chosen in the same way.
4. Code checks on the triples. Then concept IDs "<segment>/C<k>" in the checked order, relationship IDs
   "<segment>/R<k>" in the model's order (fact numbers out of range dropped).

Code checks, reported per segment. Retried (with the problem line sent to the model):
  turn 1  out_of_range      a fact number outside 1..n
          name_is_acronym   the whole name is one acronym token (fact_checks.is_acronym: "VR", "3D", "HMDs")
          empty_name        a concept with an empty name
          alias_not_written an alias written in none of the segment's facts
  turn 2  out_of_range      a fact number outside 1..n
          vague_label       a label such as "is related to", "is associated with", "involves"
          self_triple       a triple from a concept to itself
          duplicate_triple  a triple written again (same subject and object, label equal up to case and spacing);
                            the later copies are listed
Report only:
  merged            the same name twice
  name_not_in_facts, alias_not_in_facts   a concept's name or alias that appears in none of its own facts
  acronym_in_name   an acronym token inside a longer name ("VR headset"; code cannot tell it from "PlayStation VR")
  fact_without_concept   a fact that no concept cites
  no_shared_fact    a triple none of whose cited facts is cited by both its concepts (also flags a triple the
                    model states across two facts, one naming each concept)
  reverse           a triple whose reverse (object to subject) is also there (a triple from a concept to itself is
                    self_triple, not reverse)
  no_triple         a concept in no triple
The checks of the kept answer are the ones reported; the flags of an answer that passed after a retry are those of
the answer that passed. A term "appears" in a fact when its words do, ignoring case, hyphens, apostrophes ("the user's
sense organs") and a plural ending; a fact that writes "X (Y) Z" writes both "X Z" and "Y Z" ("three-dimensional (3D)
space" writes "three-dimensional space" and "3D space").

Retries are logged per turn in checks ("retries": {"turn 1": {"attempts", "kept", "first_problems", "lost",
"added"}}): the attempts made, which one was kept, the first attempt's problems, and the concept names (turn 1) or
triples "subject | label | object" (turn 2) of the first attempt missing from the kept answer (lost) and new in it
(added). The run summary counts them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, fact_checks, lectures as lec  # noqa: E402
from scripts import s2a_fact_extraction as s2a, s2b_verify_facts as s2b  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402
from scripts.llm.client import _parse_json  # noqa: E402

EXTRACT = ROOT / "prompts" / "concept_extraction.txt"
RELATE = ROOT / "prompts" / "concept_relations.txt"
VAGUE = re.compile(r"^\s*(?:is |are )?(?:related to|associated with|involves?|connected (?:to|with)|linked (?:to|with)|"
                   r"relates? to|has to do with|concerns?)\s*$", re.I)
RETRY_1 = ("out_of_range", "name_is_acronym", "empty_name", "alias_not_written")
RETRY_2 = ("out_of_range", "vague_label", "self_triple", "duplicate_triple")


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_2c_concepts"


# ---------------------------------------------------------------- inputs
def load_segments(course: str, key: str) -> list[dict]:
    """The lecture's segments with their sub-goals and verified facts, in order."""
    seg_map = json.loads((s2a.maps_dir(course) / f"{lec.stem_of(key)}.json").read_text())
    facts = json.loads((s2b.out_dir(course) / "fact_maps" / f"{lec.stem_of(key)}.json").read_text())
    return [{"id": sid, "key": key, "subgoal": seg["subgoal"],
             "facts": [{"id": fid, "text": f["text"]} for fid, f in facts.items() if fid.rsplit("/", 1)[0] == sid]}
            for sid, seg in seg_map.items()]


# ---------------------------------------------------------------- turn 1: concepts
def extraction_prompt(course: str, seg: dict) -> str:
    block, template = course_meta.course_prompt(course), EXTRACT.read_text()
    if not block:
        template = template.replace("{course}\n", "")
    head, sep, tail = template.rpartition("### Your segment")   # fill only the input part, not the examples
    numbered = "\n".join(f"[{i}] {f['text']}" for i, f in enumerate(seg["facts"], 1))
    tail = (tail.replace("{course_title}", course_meta.load(course)["title"])
            .replace("{course}", block)
            .replace("{lecture_title}", course_meta.lecture_title(course, seg["key"]))
            .replace("{subgoal}", seg["subgoal"])
            .replace("{facts}", numbered))                       # last: fact text is never replaced
    return head + sep + tail


def concept_schema(n: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["concepts"],
            "properties": {"concepts": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["name", "aliases", "facts", "defined"],
                "properties": {"name": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}},
                               "facts": {"type": "array", "minItems": 1,
                                         "items": {"type": "integer", "minimum": 1, "maximum": n}},
                               "defined": {"type": "boolean"}}}}}}


def concept_request(course: str, seg: dict, seed: int | None = None) -> Request:
    facts = [f["text"] for f in seg["facts"]]
    return Request(prompt=extraction_prompt(course, seg), key=seg["id"], schema=concept_schema(len(facts)),
                   check=concept_check(facts), feedback=True,
                   sampling={} if seed is None else {"seed": seed}, meta={"lecture": seg["key"]})


def _norm(name: str) -> str:
    return " ".join(name.lower().split())


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def concepts_form(answer) -> str | None:
    """None when a turn-1 answer has the schema's form (a server without strict schemas may break it), otherwise
    what is wrong."""
    cs = answer.get("concepts") if isinstance(answer, dict) else None
    if not isinstance(cs, list):
        return "The answer has no list of concepts."
    for c in cs:
        if not (isinstance(c, dict) and isinstance(c.get("name"), str) and isinstance(c.get("aliases"), list)
                and all(isinstance(a, str) for a in c["aliases"]) and isinstance(c.get("facts"), list)
                and all(_is_int(i) for i in c["facts"]) and isinstance(c.get("defined"), bool)):
            return ("A concept does not have the fields name (text), aliases (list of texts), facts (list of "
                    "numbers) and defined (true or false).")
    return None


def check_concepts(concepts: list[dict], n: int) -> tuple[list[dict], dict]:
    """Merge concepts with the same name, drop fact numbers out of range. Returns the checked list and the flags
    that come from these two steps."""
    flags = {"out_of_range": [], "merged": []}
    out, seen = [], {}
    for c in concepts:
        bad = [i for i in c["facts"] if not 1 <= i <= n]
        if bad:
            flags["out_of_range"].append({"concept": c["name"], "facts": bad})
        facts = [i for i in c["facts"] if 1 <= i <= n]
        key = _norm(c["name"])
        if key in seen:
            first = out[seen[key]]
            flags["merged"].append(c["name"])
            first["aliases"] += [a.strip() for a in c["aliases"] if a.strip() not in first["aliases"]]
            first["facts"] = sorted(set(first["facts"]) | set(facts))
            first["defined"] = first["defined"] or c["defined"]
        else:
            seen[key] = len(out)
            out.append({"name": c["name"].strip(), "aliases": list(dict.fromkeys(a.strip() for a in c["aliases"])),
                        "facts": sorted(set(facts)), "defined": c["defined"]})
    return out, flags


# ---------------------------------------------------------------- turn 2: relationships
def concept_list(concepts: list[dict]) -> str:
    """The checked concepts for the relations prompt: one JSON object per line, the format of the turn-1 answer."""
    return "\n".join(json.dumps(c, ensure_ascii=False) for c in concepts)


def relation_schema(names: list[str], n: int) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["relations"],
            "properties": {"relations": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["facts", "subject", "label", "object"],
                "properties": {"facts": {"type": "array", "minItems": 1,
                                         "items": {"type": "integer", "minimum": 1, "maximum": n}},
                               "subject": {"type": "string", "enum": names}, "label": {"type": "string"},
                               "object": {"type": "string", "enum": names}}}}}}


def relation_request(first: Request, answer: str, concepts: list[dict], n: int) -> Request:
    """Turn 2: turn 1's prompt and its kept answer (only), then the relations prompt."""
    return Request(prompt=first.prompt, key=first.key, schema=relation_schema([c["name"] for c in concepts], n),
                   check=relation_check(concepts, n), feedback=True,
                   followup=[{"role": "assistant", "content": answer},
                             {"role": "user", "content": RELATE.read_text().replace("{concepts}",
                                                                                    concept_list(concepts))}],
                   sampling=first.sampling, meta=first.meta)


def relations_form(answer, names: list[str]) -> str | None:
    """None when a turn-2 answer has the schema's form, otherwise what is wrong."""
    rs = answer.get("relations") if isinstance(answer, dict) else None
    if not isinstance(rs, list):
        return "The answer has no list of relations."
    for r in rs:
        if not (isinstance(r, dict) and isinstance(r.get("facts"), list) and all(_is_int(i) for i in r["facts"])
                and isinstance(r.get("label"), str) and r.get("subject") in names and r.get("object") in names):
            return ("A relationship does not have the fields facts (list of numbers), subject, label and object, "
                    "with the subject and the object written exactly as a concept name of the list.")
    return None


# ---------------------------------------------------------------- checks
APOSTROPHES = str.maketrans({"’": "'", "‘": "'"})
BRACKET = re.compile(r"\s*\(([^()]*)\)")
SEP = r"[\s'-]+"     # between the words of a term: spaces, hyphens, apostrophes ("user's" = "user" "s")


def readings(text: str) -> list[str]:
    """The text as written, lower case, and the wordings it also writes through its brackets: "X (Y) Z" writes
    "X Z" (every bracket left out) and "Y Z" (from each bracket on, the later brackets left out)."""
    t = text.lower().translate(APOSTROPHES)
    out = [t, BRACKET.sub("", t)]
    for m in BRACKET.finditer(t):
        out.append(m.group(1) + " " + BRACKET.sub("", t[m.end():]))
    return out


def appears(term: str, text: str) -> bool:
    """The term's words in the text, ignoring case, hyphens, apostrophes and a plural ending; brackets as in
    readings() ("three-dimensional (3D) space" has "three-dimensional space" and "3D space")."""
    words = re.findall(r"[a-z0-9]+", term.lower())
    if not words:
        return False
    pat = re.compile(r"(?<![a-z0-9])" + SEP.join(map(re.escape, words)) + r"(?:s|es)?(?![a-z0-9])")
    return any(pat.search(t) for t in readings(text))


def concept_checks(concepts: list[dict], facts: list[str]) -> dict:
    """The checks on the checked concepts (fact numbers within 1..n) against the segment's facts."""
    flags = {"name_not_in_facts": [], "alias_not_in_facts": [], "alias_not_written": [], "name_is_acronym": [],
             "acronym_in_name": [], "empty_name": [], "fact_without_concept": []}
    for c in concepts:
        own = [facts[i - 1] for i in c["facts"]]
        name = c["name"].strip()
        if not name:
            flags["empty_name"].append({"facts": c["facts"]})
        elif fact_checks.is_acronym(name):
            flags["name_is_acronym"].append(name)
        elif fact_checks.acronyms_in(name):
            flags["acronym_in_name"].append({"concept": name, "acronyms": fact_checks.acronyms_in(name)})
        if name and not any(appears(name, t) for t in own):
            flags["name_not_in_facts"].append(name)
        for a in c["aliases"]:
            if not any(appears(a, t) for t in own):
                flags["alias_not_in_facts"].append({"concept": name, "alias": a})
            if not any(appears(a, t) for t in facts):
                flags["alias_not_written"].append({"concept": name, "alias": a})
    cited = {i for c in concepts for i in c["facts"]}
    flags["fact_without_concept"] = [i for i in range(1, len(facts) + 1) if i not in cited]
    return flags


def relation_checks(concepts: list[dict], relations: list[dict], n: int) -> dict:
    """The checks on the triples (concept names) of the checked concepts."""
    flags = {"out_of_range": [], "no_shared_fact": [], "reverse": [], "self_triple": [], "duplicate_triple": [],
             "vague_label": [], "no_triple": []}
    by_name = {c["name"]: c for c in concepts}
    pairs = {(r["subject"], r["object"]) for r in relations if r["subject"] != r["object"]}
    seen, in_triple = set(), set()
    for k, r in enumerate(relations):
        bad = [i for i in r["facts"] if not 1 <= i <= n]
        if bad:
            flags["out_of_range"].append({"triple": k, "facts": bad})
        s, o = by_name.get(r["subject"]), by_name.get(r["object"])
        in_triple |= {r["subject"], r["object"]}
        if s and o and not set(r["facts"]) & set(s["facts"]) & set(o["facts"]):
            flags["no_shared_fact"].append(k)
        if r["subject"] == r["object"]:
            flags["self_triple"].append(k)
        elif (r["object"], r["subject"]) in pairs:
            flags["reverse"].append(k)
        key = (r["subject"], _norm(r["label"]), r["object"])
        if key in seen:
            flags["duplicate_triple"].append(k)
        seen.add(key)
        if VAGUE.match(" ".join(r["label"].split())):
            flags["vague_label"].append(k)
    flags["no_triple"] = [c["name"] for c in concepts if c["name"] not in in_triple]
    return flags


def check_all(concepts: list[dict], relations: list[dict], facts: list[str], flags: dict) -> dict:
    """All checks of a segment: the flags of check_concepts, then the concept and the triple checks."""
    rel = relation_checks(concepts, relations, len(facts))
    out = dict(flags, **concept_checks(concepts, facts))
    return dict(out, **{k: v for k, v in rel.items() if k != "out_of_range"},
                out_of_range=list(flags.get("out_of_range", [])) + rel["out_of_range"])


# ---------------------------------------------------------------- retries: problem lines for the model
def _numbers(xs: list) -> str:
    return ", ".join(str(x) for x in xs)


def _triple(r: dict) -> str:
    return f"{r['subject']} | {r['label']} | {r['object']}"


def concept_problems(flags: dict, n: int) -> list[str]:
    """The problem lines of the turn-1 retry kinds, in RETRY_1 order."""
    out = [f'The concept "{x["concept"]}" cites the fact numbers {_numbers(x["facts"])}, which are not in the list. '
           f"The facts are numbered 1 to {n}." for x in flags.get("out_of_range", []) if "concept" in x]
    out += [f'The name "{name}" is an acronym. A concept\'s name is always the full term in words; put "{name}" in '
            f"its aliases. If your list already has this concept under its full name, join the two."
            for name in flags.get("name_is_acronym", [])]
    out += [f"A concept that cites the facts {_numbers(x['facts'])} has an empty name. Give it its name: the full "
            f"term in words." for x in flags.get("empty_name", [])]
    out += [f'The alias "{x["alias"]}" of "{x["concept"]}" is written in none of the facts. Remove it.'
            for x in flags.get("alias_not_written", [])]
    return out


def relation_problems(flags: dict, relations: list[dict], n: int) -> list[str]:
    """The problem lines of the turn-2 retry kinds, in RETRY_2 order."""
    out = [f'The relationship "{_triple(relations[x["triple"]])}" cites the fact numbers {_numbers(x["facts"])}, '
           f"which are not in the list. The facts are numbered 1 to {n}."
           for x in flags.get("out_of_range", []) if "triple" in x]
    out += [f'The label "{relations[k]["label"]}" of the relationship "{_triple(relations[k])}" does not say what '
            f"the relationship is. Write a label as specific as the facts, or remove the relationship if the facts "
            f"state none." for k in flags.get("vague_label", [])]
    out += [f'The relationship "{_triple(relations[k])}" joins a concept to itself. A relationship joins two '
            f"different concepts: give it the right subject or object, or remove it."
            for k in flags.get("self_triple", [])]
    dups: dict[str, int] = {}
    for k in flags.get("duplicate_triple", []):
        dups[_triple(relations[k])] = dups.get(_triple(relations[k]), 1) + 1
    out += [f'The relationship "{t}" is written {c} times. Write it once, citing the facts of all its copies.'
            for t, c in dups.items()]
    return out


def concept_check(facts: list[str]):
    """The turn-1 check for the LLM API: the problem lines of an answer (none: it passes)."""
    def check(answer) -> list[str]:
        bad = concepts_form(answer)
        if bad:
            return [bad]
        concepts, flags = check_concepts(answer["concepts"], len(facts))
        return concept_problems({**flags, **concept_checks(concepts, facts)}, len(facts))
    return check


def relation_check(concepts: list[dict], n: int):
    """The turn-2 check for the LLM API."""
    names = [c["name"] for c in concepts]

    def check(answer) -> list[str]:
        bad = relations_form(answer, names)
        if bad:
            return [bad]
        return relation_problems(relation_checks(concepts, answer["relations"], n), answer["relations"], n)
    return check


def _concept_names(answer) -> list[str] | None:
    return [c["name"] for c in answer["concepts"]] if concepts_form(answer) is None else None


def _triples_of(names: list[str]):
    return lambda answer: ([_triple(r) for r in answer["relations"]] if relations_form(answer, names) is None
                           else None)


def lost_added(first: list[str], final: list[str]) -> tuple[list[str], list[str]]:
    """What of the first list the final one no longer has, and what it has new (case and spacing ignored)."""
    a, b = {_norm(x): x for x in first}, {_norm(x): x for x in final}
    return [a[k] for k in a if k not in b], [b[k] for k in b if k not in a]


def retry_log(res, items) -> dict | None:
    """For an answer that took more than one attempt: the attempts made, the one kept (1-based), the first
    attempt's problems, and the items (concept names or triples) lost and added from the first attempt to the kept
    answer. None when the first attempt passed."""
    if not res.history:
        return None
    first = res.history[0]
    try:
        before = items(_parse_json(first["answer"]))
    except ValueError:
        before = None
    after = items(res.parsed) if res.parsed is not None else None
    lost, added = lost_added(before or [], after or [])
    return {"attempts": len(res.history) + (1 if res.ok else 0), "kept": res.attempts if after is not None else None,
            "first_problems": first["errors"], "lost": lost, "added": added}


# ---------------------------------------------------------------- run
def run(course: str, llm: LLM, lectures: list | None = None, seed: int | None = None,
        out: Path | None = None) -> dict:
    """Concepts and relationships of every segment of the lectures (all with verified facts by default)."""
    keys = lec.normalize(lectures) or lec.keys(s2b.out_dir(course) / "fact_maps")
    od = Path(out) if out else out_dir(course)
    for sub in ("concept_maps", "relations", "text", "checks", "llm"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    cache, log = od / "llm" / "cache.jsonl", od / "llm" / "calls.jsonl"
    t0 = time.time()
    segs = {k: load_segments(course, k) for k in keys}
    todo = [s for k in keys for s in segs[k] if s["facts"]]
    first = [concept_request(course, s, seed) for s in todo]
    print(f"2c turn 1: concepts of {len(todo)} segments with {llm.model}", flush=True)
    res1 = llm.generate_many(first, cache_file=cache, log_file=log)
    state, second = {}, []
    for s, req, res in zip(todo, first, res1):
        n = len(s["facts"])
        st = state[s["id"]] = {"concepts": [], "relations": [], "flags": {}, "errors": [], "unresolved": {},
                               "retries": {}}
        if res.history:
            st["retries"]["turn 1"] = retry_log(res, _concept_names)
        if res.parsed is None or concepts_form(res.parsed):
            st["errors"] = res.errors or [concepts_form(res.parsed)]       # no attempt parsed: no answer
            continue
        if not res.ok:
            st["unresolved"]["turn 1"] = res.errors
        st["concepts"], st["flags"] = check_concepts(res.parsed["concepts"], n)
        if st["concepts"]:
            second.append((s, relation_request(req, res.content, st["concepts"], n)))
    print(f"2c turn 2: relationships in {len(second)} segments", flush=True)
    for (s, req), res in zip(second, llm.generate_many([r for _, r in second], cache_file=cache, log_file=log)):
        st = state[s["id"]]
        names = [c["name"] for c in st["concepts"]]
        if res.history:
            st["retries"]["turn 2"] = retry_log(res, _triples_of(names))
        if res.parsed is None or relations_form(res.parsed, names):
            st["errors"] += [f"turn 2: {e}" for e in res.errors or [relations_form(res.parsed, names)]]
            continue
        if not res.ok:
            st["unresolved"]["turn 2"] = res.errors
        st["relations"] = res.parsed["relations"]
    totals = {"lectures": keys, "segments": len(todo), "concepts": 0, "defined": 0, "relations": 0,
              "no_answer": [], "unresolved": {"turn 1": [], "turn 2": []}, "retried": {"turn 1": 0, "turn 2": 0},
              "lost": {"concepts": 0, "triples": 0}, "added": {"concepts": 0, "triples": 0}, "flags": {}}
    for k in keys:
        cmap, rmap, checks, text = {}, {}, {}, []
        for s in segs[k]:
            text.append(f"{s['id']}  {s['subgoal']}")
            if s["id"] not in state:
                text.append("  (no facts)\n")
                continue
            st = state[s["id"]]
            fids = [f["id"] for f in s["facts"]]
            flags = check_all(st["concepts"], st["relations"], [f["text"] for f in s["facts"]], st["flags"])
            ids = {c["name"]: f"{s['id']}/C{j}" for j, c in enumerate(st["concepts"])}
            for c in st["concepts"]:
                cmap[ids[c["name"]]] = {"name": c["name"], "aliases": c["aliases"],
                                        "facts": [fids[i - 1] for i in c["facts"]], "defined": c["defined"]}
                text.append(f"  {ids[c['name']].rsplit('/', 1)[1]:<4} {c['name']}"
                            + (f" ({', '.join(c['aliases'])})" if c["aliases"] else "")
                            + (" [defined]" if c["defined"] else "")
                            + f"  facts {', '.join(fids[i - 1].rsplit('/', 1)[1] for i in c['facts'])}")
            for j, r in enumerate(st["relations"]):
                rid = f"{s['id']}/R{j}"
                rf = [fids[i - 1] for i in r["facts"] if 1 <= i <= len(fids)]
                rmap[rid] = {"subject": ids[r["subject"]], "label": r["label"], "object": ids[r["object"]],
                             "facts": rf}
                text.append(f"  R{j:<3} {_triple(r)}  ({', '.join(f.rsplit('/', 1)[1] for f in rf)})")
            named = {kind: v for kind, v in flags.items() if v}
            checks[s["id"]] = {"facts": len(fids), "concepts": len(st["concepts"]),
                               "defined": sum(c["defined"] for c in st["concepts"]),
                               "relations": len(st["relations"]), "errors": st["errors"],
                               "unresolved": st["unresolved"], "retries": st["retries"],
                               "flag_counts": {kind: len(v) for kind, v in named.items()}, "flags": named}
            if st["errors"]:
                text.append("  no answer: " + "; ".join(st["errors"]))
            if named:
                text.append("  checks: " + "; ".join(f"{kind} {len(v)}" for kind, v in named.items()))
            for turn, rl in st["retries"].items():
                text.append(f"  retried {turn}: {rl['attempts']} attempts, kept {rl['kept'] or 'none'}; "
                            f"lost {rl['lost'] or 'nothing'}; added {rl['added'] or 'nothing'}")
            for turn, problems in st["unresolved"].items():
                text.append(f"  unresolved {turn}: " + " ".join(problems))
            text.append("")
            totals["concepts"] += len(st["concepts"])
            totals["defined"] += checks[s["id"]]["defined"]
            totals["relations"] += len(st["relations"])
            if st["errors"]:
                totals["no_answer"].append(s["id"])
            for turn in st["unresolved"]:
                totals["unresolved"][turn].append(s["id"])
            for turn, rl in st["retries"].items():
                what = "concepts" if turn == "turn 1" else "triples"
                totals["retried"][turn] += 1
                totals["lost"][what] += len(rl["lost"])
                totals["added"][what] += len(rl["added"])
            for kind, v in named.items():
                totals["flags"][kind] = totals["flags"].get(kind, 0) + len(v)
        stem = lec.stem_of(k)
        (od / "concept_maps" / f"{stem}.json").write_text(json.dumps(cmap, indent=1, ensure_ascii=False) + "\n")
        (od / "relations" / f"{stem}.json").write_text(json.dumps(rmap, indent=1, ensure_ascii=False) + "\n")
        (od / "checks" / f"{stem}.json").write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
        (od / "text" / f"{stem}.txt").write_text("\n".join(text) + "\n")
    (od / "checks" / "summary.json").write_text(json.dumps(totals, indent=1, ensure_ascii=False) + "\n")
    totals["wall_s"] = round(time.time() - t0, 1)
    print(f"{totals['segments']} segments, {totals['concepts']} concepts ({totals['defined']} defined), "
          f"{totals['relations']} relationships, {totals['wall_s']} s"
          + (f"; no answer: {totals['no_answer']}" if totals["no_answer"] else ""))
    print(f"retried: turn 1 {totals['retried']['turn 1']}, turn 2 {totals['retried']['turn 2']}; "
          f"lost {totals['lost']['concepts']} concepts, {totals['lost']['triples']} triples; "
          f"added {totals['added']['concepts']} concepts, {totals['added']['triples']} triples")
    print(f"unresolved: turn 1 {totals['unresolved']['turn 1'] or 'none'}, "
          f"turn 2 {totals['unresolved']['turn 2'] or 'none'}")
    print(f"checks: {totals['flags'] or 'none'}")
    return totals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--only", help="lectures, e.g. 1,4,16")
    ap.add_argument("--seed", type=int, help="sampling seed (default: the config's); for repeat runs")
    ap.add_argument("--out", help="output folder (default: output/<course>/stage_2c_concepts); for repeat runs")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, lec.parse_only(a.only) if a.only else None, a.seed, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
