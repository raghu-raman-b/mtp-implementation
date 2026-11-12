"""Stage 4a: the definition of every concept of the registry, from the facts that name it (one call per concept).

    python scripts/s4a_definitions.py nptel_vr --llm configs/qwen38_27b_vllm.json [--cap 40] [--seed 1 --out DIR]

Reads   output/<course>/stage_3_registry/concepts.json         {"C0001": {"name", "aliases", "facts", "lectures",
                                                                 "segments", "defined_in", "merged": [...]}}
        output/<course>/stage_2c_concepts/concept_maps/lec_<n>.json   (which segment concepts had defined=true)
        output/<course>/stage_2b_verify_facts/fact_maps/lec_<n>.json  (the fact texts)
        input/<course>/input/course.json                        (the course block)
Prompt  prompts/concept_definition.txt: {course}, {name}, {aliases}, {facts}
Writes  output/<course>/stage_4a_definitions/ (or --out)
          definitions.json  {"C0001": {"name", "definition", "defined", "facts": [fact IDs it is built from],
                             "misplaced": [fact IDs], "shown": [fact IDs given to the model, in lecture order],
                             "defining": [defining fact IDs], "total_facts": n, "capped": bool,
                             "unresolved": [the problems left in a kept answer], "errors": [no answer: why]}}
          definitions.txt   per concept: name, definition, the facts it cites and the misplaced ones, flags, retries
          checks.json       totals, the code checks per concept, and per retried concept what the retry changed
          llm/cache.jsonl, calls.jsonl

The facts given to the model. The "defining facts" of a concept are the facts of the segment concepts merged into it
(registry "merged") whose segment concept had defined=true in 2c. When the concept has more facts than the cap
(--cap, default 40), the facts kept are: the defining facts first (in lecture order; if they alone pass the cap, the
first `cap` of them), then the other facts in lecture order until the cap. The kept facts are then shown in lecture
order (as the prompt says), numbered [1]..[n], each with its lecture; defining facts are marked *:
    [3]* (lecture 4) Virtual reality (VR) is ...
and, when capped, a last line "(<n> more facts not shown)". The model answers with numbers; code maps them back to
fact IDs through the shown list (never the full list).

Code checks (decision D12). The answer is checked, and an answer with any of these problems is retried with the
problems shown to the model (LLM API, feedback; the config's retries):
  outside_list      a cited or misplaced number outside 1..n (a fact the model was not given)
  empty_definition  the definition is empty or only spaces
  empty_facts       "facts" is empty: the definition is built from no fact
  in_both           a number in both "facts" and "misplaced"
  name_absent       the concept's name is not in the definition (case, hyphens and punctuation ignored; a plural
                    ending allowed)
  lecture_reference "the lecturer" or "this lecture" in the definition
When every attempt fails, the attempt with the fewest problems is kept (ties: the latest), its numbers outside 1..n
dropped, and its remaining problems listed under "unresolved" (and as flags in checks.json); only an answer that never
parses is "no answer" (an empty definition, "errors"). Reported only:
  defined_mismatch  "defined" here against the registry: defined=true but no segment defines it (defined_in empty),
                    or defined=false although defined_in names segments
  misplaced         not split: the concepts with facts that use the name for another thing
Per retried answer, checks.json "retries" holds what was lost and added between the first and the final attempt
(items "fact <ID>", "misplaced <ID>", "defined: <bool>", "definition: <text>"); totals count the retried answers, those
the retry changed, and the items lost and added.
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

from scripts import course_meta, lectures as lec  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402
from scripts.llm.client import _parse_json  # noqa: E402

PROMPT = ROOT / "prompts" / "concept_definition.txt"
CAP = 40


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_4a_definitions"


def registry_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_3_registry"


def stage_dir(course: str, stage: str) -> Path:
    return ROOT / "output" / course / stage


# ---------------------------------------------------------------- shared helpers (used by 4b, 4c, 4d)
def fill(template: str, **values: str) -> str:
    """Put the values into the template's {placeholders} in one pass (a value is never searched again, so text that
    happens to contain "{facts}" stays as it is). Every placeholder named must be in the template."""
    missing = [k for k in values if "{" + k + "}" not in template]
    if missing:
        raise ValueError(f"the prompt has no placeholder for {missing}")
    if not values.get("course", True):                  # no course block: drop its line
        template = template.replace("{course}\n", "")
    pat = re.compile(r"\{(" + "|".join(map(re.escape, values)) + r")\}")
    return pat.sub(lambda m: values[m[1]], template)


def lecture_of(item_id: str) -> str:
    """The lecture key of a sentence, segment, fact or concept-in-segment ID: "4/S1/F2" -> "4"."""
    return item_id.split("/", 1)[0]


def segment_of(item_id: str) -> str:
    """The segment of a fact or segment concept ID: "4/S1/F2" -> "4/S1"."""
    return "/".join(item_id.split("/")[:2])


def fact_order(fid: str) -> tuple:
    """Sort key of a fact (or segment concept) ID in course order: lecture, segment, number."""
    key, s, f = fid.split("/")
    return (lec.order(key), int(s[1:]), int(re.sub(r"\D", "", f)))


def lecture_label(key: str) -> str:
    """How a lecture is named in a prompt: "lecture 4", "tutorial 1", "tutorial 1 part 2"."""
    m = re.fullmatch(r"tut_(\d+)(?:_part(\d+))?", key)
    if m:
        return f"tutorial {m[1]}" + (f" part {m[2]}" if m[2] else "")
    return f"lecture {key}"


def load_registry(course: str) -> dict:
    """The stage 3 output: concepts, segment_concepts and relations (the last two may be absent: empty)."""
    d = registry_dir(course)
    out = {"concepts": json.loads((d / "concepts.json").read_text())}
    for name in ("segment_concepts", "relations"):
        p = d / f"{name}.json"
        out[name] = json.loads(p.read_text()) if p.exists() else {}
    return out


def registry_lectures(reg: dict) -> list[str]:
    """Every lecture a concept of the registry appears in, in course order."""
    keys = {k for c in reg["concepts"].values() for k in c["lectures"]}
    return sorted(keys, key=lec.order)


def load_per_lecture(course: str, stage: str, sub: str, keys) -> dict:
    """A stage's per-lecture maps joined into one dict (lectures without a file are skipped)."""
    out = {}
    for k in keys:
        p = stage_dir(course, stage) / sub / f"{lec.stem_of(k)}.json"
        if p.exists():
            out.update(json.loads(p.read_text()))
    return out


