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
                                      ({} for a lecture whose call gave no answer)
          course_goals.json           {"lectures": [keys], "reasoning", "goals": {"G1": {"goal", "achieves",
                                       "lectures": [keys]}, ...}}
          goals.txt                   the course goals, then per lecture its goal, objectives and their segments
          checks.json                 totals, the code checks per lecture and for the course (below), and per
                                      retried answer what the retry changed
          llm/cache.jsonl, calls.jsonl

1. One call per lecture (the lectures with 2c concept maps, or --only). Its segments are numbered [1]..[n] in
   lecture order, each with its sub-goal, the concepts it defines and the concepts it only uses (registry names; a
   concept is "defined" in a segment when one of its segment concepts there has defined=true). Segments without
   concepts are listed too ("none"). The answer's segment numbers are mapped back to segment IDs in code.
   IDs: objectives "<lecture>/O1", "<lecture>/O2", ... in the model's order (from 1, like the course goals); the
   lecture goal "<lecture>/G".
2. One call for the course: every lecture of the run as
       [4] Lecture 4: <title>            ("[tut_1] Tutorial 1: <title>" for a tutorial)
       Goal: <the lecture goal>
       Achieves: <what the lecture goal achieves>
       Objectives:
       - <objective goal>
   (a lecture whose call gave no answer: "Goal: (none: the lecture call gave no answer)"). The answer's lectures are
   limited by the schema to the lecture keys ("4", "24b", "tut_1"). Course goal IDs "G1", "G2", ... in the model's
   order.

Code checks (decision D12). An answer with a problem below is retried with the problems shown to the model (LLM API,
feedback; the config's retries); one that still fails keeps its best attempt (fewest problems, ties: the latest),
flagged "unresolved" with its remaining problems; only an answer that never parses is "no answer".
  lecture, retried: out_of_range (a segment number outside 1..n; dropped), segment_twice (a segment in two
           objectives), out_of_order (objectives not in lecture order), empty_goal (an empty goal or achieves, of an
           objective or the lecture), not_consecutive (an objective whose segments are not one run, ignoring the
           segments in no objective: [1, 3] with segment 2 in none is one run)
  lecture, reported: in_no_objective (a segment in no objective, with its sub-goal and the concepts it defines:
           allowed for a recap, an outline or a closing summary; one that defines concepts is worth a look)
  course, retried: lecture_in_no_goal (a lecture that serves no course goal; a lecture whose own call gave no answer
           is not counted)
  course, fixed in code: a goal's lectures put in course order and repeats dropped (reported: reordered,
           repeats_removed)
  course, reported: goal_over_half (a goal that lists more than half the lectures)
