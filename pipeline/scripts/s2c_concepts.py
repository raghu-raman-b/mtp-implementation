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
          text/lec_<n>.txt           both, readable: per segment its concepts, then its triples with names
          checks/lec_<n>.json        the code checks per segment (below)
          llm/cache.jsonl, calls.jsonl

One conversation per segment with facts (segments without facts are skipped):
1. Turn 1: the segment's verified facts, numbered [1]..[n], in; concepts out: name, aliases, facts (numbers),
   defined. The fact numbers are mapped back to fact IDs in code.
2. Code checks on the answer. The only change code makes: concepts with the same name (case and spacing ignored)
   are merged into the first (aliases and facts joined, defined if either is); fact numbers out of range are dropped.
3. Turn 2: the conversation continued (turn 1's prompt and answer as the model gave it), then the relations prompt
   with the checked concept list; triples out: facts, subject, label, object. The answer schema limits subject and
   object to the checked concept names.
4. Code checks on the triples. Then concept IDs "<segment>/C<k>" in the checked order, relationship IDs
   "<segment>/R<k>" in the model's order.

Code checks, reported per segment (none drops or changes anything except the two named in step 2):
  out_of_range      a fact number outside 1..n (concepts or triples)
  merged            the same name twice
  name_not_in_facts, alias_not_in_facts   a concept's name or alias that appears in none of its own facts
  alias_not_written an alias written in none of the segment's facts
  fact_without_concept   a fact that no concept cites
  no_shared_fact    a triple none of whose cited facts is cited by both its concepts (also flags a triple the
                    model states across two facts, one naming each concept)
  reverse           a triple whose reverse (object to subject) is also there (a triple from a concept to itself
                    is its own reverse, so it is flagged here)
  vague_label       a label such as "is related to", "is associated with", "involves"
  no_triple         a concept in no triple
A term "appears" in a fact when its words do, ignoring case, hyphens and a plural ending.
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

from scripts import course_meta, lectures as lec, s2a_fact_extraction as s2a, s2b_verify_facts as s2b  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

EXTRACT = ROOT / "prompts" / "concept_extraction.txt"
RELATE = ROOT / "prompts" / "concept_relations.txt"
VAGUE = re.compile(r"^\s*(?:is |are )?(?:related to|associated with|involves?|connected (?:to|with)|linked (?:to|with)|"
                   r"relates? to|has to do with|concerns?)\s*$", re.I)


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
    return Request(prompt=extraction_prompt(course, seg), key=seg["id"], schema=concept_schema(len(seg["facts"])),
                   sampling={} if seed is None else {"seed": seed}, meta={"lecture": seg["key"]})


def _norm(name: str) -> str:
    return " ".join(name.lower().split())


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
            first["aliases"] += [a for a in c["aliases"] if a not in first["aliases"]]
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
    return Request(prompt=first.prompt, key=first.key, schema=relation_schema([c["name"] for c in concepts], n),
                   followup=[{"role": "assistant", "content": answer},
                             {"role": "user", "content": RELATE.read_text().replace("{concepts}",
                                                                                    concept_list(concepts))}],
                   sampling=first.sampling, meta=first.meta)


# ---------------------------------------------------------------- checks
def appears(term: str, text: str) -> bool:
    """The term's words in the text, ignoring case, hyphens and a plural ending."""
    words = re.findall(r"[a-z0-9]+", term.lower())
    if not words:
        return False
    pat = r"(?<![a-z0-9])" + r"[\s-]+".join(map(re.escape, words)) + r"(?:s|es)?(?![a-z0-9])"
    return re.search(pat, text.lower()) is not None


def check_all(concepts: list[dict], relations: list[dict], facts: list[str], flags: dict) -> dict:
    """The remaining checks on the checked concepts (fact numbers 1..n) and the triples (names)."""
    n = len(facts)
    flags = dict(flags, name_not_in_facts=[], alias_not_in_facts=[], alias_not_written=[], fact_without_concept=[],
                 no_shared_fact=[], reverse=[], vague_label=[], no_triple=[])
    for c in concepts:
        own = [facts[i - 1] for i in c["facts"]]
        if not any(appears(c["name"], t) for t in own):
            flags["name_not_in_facts"].append(c["name"])
        for a in c["aliases"]:
            if not any(appears(a, t) for t in own):
                flags["alias_not_in_facts"].append({"concept": c["name"], "alias": a})
            if not any(appears(a, t) for t in facts):
                flags["alias_not_written"].append({"concept": c["name"], "alias": a})
    cited = {i for c in concepts for i in c["facts"]}
    flags["fact_without_concept"] = [i for i in range(1, n + 1) if i not in cited]
    by_name = {c["name"]: c for c in concepts}
    pairs = {(r["subject"], r["object"]) for r in relations}
    in_triple = set()
    for k, r in enumerate(relations):
        bad = [i for i in r["facts"] if not 1 <= i <= n]
        if bad:
            flags["out_of_range"].append({"triple": k, "facts": bad})
        s, o = by_name.get(r["subject"]), by_name.get(r["object"])
        in_triple |= {r["subject"], r["object"]}
        if s and o and not set(r["facts"]) & set(s["facts"]) & set(o["facts"]):
            flags["no_shared_fact"].append(k)
        if (r["object"], r["subject"]) in pairs:
            flags["reverse"].append(k)
        if VAGUE.match(r["label"]):
            flags["vague_label"].append(k)
    flags["no_triple"] = [c["name"] for c in concepts if c["name"] not in in_triple]
    return flags


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
        if not res.ok:
            state[s["id"]] = {"concepts": [], "relations": [], "flags": {}, "errors": res.errors}
            continue
        concepts, flags = check_concepts(res.parsed["concepts"], n)
        state[s["id"]] = {"concepts": concepts, "relations": [], "flags": flags, "errors": []}
        if concepts:
            second.append((s, relation_request(req, res.content, concepts, n)))
    print(f"2c turn 2: relationships in {len(second)} segments", flush=True)
    for (s, _), res in zip(second, llm.generate_many([r for _, r in second], cache_file=cache, log_file=log)):
        if res.ok:
            state[s["id"]]["relations"] = res.parsed["relations"]
        else:
            state[s["id"]]["errors"] += [f"turn 2: {e}" for e in res.errors]
    totals = {"segments": len(todo), "concepts": 0, "defined": 0, "relations": 0, "no_answer": [], "flags": {}}
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
                text.append(f"  R{j:<3} {r['subject']} | {r['label']} | {r['object']}"
                            f"  ({', '.join(f.rsplit('/', 1)[1] for f in rf)})")
            named = {kind: v for kind, v in flags.items() if v}
            checks[s["id"]] = {"facts": len(fids), "concepts": len(st["concepts"]),
                               "defined": sum(c["defined"] for c in st["concepts"]),
                               "relations": len(st["relations"]), "errors": st["errors"],
                               "flag_counts": {kind: len(v) for kind, v in named.items()}, "flags": named}
            if named:
                text.append("  checks: " + "; ".join(f"{kind} {len(v)}" for kind, v in named.items()))
            text.append("")
            totals["concepts"] += len(st["concepts"])
            totals["defined"] += checks[s["id"]]["defined"]
            totals["relations"] += len(st["relations"])
            if st["errors"]:
                totals["no_answer"].append(s["id"])
            for kind, v in named.items():
                totals["flags"][kind] = totals["flags"].get(kind, 0) + len(v)
        stem = lec.stem_of(k)
        (od / "concept_maps" / f"{stem}.json").write_text(json.dumps(cmap, indent=1, ensure_ascii=False) + "\n")
        (od / "relations" / f"{stem}.json").write_text(json.dumps(rmap, indent=1, ensure_ascii=False) + "\n")
        (od / "checks" / f"{stem}.json").write_text(json.dumps(checks, indent=1, ensure_ascii=False) + "\n")
        (od / "text" / f"{stem}.txt").write_text("\n".join(text) + "\n")
    totals["wall_s"] = round(time.time() - t0, 1)
    print(f"{totals['segments']} segments, {totals['concepts']} concepts ({totals['defined']} defined), "
          f"{totals['relations']} relationships, {totals['wall_s']} s"
          + (f"; no answer: {totals['no_answer']}" if totals["no_answer"] else ""))
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