def load_facts(course: str, keys) -> dict:
    """The verified facts (2b) of the lectures: {fact ID: {"text", "evidence"}}."""
    return load_per_lecture(course, "stage_2b_verify_facts", "fact_maps", keys)


def load_concept_maps(course: str, keys) -> dict:
    """The segment concepts (2c) of the lectures: {"4/S1/C0": {"name", "aliases", "facts", "defined"}}."""
    return load_per_lecture(course, "stage_2c_concepts", "concept_maps", keys)


def answered(res) -> bool:
    """A result holds an answer to keep: it passed its check, or (decision D12) every attempt failed it but one parsed
    to an object (the client keeps the one with the fewest problems). Otherwise it is "no answer"."""
    return res.ok or (isinstance(res.parsed, dict) and res.finish != "length")


def first_answer(res):
    """The parsed first attempt of a retried request (None when it was not retried, or did not parse)."""
    if not res.history:
        return None
    try:
        return _parse_json(res.history[0]["answer"])
    except ValueError:
        return None


def retry_log(res, items) -> dict | None:
    """For a retried request (decision D12): the items lost and added between its first and its final attempt.
    items(answer) -> list of readable strings (an answer that did not parse: none)."""
    if not res.history:
        return None
    first, final = first_answer(res), res.parsed
    a = items(first) if isinstance(first, dict) else []
    b = items(final) if isinstance(final, dict) else []
    return {"attempts": res.attempts, "lost": [x for x in a if x not in b], "added": [x for x in b if x not in a]}