Per retried answer, checks.json "retries" holds the items lost and added between the first and the final attempt
(lecture: "objective [4/S0, 4/S1]: <goal>", "... achieves: <text>", "lecture goal: <text>", "lecture achieves:
<text>"; course: "[1, 4] <goal>", "[1, 4] achieves: <text>"); totals count the retried answers, those the retry
changed, and the items lost and added.
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
RETRY_LECTURE = ("out_of_range", "segment_twice", "out_of_order", "empty_goal", "not_consecutive")


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


def _text(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def _objectives(answer) -> list[dict]:
    objs = answer.get("objectives") if isinstance(answer, dict) else None
    return [o for o in objs if isinstance(o, dict)] if isinstance(objs, list) else []


def check_lecture(answer: dict, segs: list[dict], key: str) -> tuple[dict, dict, list[str]]:
    """The lecture's goal records (IDs, segment numbers mapped to IDs), the flags of the code checks, and the
    problems that send the answer back (the RETRY_LECTURE kinds, as messages in the prompt's numbering)."""
    n = len(segs)
    flags: dict = {}
    problems: list[str] = []
    objs = _objectives(answer)
    nums_of = []
    for o in objs:
        raw = [i for i in o.get("segments", []) if isinstance(i, int)]
        nums_of.append(sorted(dict.fromkeys(i for i in raw if 1 <= i <= n)))
    placed = {i for nums in nums_of for i in nums}
    owner: dict[int, list[int]] = {}
    recs, firsts, oids = {}, [], []
    for k, (o, nums) in enumerate(zip(objs, nums_of), 1):
        oid = objective_id(key, k)
        oids.append(oid)
        bad = [i for i in o.get("segments", []) if not (isinstance(i, int) and 1 <= i <= n)]
        if bad:
            flags.setdefault("out_of_range", []).append({"objective": oid, "segments": bad})
            problems.append(f"Objective {k} lists segment numbers that do not exist: {bad}. The segments are "
                            f"numbered 1 to {n}.")
        for i in nums:
            owner.setdefault(i, []).append(k)
        gaps = [i for i in range(nums[0], nums[-1] + 1) if i not in nums and i in placed] if nums else []
        if gaps:
            flags.setdefault("not_consecutive", []).append(oid)
            problems.append(f"Objective {k} covers segments {nums}, but segment{'s' if len(gaps) > 1 else ''} "
                            f"{', '.join(map(str, gaps))} between them belong{'' if len(gaps) > 1 else 's'} to "
                            f"another objective. An objective covers one run of consecutive segments.")
        if nums:
            firsts.append(nums[0])
        for field in ("goal", "achieves"):
            if not _text(o.get(field)):
                flags.setdefault("empty_goal", []).append(f"{oid} {field}")
                problems.append(f'Objective {k} has an empty "{field}". Write it.')
        recs[oid] = {"goal": _text(o.get("goal")), "achieves": _text(o.get("achieves")),
                     "segments": [segs[i - 1]["id"] for i in nums]}
    for i, ks in sorted(owner.items()):
        if len(ks) > 1:
            flags.setdefault("segment_twice", []).append(segs[i - 1]["id"])
            problems.append(f"Segment {i} is in more than one objective (objectives {', '.join(map(str, ks))}). "
                            f"Every segment belongs to exactly one objective.")
    if firsts != sorted(firsts):
        flags["out_of_order"] = True
        problems.append("The objectives are not in lecture order. List them in the order of their first segments.")
    for field in ("goal", "achieves"):
        if not _text(answer.get(field)):
            flags.setdefault("empty_goal", []).append(f"{goal_id(key)} {field}")
            problems.append(f'The lecture "{field}" is empty. Write it.')
    left = [{"segment": s["id"], "subgoal": s["subgoal"], "defines": s.get("defines", [])}
            for i, s in enumerate(segs, 1) if i not in placed]
    if left:
        flags["in_no_objective"] = left
    out = {goal_id(key): {"goal": _text(answer.get("goal")), "achieves": _text(answer.get("achieves")),
                          "objectives": oids}}
    out.update(recs)
    return out, flags, problems


def lecture_items(answer: dict, segs: list[dict]) -> list[str]:
    """A lecture answer as readable items for the retry log."""
    n, out = len(segs), []
    for o in _objectives(answer):
        ids = ", ".join(segs[i - 1]["id"] for i in sorted(dict.fromkeys(
            i for i in o.get("segments", []) if isinstance(i, int) and 1 <= i <= n)))
        out += [f"objective [{ids}]: {_text(o.get('goal'))}", f"objective [{ids}] achieves: {_text(o.get('achieves'))}"]
    return out + [f"lecture goal: {_text(answer.get('goal'))}", f"lecture achieves: {_text(answer.get('achieves'))}"]


# ---------------------------------------------------------------- course call
def lecture_block(course: str, key: str, goals: dict | None) -> str:
    head = f"[{key}] {s4a.lecture_label(key).capitalize()}: {course_meta.lecture_title(course, key)}"
    if not goals:
        return head + "\nGoal: (none: the lecture call gave no answer)"
    g = goals[goal_id(key)]
    objs = "\n".join(f"- {goals[o]['goal']}" for o in g["objectives"])
    return f"{head}\nGoal: {g['goal']}\nAchieves: {g['achieves']}\nObjectives:\n{objs}"


def course_prompt(course: str, keys: list[str], goals: dict) -> str:
    return s4a.fill(COURSE.read_text(), course=course_meta.course_prompt(course),
                    lectures="\n\n".join(lecture_block(course, k, goals.get(k)) for k in keys))


def course_schema(keys: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["reasoning", "goals"],
            "properties": {"reasoning": {"type": "string"}, "goals": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["lectures", "goal", "achieves"],
                "properties": {"lectures": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": keys}},
                               "goal": {"type": "string"}, "achieves": {"type": "string"}}}}}}


