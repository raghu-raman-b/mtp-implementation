"""Stage 3b: the concept registry, step 3: which entries of each cluster are the same concept (one model call each).

    python scripts/s3b_same.py nptel_vr --llm configs/qwen38_27b_vllm.json [--out DIR]

Reads   output/<course>/stage_3_registry/clusters.json   (s3a: entries and clusters)
        output/<course>/stage_2b_verify_facts/fact_maps/lec_<n>.json, course.json (the course block)
Prompt  prompts/concept_same.txt: {course} (the course block, scripts/course_meta.py), {entries}
Writes  output/<course>/stage_3_registry/ (or --out)
          clusters.json        each cluster gets "groups" [{"entries": [entry IDs], "name", "reason"}], "ok",
                               "errors", "attempts"; settings get "same_model"
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
The answer is constrained by a JSON schema that follows the prompt's ANSWER section: {"groups": [{"entries": [numbers
1..n], "reason": str, "name": one of the cluster's names}]}, fields in the prompt's order. The schema cannot say
that every number appears once or that a group's name is one of its own entries' names, so a check does, and a
failing answer is retried with the problems shown to the model (LLM API, feedback). A cluster still without a valid
answer keeps its entries apart (the prompt's rule: a wrong merge costs more than a missed one); its "ok" is false
and s3c logs it.
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

PROMPT = ROOT / "prompts" / "concept_same.txt"
FACT_CAP = 8         # facts shown per entry (defining facts first)


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


def schema(n: int, names: list[str]) -> dict:
    """The prompt's answer format: groups, each with entries (1..n), reason, name (one of the cluster's names)."""
    return {"type": "object", "additionalProperties": False, "required": ["groups"],
            "properties": {"groups": {"type": "array", "minItems": 1, "maxItems": n, "items": {
                "type": "object", "additionalProperties": False, "required": ["entries", "reason", "name"],
                "properties": {"entries": {"type": "array", "minItems": 1,
                                           "items": {"type": "integer", "minimum": 1, "maximum": n}},
                               "reason": {"type": "string"},
                               "name": {"type": "string", "enum": names}}}}}}


def problems(answer, entries: list[dict]) -> list[str]:
    """What is wrong with a parsed answer: entry numbers missing, repeated or out of range; a group named with a name
    of none of its entries."""
    n, out = len(entries), []
    groups = answer.get("groups") if isinstance(answer, dict) else None
    if not isinstance(groups, list) or not groups:
        return ["the answer has no groups"]
    seen: dict[int, int] = {}
    for g in groups:
        for k in g.get("entries", []):
            seen[k] = seen.get(k, 0) + 1
    bad = sorted(k for k in seen if not (isinstance(k, int) and 1 <= k <= n))
    missing = [k for k in range(1, n + 1) if k not in seen]
    twice = sorted(k for k, c in seen.items() if c > 1 and k not in bad)
    if bad:
        out.append(f"entry numbers out of range 1..{n}: {bad}")
    if missing:
        out.append(f"entries in no group: {missing}")
    if twice:
        out.append(f"entries in more than one group: {twice}")
    for g in groups:
        own = {x.lower() for k in g.get("entries", []) if isinstance(k, int) and 1 <= k <= n
               for x in entries[k - 1]["names"]}
        if str(g.get("name", "")).lower() not in own:
            out.append(f"group {g.get('entries')}: the name {g.get('name')!r} is not a name of its entries")
    return out


def request(course: str, kid: str, entries: list[dict], facts: dict) -> Request:
    names = list(dict.fromkeys(n for e in entries for n in e["names"]))
    return Request(prompt=build_prompt(course, entries, facts), key=kid, schema=schema(len(entries), names),
                   check=lambda a: problems(a, entries), feedback=True, meta={"cluster": kid})


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
    totals = {"clusters": len(kids), "no_answer": [], "merged_groups": 0, "entries_merged": 0}
    for kid, res in zip(kids, results):
        k = data["clusters"][kid]
        es = k["entries"]
        if res.ok:
            k["groups"] = [{"entries": [es[i - 1] for i in sorted(g["entries"])], "name": g["name"],
                            "reason": g["reason"]} for g in res.parsed["groups"]]
            k["groups"].sort(key=lambda g: es.index(g["entries"][0]))
            k["ok"], k["errors"] = True, []
        else:
            k["groups"] = [{"entries": [e], "name": E[e]["name"], "reason": "kept apart: no valid answer"}
                           for e in es]
            k["ok"], k["errors"] = False, res.errors
            totals["no_answer"].append(kid)
        k["attempts"] = res.attempts
        several = [g for g in k["groups"] if len(g["entries"]) > 1]
        totals["merged_groups"] += len(several)
        totals["entries_merged"] += sum(len(g["entries"]) for g in several)
    data["settings"]["same_model"] = llm.model
    s3a.save(od, data)
    totals["wall_s"] = round(time.time() - t0, 1)
    print(f"3b: {totals['merged_groups']} groups of several entries ({totals['entries_merged']} entries), "
          f"{totals['wall_s']} s" + (f"; no valid answer (kept apart): {totals['no_answer']}"
                                     if totals["no_answer"] else ""))
    return totals


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
