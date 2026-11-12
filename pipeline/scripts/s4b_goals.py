"""Stage 4b: the goals of each lecture (objectives and the lecture goal), then the goals of the course.

    python scripts/s4b_goals.py nptel_vr --llm configs/qwen38_27b_vllm.json [--only 1,4,16] [--seed 1 --out DIR]

Reads   output/<course>/stage_1b_verify_segments/segment_maps/lec_<n>.json   (the segments and their sub-goals)
        output/<course>/stage_2c_concepts/concept_maps/lec_<n>.json         (each segment's concepts, defined or not)
        output/<course>/stage_3_registry/segment_concepts.json, concepts.json (the registry name of each)
        input/<course>/input/course.json, titles.tsv                         (course block, lecture titles)
Prompts prompts/lecture_goals.txt: {course}, {lecture_title}, {segments}
        prompts/course_goals.txt: {course}, {lectures}
Writes  output/<course>/stage_4b_goals/ (or --out)
          lecture_goals/lec_<n>.json  {"4/G": {"goal", "achieves", "objectives": ["4/O1", ...]},
                                       "4/O1": {"goal", "achieves", "segments": ["4/S0", "4/S1"]}, ...}
          course_goals.json           {"lectures": [keys], "reasoning", "goals": {"G1": {"goal", "achieves",
                                       "lectures": [keys]}, ...}}
          goals.txt                   the course goals, then per lecture its goal, objectives and their segments
          checks.json                 totals and the code checks per lecture and for the course (below)
          llm/cache.jsonl, calls.jsonl

1. One call per lecture (the lectures with 2c concept maps, or --only). Its segments are numbered [1]..[n] in
   lecture order, each with its sub-goal, the concepts it defines and the concepts it only uses (registry names; a
   concept is "defined" in a segment when one of its segment concepts there has defined=true). Segments without
   concepts are listed too ("none"). The answer's segment numbers are mapped back to segment IDs in code.
   IDs: objectives "<lecture>/O1", "<lecture>/O2", ... in the model's order (from 1, like the course goals); the
   lecture goal "<lecture>/G".
2. One call for the course: every lecture of the run with its number, title, goal and objectives (goals only; the
   "achieves" lines are not shown, as the prompt lists only goal and objectives). The answer's lectures are limited
   by the schema to the lecture keys ("4", "24b", "tut_1"). Course goal IDs "G1", "G2", ... in the model's order.

Code checks (reported; code only drops numbers out of range and repeats):
  lecture: out_of_range (a segment number outside 1..n), segment_twice (a segment in two objectives),
           not_consecutive (an objective whose segments are not one run), out_of_order (objectives not in lecture
           order), in_no_objective (a segment in no objective, with its sub-goal: allowed for a closing summary)
  course:  lecture_in_no_goal (every lecture should serve one), not_in_course_order (a goal's lectures out of order)
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

from scripts import course_meta, lectures as lec, s2a_fact_extraction as s2a  # noqa: E402
from scripts import s4a_definitions as s4a  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

LECTURE = ROOT / "prompts" / "lecture_goals.txt"
COURSE = ROOT / "prompts" / "course_goals.txt"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_4b_goals"


def objective_id(key: str, k: int) -> str:
    return f"{key}/O{k}"


def goal_id(key: str) -> str:
    return f"{key}/G"


# ---------------------------------------------------------------- lecture call
def load_segments(course: str, key: str, cmaps: dict, reg: dict) -> tuple[list[dict], list[str]]:
    """The lecture's segments in order, each with its sub-goal and the registry names of the concepts it defines and
    only uses; and the segment concepts the registry does not map."""
    seg_map = json.loads((s2a.maps_dir(course) / f"{lec.stem_of(key)}.json").read_text())
    names = {cid: c["name"] for cid, c in reg["concepts"].items()}
    unmapped, segs = [], []
    for sid, seg in seg_map.items():
        defines, uses = {}, {}
        for scid, sc in cmaps.items():
            if s4a.segment_of(scid) != sid:
                continue
            cid = reg["segment_concepts"].get(scid)
            if cid is None:
                unmapped.append(scid)
            name = names.get(cid, sc["name"])
            (defines if sc["defined"] else uses)[name] = True
        segs.append({"id": sid, "subgoal": seg["subgoal"], "defines": list(defines),
                     "uses": [n for n in uses if n not in defines]})
    return segs, unmapped


def segment_lines(segs: list[dict]) -> str:
    return "\n".join(f"[{i}] Sub-goal: {s['subgoal']}\n    Defines: {', '.join(s['defines']) or 'none'}\n"
                     f"    Uses: {', '.join(s['uses']) or 'none'}" for i, s in enumerate(segs, 1))


def lecture_prompt(course: str, key: str, segs: list[dict]) -> str:
    return s4a.fill(LECTURE.read_text(), course=course_meta.course_prompt(course),
                    lecture_title=course_meta.lecture_title(course, key), segments=segment_lines(segs))


def lecture_schema(n: int) -> dict:
    goal = {"goal": {"type": "string"}, "achieves": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": ["objectives", "goal", "achieves"],
            "properties": {"objectives": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["segments", "goal", "achieves"],
                "properties": {"segments": {"type": "array", "minItems": 1,
                                            "items": {"type": "integer", "minimum": 1, "maximum": n}}, **goal}}},
                **goal}}


def check_lecture(answer: dict, segs: list[dict], key: str) -> tuple[dict, dict]:
    """The lecture's goal records (IDs, segment numbers mapped to IDs) and the flags of the code checks."""
    n = len(segs)
    flags: dict = {}
    seen: dict[int, int] = {}
    recs, firsts = {}, []
    oids = []
    for k, o in enumerate(answer["objectives"], 1):
        bad = [i for i in o["segments"] if not 1 <= i <= n]
        if bad:
            flags.setdefault("out_of_range", []).append({"objective": objective_id(key, k), "segments": bad})
        nums = sorted(dict.fromkeys(i for i in o["segments"] if 1 <= i <= n))
        for i in nums:
            if i in seen:
                flags.setdefault("segment_twice", []).append(segs[i - 1]["id"])
            seen.setdefault(i, k)
        if nums and nums != list(range(nums[0], nums[-1] + 1)):
            flags.setdefault("not_consecutive", []).append(objective_id(key, k))
        if nums:
            firsts.append(nums[0])
        oid = objective_id(key, k)
        oids.append(oid)
        recs[oid] = {"goal": o["goal"].strip(), "achieves": o["achieves"].strip(),
                     "segments": [segs[i - 1]["id"] for i in nums]}
    if firsts != sorted(firsts):
        flags["out_of_order"] = True
    left = [{"segment": s["id"], "subgoal": s["subgoal"]} for i, s in enumerate(segs, 1) if i not in seen]
    if left:
        flags["in_no_objective"] = left
    out = {goal_id(key): {"goal": answer["goal"].strip(), "achieves": answer["achieves"].strip(), "objectives": oids}}
    out.update(recs)
    return out, flags