def _goals(answer) -> list[dict]:
    gs = answer.get("goals") if isinstance(answer, dict) else None
    return [g for g in gs if isinstance(g, dict)] if isinstance(gs, list) else []


def check_course(answer: dict, keys: list[str], no_answer: list[str] = ()) -> tuple[dict, dict, list[str]]:
    """The course goals (each goal's lectures put in course order, repeats dropped), the flags, and the problems that
    send the answer back: lectures in no goal, except those whose own call gave no answer (no_answer)."""
    flags: dict = {}
    goals = {}
    for k, g in enumerate(_goals(answer), 1):
        raw = [x for x in g.get("lectures", []) if x in keys]
        ls = sorted(dict.fromkeys(raw), key=lec.order)
        if len(ls) < len(raw):
            flags.setdefault("repeats_removed", []).append(f"G{k}")
        if list(dict.fromkeys(raw)) != ls:
            flags.setdefault("reordered", []).append(f"G{k}")
        if len(ls) > len(keys) / 2:
            flags.setdefault("goal_over_half", []).append({"goal": f"G{k}", "lectures": len(ls), "of": len(keys)})
        goals[f"G{k}"] = {"goal": _text(g.get("goal")), "achieves": _text(g.get("achieves")), "lectures": ls}
    served = {x for g in goals.values() for x in g["lectures"]}
    left = [k for k in keys if k not in served and k not in no_answer]
    problems = []
    if left:
        flags["lecture_in_no_goal"] = left
        problems.append(f"The lecture{'s' if len(left) > 1 else ''} {', '.join(f'[{k}]' for k in left)} "
                        f"serve{'' if len(left) > 1 else 's'} no course goal. Every lecture serves at least one "
                        f"course goal: add each to the goals its objectives work toward.")
    return ({"lectures": keys, "reasoning": _text(answer.get("reasoning") if isinstance(answer, dict) else ""),
             "goals": goals}, flags, problems)


