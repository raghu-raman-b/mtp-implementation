"""Stage 3b: the concept registry, step 3: which entries of each cluster are the same concept (one model call each).

    python scripts/s3b_same.py nptel_vr --llm configs/qwen38_27b_vllm.json [--out DIR]

Reads   output/<course>/stage_3_registry/clusters.json   (s3a: entries and clusters)
        output/<course>/stage_2b_verify_facts/fact_maps/lec_<n>.json, course.json (the course block)
Prompt  prompts/concept_same.txt: {course} (the course block, scripts/course_meta.py), {entries}
Writes  output/<course>/stage_3_registry/ (or --out)
          clusters.json        each cluster gets "groups" [{"entries": [entry IDs], "name", "reason"}], "ok",
                               "unresolved", "no_answer", "errors", "attempts", and "retry" when it was retried;
                               settings get "same_model"; the file gets "same_checks" (the totals below)
          text/clusters.txt    the clusters with the model's groups
          llm/cache.jsonl, calls.jsonl

One call per cluster of s3a (entries without a candidate are not sent). The entries are numbered [1]..[n] in course
order, each as:
    [2] head-mounted display
    other names: HMD, headset
    lectures: 1, 4
    facts:
    * <a fact of a segment concept with defined=true>
    - <another fact>
    (3 more facts not shown)
with its defining facts first (marked *), then the others, in course order, at most FACT_CAP in all.

The group's name (decision D8: a concept's name is never an acronym). An entry's own name is the name on its first
line (the wording most of its 2c segment concepts use: a 2c name, never an alias). allowed_names(group):
  1. the group's entries' own names that are not acronyms (is_acronym, scripts/fact_checks.py);
  2. when every entry of the group is named by an acronym: the non-acronym names among their other names;
  3. when there is none either: the entries' own names (an acronym whose full term the course never writes).
The answer is constrained by a JSON schema that follows the prompt's ANSWER section: {"groups": [{"entries": [numbers
1..n], "reason": str, "name": str}]}, fields in the prompt's order; the name's enum is every name some group of the
cluster could be allowed (name_enum). The schema cannot say that every number appears once or that a group's name is
allowed for that group, so problems() does, and a failing answer is retried with the problems shown to the model (LLM
API, feedback).

When every attempt fails (decision D12), the attempt with the fewest problems is kept, repaired in code (repair()),
and the cluster is flagged "unresolved" with its remaining problems: numbers out of range dropped; an entry in
several groups or in none kept apart (a group of its own: a wrong merge costs more than a missed one); a name that
is not allowed replaced by the group's first allowed name. Only a cluster without any parsed answer has "no_answer":
its entries are kept apart. "retry" records, for a retried cluster, the groups ("E0001+E0004: name") lost and added
between the first and the final attempt.

same_checks: {"clusters", "valid", "unresolved": [cluster IDs], "no_answer": [cluster IDs], "retried",
"changed_by_retry", "lost", "added" (groups, summed over the retried clusters), "acronym_names": [the groups named by
an acronym under rule 3]}.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, s3a_candidates as s3a  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402
from scripts.llm.client import _parse_json  # noqa: E402

PROMPT = ROOT / "prompts" / "concept_same.txt"
FACT_CAP = 8         # facts shown per entry (defining facts first)
is_acronym = s3a.is_acronym


# ---------------------------------------------------------------- prompt
def entry_block(k: int, entry: dict, facts: dict, cap: int = FACT_CAP) -> str:
    defining = [f for f in entry["defining_facts"] if f in facts]
    others = [f for f in entry["facts"] if f in facts and f not in set(defining)]
    shown = ([("*", f) for f in defining] + [("-", f) for f in others])[:cap]
    lines = [f"[{k}] {entry['name']}",
             "other names: " + (", ".join(entry["names"][1:]) or "none"),
             "lectures: " + ", ".join(entry["lectures"]),
             "facts:"] + [f"{mark} {facts[f]}" for mark, f in shown]
    rest = len(defining) + len(others) - len(shown)
    if rest > 0:
        lines.append(f"({rest} more facts not shown)")
    return "\n".join(lines)


def build_prompt(course: str, entries: list[dict], facts: dict) -> str:
    block, template = course_meta.course_prompt(course), PROMPT.read_text()
    if not block:
        template = template.replace("{course}\n", "")
    body = "\n\n".join(entry_block(k, e, facts) for k, e in enumerate(entries, 1))
    return template.replace("{course}", block).replace("{entries}", body)   # last: fact text is never replaced


# ---------------------------------------------------------------- the group's name
def _acr(name: str) -> bool:
    return is_acronym(name.strip())


def _dedupe(names) -> list[str]:
    return list(dict.fromkeys(n for n in names if n.strip()))


def allowed_names(entries: list[dict]) -> list[str]:
    """The names a group of these entries may take (module docstring, rules 1 to 3), in course order."""
    own = _dedupe(e["name"] for e in entries if not _acr(e["name"]))
    if own:
        return own
    other = _dedupe(n for e in entries for n in e["names"][1:] if not _acr(n))
    return other or _dedupe(e["name"] for e in entries)


def name_enum(entries: list[dict]) -> list[str]:
    """Every name that some group of the cluster's entries could be allowed: the schema's enum."""
    out = []
    for e in entries:
        if not _acr(e["name"]):
            out.append(e["name"])
        else:
            out += [n for n in e["names"][1:] if not _acr(n)] or [e["name"]]
    return _dedupe(out)


def schema(n: int, names: list[str]) -> dict:
    """The prompt's answer format: groups, each with entries (1..n), reason, name (from the cluster's name_enum)."""
    return {"type": "object", "additionalProperties": False, "required": ["groups"],
            "properties": {"groups": {"type": "array", "minItems": 1, "maxItems": n, "items": {
                "type": "object", "additionalProperties": False, "required": ["entries", "reason", "name"],
                "properties": {"entries": {"type": "array", "minItems": 1,
                                           "items": {"type": "integer", "minimum": 1, "maximum": n}},
                               "reason": {"type": "string"},
                               "name": {"type": "string", "enum": names}}}}}}


# ---------------------------------------------------------------- checks
def _groups(answer) -> list | None:
    groups = answer.get("groups") if isinstance(answer, dict) else None
    return groups if isinstance(groups, list) and groups else None


def _nums(g: dict, n: int) -> list[int]:
    return [k for k in g.get("entries", []) if isinstance(k, int) and 1 <= k <= n]


def problems(answer, entries: list[dict]) -> list[str]:
    """What is wrong with a parsed answer: entry numbers missing, repeated or out of range; a group whose name is not
    allowed for it (allowed_names: an acronym while a full name exists, another entry's name, an alias)."""
    n, out = len(entries), []
    groups = _groups(answer)
    if groups is None:
        return ["the answer has no groups"]
    seen: dict = {}
    for g in groups:
        for k in g.get("entries", []):
            seen[k] = seen.get(k, 0) + 1
    bad = sorted((k for k in seen if not (isinstance(k, int) and 1 <= k <= n)), key=str)
    missing = [k for k in range(1, n + 1) if k not in seen]
    twice = sorted(k for k, c in seen.items() if c > 1 and k not in bad)
    if bad:
        out.append(f"entry numbers out of range 1..{n}: {bad}")
    if missing:
        out.append(f"entries in no group: {missing}")
    if twice:
        out.append(f"entries in more than one group: {twice}")
    for g in groups:
        nums = _nums(g, n)
        if not nums:
            continue
        allowed = allowed_names([entries[k - 1] for k in nums])
        name = str(g.get("name", ""))
        if name.lower() not in {a.lower() for a in allowed}:
            why = (f'is an acronym; a concept\'s name is the full term in words, and the acronym stays among the '
                   f'other names' if _acr(name) and not all(_acr(a) for a in allowed)
                   else "is not the name on the first line of one of its entries")
            out.append(f'group {g.get("entries")}: the name "{name}" {why}. Name it '
                       + " or ".join(f'"{a}"' for a in allowed) + ".")
    return out


def repair(answer, entries: list[dict]) -> list[dict]:
    """The groups of an answer that failed its check, made usable (module docstring): [{"entries": [numbers],
    "name", "reason"}] covering 1..n exactly once, in the answer's order, then the entries kept apart."""
    n = len(entries)
    groups = _groups(answer) or []
    count: dict[int, int] = {}
    for g in groups:
        for k in set(_nums(g, n)):
            count[k] = count.get(k, 0) + 1
    out, placed = [], set()
    for g in groups:
        nums = sorted(k for k in set(_nums(g, n)) if count[k] == 1)
        if not nums:
            continue
        allowed = allowed_names([entries[k - 1] for k in nums])
        name = str(g.get("name", ""))
        name = next((a for a in allowed if a.lower() == name.lower()), allowed[0])
        out.append({"entries": nums, "name": name, "reason": str(g.get("reason", ""))})
        placed |= set(nums)
    for k in range(1, n + 1):
        if k not in placed:
            why = "in several groups of the answer" if count.get(k, 0) > 1 else "in no group of the answer"
            out.append({"entries": [k], "name": allowed_names([entries[k - 1]])[0],
                        "reason": f"kept apart: {why} (unresolved answer)"})
    return out


def request(course: str, kid: str, entries: list[dict], facts: dict) -> Request:
    return Request(prompt=build_prompt(course, entries, facts), key=kid, schema=schema(len(entries), name_enum(entries)),
                   check=lambda a: problems(a, entries), feedback=True, meta={"cluster": kid})


def group_items(groups: list[dict], es: list[str]) -> list[str]:
    """Groups as readable items for the retry log: "E0001+E0004: name" (numbers out of range left out)."""
    return [f"{'+'.join(es[k - 1] for k in sorted(set(_nums(g, len(es)))))}: {g.get('name', '')}"
            for g in groups if _nums(g, len(es))]


def retry_log(res, es: list[str]) -> dict | None:
    """For a retried cluster: the groups lost and added between the first and the final attempt."""
    if not res.history:
        return None
    try:
        first = _groups(_parse_json(res.history[0]["answer"])) or []
    except ValueError:
        first = []
    final = _groups(res.parsed) or []
    a, b = group_items(first, es), group_items(final, es)
    return {"lost": [x for x in a if x not in b], "added": [x for x in b if x not in a]}


# ---------------------------------------------------------------- run
def run(course: str, llm: LLM, out: Path | None = None) -> dict:
    """The model's grouping of every cluster in clusters.json (written by s3a)."""
    t0 = time.time()
    od = Path(out) if out else s3a.out_dir(course)
    data = s3a.load(od, course)
    facts = s3a.load_facts(course, data["settings"]["lectures"])
    E = data["entries"]
    kids = list(data["clusters"])
    reqs = [request(course, kid, [E[e] for e in data["clusters"][kid]["entries"]], facts) for kid in kids]
    print(f"3b: {len(reqs)} clusters with {llm.model}", flush=True)
    results = llm.generate_many(reqs, cache_file=od / "llm" / "cache.jsonl", log_file=od / "llm" / "calls.jsonl")
    totals = {"clusters": len(kids), "valid": 0, "unresolved": [], "no_answer": [], "retried": 0,
              "changed_by_retry": 0, "lost": 0, "added": 0, "acronym_names": []}
    merged_groups = entries_merged = 0
    for kid, res in zip(kids, results):
        k = data["clusters"][kid]
        es = k["entries"]
        ents = [E[e] for e in es]
        k.pop("retry", None)
        if res.ok:
            groups = res.parsed["groups"]
            k.update(ok=True, unresolved=[], no_answer=False, errors=[])
            totals["valid"] += 1
        elif _groups(res.parsed) is not None:
            groups = repair(res.parsed, ents)
            k.update(ok=False, unresolved=problems(res.parsed, ents), no_answer=False, errors=res.errors)
            totals["unresolved"].append(kid)
        else:
            groups = [{"entries": [i], "name": allowed_names([e])[0], "reason": "kept apart: no answer"}
                      for i, e in enumerate(ents, 1)]
            k.update(ok=False, unresolved=[], no_answer=True, errors=res.errors)
            totals["no_answer"].append(kid)
        k["groups"] = [{"entries": [es[i - 1] for i in sorted(set(g["entries"]))], "name": g["name"],
                        "reason": g["reason"]} for g in groups]
        k["groups"].sort(key=lambda g: es.index(g["entries"][0]))
        k["attempts"] = res.attempts
        log = retry_log(res, es)
        if log is not None:
            k["retry"] = log
            totals["retried"] += 1
            totals["changed_by_retry"] += bool(log["lost"] or log["added"])
            totals["lost"] += len(log["lost"])
            totals["added"] += len(log["added"])
        for g in k["groups"]:
            if _acr(g["name"]):
                totals["acronym_names"].append(f"{kid}: {g['name']}")
        several = [g for g in k["groups"] if len(g["entries"]) > 1]
        merged_groups += len(several)
        entries_merged += sum(len(g["entries"]) for g in several)
    data["settings"]["same_model"] = llm.model
    data["same_checks"] = totals
    s3a.save(od, data)
    wall = round(time.time() - t0, 1)
    print(f"3b: {merged_groups} groups of several entries ({entries_merged} entries), {wall} s; "
          f"{totals['retried']} clusters retried ({totals['changed_by_retry']} changed)"
          + (f"; unresolved (best answer kept, repaired): {totals['unresolved']}" if totals["unresolved"] else "")
          + (f"; no answer (kept apart): {totals['no_answer']}" if totals["no_answer"] else ""))
    return {**totals, "merged_groups": merged_groups, "entries_merged": entries_merged, "wall_s": wall}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--out", help="the stage folder (default: output/<course>/stage_3_registry)")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