# ---------------------------------------------------------------- course call
def lecture_block(course: str, key: str, goals: dict | None) -> str:
    head = f"{s4a.lecture_label(key).capitalize()}: {course_meta.lecture_title(course, key)}"
    if not goals:
        return head + "\nGoal: (none: the lecture call gave no answer)"
    g = goals[goal_id(key)]
    objs = "\n".join(f"- {goals[o]['goal']}" for o in g["objectives"])
    return f"{head}\nGoal: {g['goal']}\nObjectives:\n{objs}"


def course_prompt(course: str, keys: list[str], goals: dict) -> str:
    return s4a.fill(COURSE.read_text(), course=course_meta.course_prompt(course),
                    lectures="\n\n".join(lecture_block(course, k, goals.get(k)) for k in keys))


def course_schema(keys: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["reasoning", "goals"],
            "properties": {"reasoning": {"type": "string"}, "goals": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["lectures", "goal", "achieves"],
                "properties": {"lectures": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": keys}},
                               "goal": {"type": "string"}, "achieves": {"type": "string"}}}}}}


def check_course(answer: dict, keys: list[str]) -> tuple[dict, dict]:
    flags: dict = {}
    goals = {}
    for k, g in enumerate(answer["goals"], 1):
        ls = list(dict.fromkeys(x for x in g["lectures"] if x in keys))
        if ls != sorted(ls, key=lec.order):
            flags.setdefault("not_in_course_order", []).append(f"G{k}")
        goals[f"G{k}"] = {"goal": g["goal"].strip(), "achieves": g["achieves"].strip(), "lectures": ls}
    served = {x for g in goals.values() for x in g["lectures"]}
    left = [k for k in keys if k not in served]
    if left:
        flags["lecture_in_no_goal"] = left
    return {"lectures": keys, "reasoning": answer["reasoning"].strip(), "goals": goals}, flags