def course_items(answer: dict, keys: list[str]) -> list[str]:
    """A course answer as readable items for the retry log."""
    out = []
    for g in _goals(answer):
        ls = ", ".join(sorted(dict.fromkeys(x for x in g.get("lectures", []) if x in keys), key=lec.order))
        out += [f"[{ls}] {_text(g.get('goal'))}", f"[{ls}] achieves: {_text(g.get('achieves'))}"]
    return out


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
                    check=lambda a, s=segs[k], k=k: check_lecture(a, s, k)[2], feedback=True,
                    sampling=sampling, meta={"lecture": k}) for k in keys]
    print(f"4b: goals of {len(keys)} lectures with {llm.model}", flush=True)
    goals, checks, retries = {}, {"lectures": {}, "course": {}}, {"lectures": {}, "course": None}
    totals = {"lectures": len(keys), "objectives": 0, "course_goals": 0, "no_answer": [], "unresolved": [],
              "unmapped": unmapped, "flags": {}, "in_no_objective_defining": 0,
              "retried": 0, "changed_by_retry": 0, "lost": 0, "added": 0}

    def count(flags: dict):
        for kind in flags:
            totals["flags"][kind] = totals["flags"].get(kind, 0) + 1

    for k, res in zip(keys, llm.generate_many(reqs, cache_file=cache, log_file=log)):
        rlog = s4a.retry_log(res, lambda a, s=segs[k]: lecture_items(a, s))
        s4a.count_retries(totals, rlog)
        if rlog is not None:
            retries["lectures"][k] = rlog
        if not s4a.answered(res):
            totals["no_answer"].append(f"lecture {k}")
            checks["lectures"][k] = {"errors": res.errors}
            continue
        goals[k], flags, problems = check_lecture(res.parsed, segs[k], k)
        if not res.ok:
            flags["unresolved"] = problems or res.errors
            totals["unresolved"].append(f"lecture {k}")
        totals["objectives"] += len(goals[k][goal_id(k)]["objectives"])
        totals["in_no_objective_defining"] += sum(bool(x["defines"]) for x in flags.get("in_no_objective", []))
        if flags:
            checks["lectures"][k] = flags
        count(flags)
    print("4b: the course goals", flush=True)
    no_answer = [k for k in keys if k not in goals]
    res = llm.generate_many([Request(prompt=course_prompt(course, keys, goals), key="course", schema=course_schema(keys),
                                     check=lambda a: check_course(a, keys, no_answer)[2], feedback=True,
                                     sampling=sampling)], cache_file=cache, log_file=log)[0]
    rlog = s4a.retry_log(res, lambda a: course_items(a, keys))
    s4a.count_retries(totals, rlog)
    retries["course"] = rlog
    if s4a.answered(res):
        cgoals, flags, problems = check_course(res.parsed, keys, no_answer)
        if not res.ok:
            flags["unresolved"] = problems or res.errors
            totals["unresolved"].append("course")
        if no_answer:
            flags["not_counted"] = no_answer          # lectures without an answer: not checked for a course goal
        checks["course"] = flags
        count(flags)
    else:
        cgoals = {"lectures": keys, "reasoning": "", "goals": {}}
        checks["course"] = {"errors": res.errors}
        totals["no_answer"].append("course")
    totals["course_goals"] = len(cgoals["goals"])
    for k in keys:
        (od / "lecture_goals" / f"{lec.stem_of(k)}.json").write_text(
            json.dumps(goals.get(k, {}), indent=1, ensure_ascii=False) + "\n")
    (od / "course_goals.json").write_text(json.dumps(cgoals, indent=1, ensure_ascii=False) + "\n")
    retries["lectures"] = dict(sorted(retries["lectures"].items(), key=lambda kv: lec.order(kv[0])))
    (od / "checks.json").write_text(json.dumps({"totals": totals, **checks, "retries": retries}, indent=1,
                                               ensure_ascii=False) + "\n")
    (od / "goals.txt").write_text(goals_text(course, keys, goals, cgoals, segs, checks, retries))
    print(f"{len(keys)} lectures, {totals['objectives']} objectives, {totals['course_goals']} course goals, "
          f"{round(time.time() - t0, 1)} s; {totals['retried']} retried ({totals['changed_by_retry']} changed)"
          + (f"; unresolved (best answer kept): {totals['unresolved']}" if totals["unresolved"] else "")
          + (f"; no answer: {totals['no_answer']}" if totals["no_answer"] else ""))
    print(f"checks: {totals['flags'] or 'none'}")
    return totals


def _retry_line(rlog: dict | None, indent: str) -> list[str]:
    if not rlog:
        return []
    return [f"{indent}retried ({rlog['attempts']} attempts): lost {' | '.join(rlog['lost']) or 'nothing'}; "
            f"added {' | '.join(rlog['added']) or 'nothing'}"]


def goals_text(course: str, keys: list[str], goals: dict, cgoals: dict, segs: dict, checks: dict,
               retries: dict) -> str:
    out = ["COURSE GOALS"]
    for gid, g in cgoals["goals"].items():
        out += [f"{gid}  {g['goal']}", f"     achieves: {g['achieves']}", f"     lectures: {', '.join(g['lectures'])}"]
    if checks["course"]:
        out.append("checks: " + "; ".join(checks["course"]))
    if checks["course"].get("unresolved"):
        out.append("UNRESOLVED (best answer kept): " + " | ".join(checks["course"]["unresolved"]))
    out += _retry_line(retries["course"], "")
    for k in keys:
        out += ["", f"LECTURE {k}: {course_meta.lecture_title(course, k)}"]
        out += _retry_line(retries["lectures"].get(k), "  ")
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
        fl = checks["lectures"].get(k, {})
        for x in fl.get("in_no_objective", []):
            out.append(f"  in no objective: {x['segment']}  {x['subgoal']}"
                       + (f"  (defines {', '.join(x['defines'])})" if x["defines"] else ""))
        if fl:
            out.append("  checks: " + "; ".join(fl))
        if fl.get("unresolved"):
            out.append("  UNRESOLVED (best answer kept): " + " | ".join(fl["unresolved"]))
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