def count_retries(totals: dict, log: dict | None):
    """Add one retry log to a stage's totals: retried, changed_by_retry, lost, added."""
    for k in ("retried", "changed_by_retry", "lost", "added"):
        totals.setdefault(k, 0)
    if log is not None:
        totals["retried"] += 1
        totals["changed_by_retry"] += bool(log["lost"] or log["added"])
        totals["lost"] += len(log["lost"])
        totals["added"] += len(log["added"])


def defining_facts(concept: dict, cmaps: dict) -> list[str]:
    """The facts of the segment concepts merged into the concept that had defined=true, in course order (only facts
    the concept itself lists)."""
    own = set(concept["facts"])
    out = {f for m in concept.get("merged", []) for f in cmaps.get(m["segment_concept"], {}).get("facts", [])
           if cmaps.get(m["segment_concept"], {}).get("defined") and f in own}
    return sorted(out, key=fact_order)


# ---------------------------------------------------------------- the request
def select_facts(facts: list[str], defining: list[str], cap: int) -> list[str]:
    """The facts shown to the model, in lecture order: the defining facts first up to the cap, then the others in
    lecture order until the cap."""
    facts = sorted(dict.fromkeys(facts), key=fact_order)
    dset = set(defining)
    keep = [f for f in facts if f in dset][:cap]
    keep += [f for f in facts if f not in dset][:max(0, cap - len(keep))]
    return sorted(keep, key=fact_order)


def fact_lines(shown: list[str], defining: list[str], texts: dict, total: int | None = None) -> str:
    """The numbered facts; when the list was capped (total facts more than shown), a last line says how many are
    not shown."""
    dset = set(defining)
    lines = [f"[{i}]{'*' if f in dset else ''} ({lecture_label(lecture_of(f))}) {texts[f]['text']}"
             for i, f in enumerate(shown, 1)]
    if total is not None and total > len(shown):
        lines.append(f"({total - len(shown)} more facts not shown)")
    return "\n".join(lines)


def build_prompt(course: str, concept: dict, shown: list[str], defining: list[str], texts: dict,
                 total: int | None = None) -> str:
    return fill(PROMPT.read_text(), course=course_meta.course_prompt(course), name=concept["name"],
                aliases=", ".join(concept["aliases"]) or "none", facts=fact_lines(shown, defining, texts, total))