# ---------------------------------------------------------------- run
def run(course: str, llm: LLM, lectures: list | None = None, seed: int | None = None,
        out: Path | None = None) -> dict:
    keys = lec.normalize(lectures) or lec.keys(s4a.stage_dir(course, "stage_2c_concepts") / "concept_maps")
    od = Path(out) if out else out_dir(course)
    for sub in ("lecture_goals", "llm"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    cache, log = od / "llm" / "cache.jsonl", od / "llm" / "calls.jsonl"
    sampling = {} if seed is None else {"seed": seed}
    t0 = time.time()
    reg = s4a.load_registry(course)
    cmaps = s4a.load_concept_maps(course, keys)
    segs, unmapped = {}, {}
    for k in keys:
        segs[k], um = load_segments(course, k, cmaps, reg)
        if um:
            unmapped[k] = um
    reqs = [Request(prompt=lecture_prompt(course, k, segs[k]), key=f"lecture {k}", schema=lecture_schema(len(segs[k])),
                    sampling=sampling, meta={"lecture": k}) for k in keys]
    print(f"4b: goals of {len(keys)} lectures with {llm.model}", flush=True)
    goals, checks = {}, {"lectures": {}, "course": {}}
    totals = {"lectures": len(keys), "objectives": 0, "course_goals": 0, "no_answer": [], "unmapped": unmapped,
              "flags": {}}
    for k, res in zip(keys, llm.generate_many(reqs, cache_file=cache, log_file=log)):
        if not res.ok:
            totals["no_answer"].append(f"lecture {k}")
            checks["lectures"][k] = {"errors": res.errors}
            continue
        goals[k], flags = check_lecture(res.parsed, segs[k], k)
        totals["objectives"] += len(goals[k][goal_id(k)]["objectives"])
        if flags:
            checks["lectures"][k] = flags
        for kind in flags:
            totals["flags"][kind] = totals["flags"].get(kind, 0) + 1
    print("4b: the course goals", flush=True)
    res = llm.generate_many([Request(prompt=course_prompt(course, keys, goals), key="course", schema=course_schema(keys),
                                     sampling=sampling)], cache_file=cache, log_file=log)[0]
    if res.ok:
        cgoals, flags = check_course(res.parsed, keys)
        checks["course"] = flags
        for kind in flags:
            totals["flags"][kind] = totals["flags"].get(kind, 0) + 1
    else:
        cgoals = {"lectures": keys, "reasoning": "", "goals": {}}
        checks["course"] = {"errors": res.errors}
        totals["no_answer"].append("course")
    totals["course_goals"] = len(cgoals["goals"])
    for k in keys:
        (od / "lecture_goals" / f"{lec.stem_of(k)}.json").write_text(
            json.dumps(goals.get(k, {}), indent=1, ensure_ascii=False) + "\n")
    (od / "course_goals.json").write_text(json.dumps(cgoals, indent=1, ensure_ascii=False) + "\n")
    (od / "checks.json").write_text(json.dumps({"totals": totals, **checks}, indent=1, ensure_ascii=False) + "\n")
    (od / "goals.txt").write_text(goals_text(course, keys, goals, cgoals, segs, checks))
    print(f"{len(keys)} lectures, {totals['objectives']} objectives, {totals['course_goals']} course goals, "
          f"{round(time.time() - t0, 1)} s" + (f"; no answer: {totals['no_answer']}" if totals["no_answer"] else ""))
    print(f"checks: {totals['flags'] or 'none'}")
    return totals


def goals_text(course: str, keys: list[str], goals: dict, cgoals: dict, segs: dict, checks: dict) -> str:
    out = ["COURSE GOALS"]
    for gid, g in cgoals["goals"].items():
        out += [f"{gid}  {g['goal']}", f"     achieves: {g['achieves']}", f"     lectures: {', '.join(g['lectures'])}"]
    if checks["course"]:
        out.append("checks: " + "; ".join(checks["course"]))
    for k in keys:
        out += ["", f"LECTURE {k}: {course_meta.lecture_title(course, k)}"]
        if k not in goals:
            out.append("  (no answer)")
            continue
        g = goals[k][goal_id(k)]
        out += [f"{goal_id(k)}  {g['goal']}", f"     achieves: {g['achieves']}"]
        sub = {s["id"]: s["subgoal"] for s in segs[k]}
        for oid in g["objectives"]:
            o = goals[k][oid]
            out += [f"  {oid}  {o['goal']}", f"        achieves: {o['achieves']}"]
            out += [f"        {sid}  {sub[sid]}" for sid in o["segments"]]
        if checks["lectures"].get(k):
            out.append("  checks: " + "; ".join(checks["lectures"][k]))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--only", help="lectures, e.g. 1,4,16 (the course goals are then built from these)")
    ap.add_argument("--seed", type=int, help="sampling seed (default: the config's); for repeat runs")
    ap.add_argument("--out", help="output folder (default: output/<course>/stage_4b_goals); for repeat runs")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, lec.parse_only(a.only) if a.only else None, a.seed, Path(a.out) if a.out else None)


if __name__ == "__main__":
    main()