def schema(n: int) -> dict:
    nums = {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": n}}
    return {"type": "object", "additionalProperties": False, "required": ["facts", "definition", "defined", "misplaced"],
            "properties": {"facts": nums, "definition": {"type": "string"}, "defined": {"type": "boolean"},
                           "misplaced": nums}}


# ---------------------------------------------------------------- checks
LECTURE_REFERENCE = re.compile(r"\bthe lecturer\b|\bthis lecture\b", re.I)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def names_concept(definition: str, name: str) -> bool:
    """The concept's name is written in the definition: case, hyphens and punctuation ignored, a plural ending
    allowed ("Head-mounted displays (HMDs) are ..." names "head-mounted display")."""
    n = _norm(name)
    return bool(n) and re.search(r"(?<![a-z0-9])" + re.escape(n), _norm(definition)) is not None


def _ints(x) -> list:
    return [i for i in x if isinstance(i, int)] if isinstance(x, list) else []


def problems(answer: dict, n: int, name: str) -> list[tuple[str, str]]:
    """The problems that send a definition back to the model (module docstring): [(kind, message)]."""
    out = []
    facts, misplaced = _ints(answer.get("facts")), _ints(answer.get("misplaced"))
    definition = str(answer.get("definition", ""))
    outside = [i for i in facts + misplaced if not 1 <= i <= n]
    if outside:
        out.append(("outside_list", f"The numbers {outside} are not in the list of facts: use only the numbers 1 to "
                                    f"{n}."))
    if not definition.strip():
        out.append(("empty_definition", "The definition is empty. Write the definition from the facts."))
    if not facts:
        out.append(("empty_facts", '"facts" is empty. List the numbers of the facts the definition is built from.'))
    both = sorted(set(facts) & set(misplaced))
    if both:
        out.append(("in_both", f'The facts {both} are in both "facts" and "misplaced". A fact the definition is built '
                               f'from is not misplaced: put each fact in one list only.'))
    if definition.strip() and not names_concept(definition, name):
        out.append(("name_absent", f'The definition does not contain the name "{name}". Begin with the name '
                                   f'exactly as given.'))
    refs = sorted({m.group(0).lower() for m in LECTURE_REFERENCE.finditer(definition)})
    if refs:
        out.append(("lecture_reference", "The definition says " + " and ".join(f'"{r}"' for r in refs)
                    + ". A definition does not refer to the lecture or the lecturer: say what the concept is."))
    return out


def answer_items(answer: dict, shown: list[str]) -> list[str]:
    """An answer as readable items for the retry log (numbers mapped to fact IDs; those outside the list left out)."""
    n = len(shown)
    return ([f"fact {shown[i - 1]}" for i in _ints(answer.get("facts")) if 1 <= i <= n]
            + [f"misplaced {shown[i - 1]}" for i in _ints(answer.get("misplaced")) if 1 <= i <= n]
            + [f"defined: {bool(answer.get('defined'))}", f"definition: {str(answer.get('definition', '')).strip()}"])


def check_answer(answer: dict, shown: list[str], defined_in: list[str], name: str | None = None) -> tuple[dict, dict]:
    """Map the answer's numbers to fact IDs through the shown list; the flags of the code checks (the problems of
    problems() when a name is given, then defined_mismatch and misplaced)."""
    n = len(shown)
    flags = {}
    outside = [i for i in _ints(answer["facts"]) + _ints(answer["misplaced"]) if not 1 <= i <= n]
    if outside:
        flags["outside_list"] = outside
    if not answer["definition"].strip():
        flags["empty_definition"] = True
    if name is not None:
        for kind, message in problems(answer, n, name):
            flags.setdefault(kind, message)
    if answer["defined"] and not defined_in:
        flags["defined_mismatch"] = "defined here, but no segment defines it (defined_in is empty)"
    elif not answer["defined"] and defined_in:
        flags["defined_mismatch"] = f"not defined here, but defined in {', '.join(defined_in)}"
    pick = lambda nums: list(dict.fromkeys(shown[i - 1] for i in _ints(nums) if 1 <= i <= n))  # noqa: E731
    mapped = {"definition": answer["definition"].strip(), "defined": answer["defined"],
              "facts": pick(answer["facts"]), "misplaced": pick(answer["misplaced"])}
    if mapped["misplaced"]:
        flags["misplaced"] = mapped["misplaced"]
    return mapped, flags


# ---------------------------------------------------------------- run
def run(course: str, llm: LLM, cap: int = CAP, seed: int | None = None, out: Path | None = None) -> dict:
    """A definition for every concept of the registry."""
    reg = load_registry(course)
    keys = registry_lectures(reg)
    texts, cmaps = load_facts(course, keys), load_concept_maps(course, keys)
    od = Path(out) if out else out_dir(course)
    (od / "llm").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    todo, reqs, missing = [], [], {}
    for cid, c in reg["concepts"].items():
        lost = [f for f in c["facts"] if f not in texts]
        if lost:
            missing[cid] = lost
        facts = [f for f in c["facts"] if f in texts]
        defining = defining_facts(c, cmaps)
        shown = select_facts(facts, defining, cap)
        todo.append((cid, c, facts, defining, shown))
        if shown:
            check = lambda a, n=len(shown), name=c["name"]: [m for _, m in problems(a, n, name)]  # noqa: E731
            reqs.append(Request(prompt=build_prompt(course, c, shown, defining, texts, len(facts)), key=cid,
                                schema=schema(len(shown)), check=check, feedback=True,
                                sampling={} if seed is None else {"seed": seed}, meta={"concept": cid}))
    print(f"4a: definitions of {len(reqs)} concepts with {llm.model} (cap {cap} facts)", flush=True)
    results = {r.key: r for r in llm.generate_many(reqs, cache_file=od / "llm" / "cache.jsonl",
                                                   log_file=od / "llm" / "calls.jsonl")}
    defs, checks, retries, text = {}, {}, {}, []
    totals = {"concepts": len(todo), "defined": 0, "capped": 0, "no_answer": [], "unresolved": [], "no_facts": [],
              "facts_missing": missing, "flags": {}, "retried": 0, "changed_by_retry": 0, "lost": 0, "added": 0}
    for cid, c, facts, defining, shown in todo:
        res = results.get(cid)
        rec = {"name": c["name"], "definition": "", "defined": False, "facts": [], "misplaced": [], "shown": shown,
               "defining": defining, "total_facts": len(facts), "capped": len(facts) > len(shown), "unresolved": [],
               "errors": []}
        flags, log = {}, None
        if not shown:
            totals["no_facts"].append(cid)
            rec["errors"] = ["no facts"]
        elif not answered(res):
            totals["no_answer"].append(cid)
            rec["errors"] = res.errors
        else:
            mapped, flags = check_answer(res.parsed, shown, c.get("defined_in", []), c["name"])
            rec.update(mapped)
            if not res.ok:
                rec["unresolved"] = [m for _, m in problems(res.parsed, len(shown), c["name"])] or res.errors
                totals["unresolved"].append(cid)
        if shown:
            log = retry_log(res, lambda a, shown=shown: answer_items(a, shown))
            count_retries(totals, log)
            if log is not None:
                retries[cid] = log
        defs[cid] = rec
        totals["defined"] += rec["defined"]
        totals["capped"] += rec["capped"]
        if flags:
            checks[cid] = flags
        for kind in flags:
            totals["flags"][kind] = totals["flags"].get(kind, 0) + 1
        num = {f: i for i, f in enumerate(shown, 1)}
        text.append(f"{cid}  {c['name']}" + (f" ({', '.join(c['aliases'])})" if c["aliases"] else "")
                    + f"  [{'defined' if rec['defined'] else 'not defined'}; defined_in: "
                    + f"{', '.join(c.get('defined_in', [])) or 'none'}; {len(shown)} of {len(facts)} facts shown]")
        text.append(f"  {rec['definition'] or '(no definition: ' + '; '.join(rec['errors']) + ')'}")
        if rec["facts"]:
            text.append("  built from: " + ", ".join(f"[{num[f]}] {f}" for f in rec["facts"]))
        if rec["misplaced"]:
            text.append("  misplaced: " + ", ".join(f"[{num[f]}] {f}" for f in rec["misplaced"]))
        if flags:
            text.append("  checks: " + "; ".join(k for k in flags))
        if rec["unresolved"]:
            text.append("  UNRESOLVED (best answer kept): " + " | ".join(rec["unresolved"]))
        if log is not None:
            text.append(f"  retried ({log['attempts']} attempts): lost {' | '.join(log['lost']) or 'nothing'}; "
                        f"added {' | '.join(log['added']) or 'nothing'}")
        text.append("")
    totals["misplaced"] = sorted(cid for cid, f in checks.items() if "misplaced" in f)
    (od / "definitions.json").write_text(json.dumps(defs, indent=1, ensure_ascii=False) + "\n")
    (od / "definitions.txt").write_text("\n".join(text) + "\n")
    (od / "checks.json").write_text(json.dumps({"cap": cap, "totals": totals, "concepts": checks, "retries": retries},
                                               indent=1, ensure_ascii=False) + "\n")
    print(f"{totals['concepts']} concepts, {totals['defined']} defined, {totals['capped']} capped, "
          f"{round(time.time() - t0, 1)} s; {totals['retried']} retried ({totals['changed_by_retry']} changed)"
          + (f"; unresolved (best answer kept): {totals['unresolved']}" if totals["unresolved"] else "")
          + (f"; no answer: {totals['no_answer']}" if totals["no_answer"] else ""))
    print(f"checks: {totals['flags'] or 'none'}")
    return totals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--cap", type=int, default=CAP, help=f"most facts given per concept (default {CAP})")
    ap.add_argument("--seed", type=int, help="sampling seed (default: the config's); for repeat runs")
    ap.add_argument("--out", help="output folder (default: output/<course>/stage_4a_definitions); for repeat runs")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, a.cap, a.seed, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
