"""Stage 7: assemble the LIR files (no LLM calls), run the cross-cutting checks, validate against lir_schema."""
from __future__ import annotations

import json
import re
from pathlib import Path

import scorer
from lir_schema import Course, Lecture

from . import calibrate
from .context import Run
from .embed import EMBED_MODEL, embed

HERE = Path(__file__).resolve().parent.parent

CONCEPT_KEYS = {"concept_id", "to_concept_id", "for_new_concept_id", "src", "dst"}


def _concept_refs(obj, out: set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in CONCEPT_KEYS and isinstance(v, str) and v.startswith("C"):
                out.add(v)
            elif k == "concept_ids" and isinstance(v, list):
                out.update(v)
            else:
                _concept_refs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _concept_refs(v, out)
    return out


# LaTeX in generated text loses backslashes when the model writes \t, \f, \b, \n, \r or \v inside a JSON string:
# "\theta" arrives as a tab + "heta", "\frac" as a form feed + "rac". Put the backslash back inside $...$ math, and in
# short bare expressions such as an answer option "n \times 1". Real line breaks in ordinary text are left alone.
_CTRL = {"\t": "\\t", "\b": "\\b", "\f": "\\f", "\r": "\\r", "\n": "\\n", "\v": "\\v"}
_MATH = re.compile(r"\$[^$]{1,300}?\$")
_CTRL_RE = re.compile(r"[\t\b\f\r\n\v]")


def _fix_tex(s: str) -> str:
    s = _MATH.sub(lambda m: _CTRL_RE.sub(lambda c: _CTRL[c.group()], m.group()), s)
    if "$" not in s and len(s) <= 60 and re.search(r"[\t\b\f\v][a-z]", s):
        s = re.sub(r"[\t\b\f\v]", lambda c: _CTRL[c.group()], s)
    return s


def fix_math(obj, stats: list | None = None):
    """Return obj with the LaTeX backslashes repaired in every string (transcript sentences are left as they are)."""
    if isinstance(obj, dict):
        return {k: (v if k == "sentences" else fix_math(v, stats)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_math(v, stats) for v in obj]
    if isinstance(obj, str):
        new = _fix_tex(obj)
        if new != obj and stats is not None:
            stats.append(1)
        return new
    return obj


def _leak_errors(R: Run, lec_json: dict, pos: int) -> list[str]:
    errs = []
    st = R.state
    late = sorted(c for c in _concept_refs(lec_json, set()) if c in st.concepts and st.concepts[c].intro_pos > pos)
    if late:
        errs.append(f"uses concepts introduced after this lecture: {late}")
    primer = lec_json["phases"][0]
    for r in primer["recall"]:
        if st.pos_of[r["jump_to"]["lecture_id"]] >= pos:
            errs.append(f"recall item {r['concept_id']} points to lecture {r['jump_to']['lecture_id']}, not an earlier one")
    n = len(lec_json["sentences"])
    for ph in lec_json["phases"]:
        for src in _sources(ph):
            if not 0 <= src < n:
                errs.append(f"phase {ph['type']} cites sentence {src}, which does not exist")
    return errs


def _sources(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "sources" and isinstance(v, list):
                yield from v
            else:
                yield from _sources(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _sources(v)


def run(R: Run, video_dir: Path | None = None):
    out = R.lir_dir
    out.mkdir(parents=True, exist_ok=True)
    cal = calibrate.fit(R)
    R.log(f"  scorer calibration: m={cal['m']}, tau={cal['tau']}"
          + (f", agreement {cal['agreement']:.0%} on {cal['answers']} answers" if cal.get("calibrated") else
             f" ({cal.get('note', 'defaults')})"), "ok")
    scoring = {"embedding_model": EMBED_MODEL,
               "open_answer": {**cal, "tiers": [{"min": lo, "id": tid, "label": label} for lo, tid, label in scorer.TIERS]},
               "concept_map": {"node_match_tau": 0.75, "label_bonus_tau": 0.6, "label_bonus": 0.25}}
    # key-point embeddings for the runtime scorer, computed once for the whole course
    kps = [kp for lec in R.lectures for ph in lec.phases if ph["type"] == "constructive"
           for q in ph["open_questions"] for kp in q["key_points"]]
    for kp, e in zip(kps, embed([kp["text"] for kp in kps])):
        kp["embedding"] = [round(float(x), 5) for x in e]

    fixed: list = []
    for pos, lec in enumerate(R.lectures, 1):
        segs = [{"id": s.id, "sentence_range": [s.a, s.b], "start": s.start, "end": s.end, "subgoal": s.subgoal,
                 "content_type": s.content_type, "objective_id": s.objective_id, "key_points": s.key_points,
                 "key_terms": [{"concept_id": t.get("concept_id", ""), "term": t["term"], "definition": t["definition"],
                                "sentence_ids": t["sentence_ids"]} for t in s.key_terms],
                 "concept_ids": s.concept_ids, "flags": s.flags} for s in lec.segments]
        try:
            src = str(lec.inp.srt.relative_to(R.course.root))
        except ValueError:
            src = str(lec.inp.srt)
        video = None
        if video_dir is not None and ((video_dir / f"{lec.id}.mp4").exists() or getattr(R, "videos_expected", False)):
            video = str((video_dir / f"{lec.id}.mp4").relative_to(HERE))
        doc = {"course_id": R.course.course_id, "lecture_id": lec.id, "index": lec.inp.index, "title": lec.inp.title,
               "source_file": src, "timing_source": lec.inp.timing_source, "youtube_id": lec.inp.youtube_id or None,
               "video": video, "duration_s": round(lec.inp.duration, 2),
               "sentences": [vars(s) for s in lec.sentences],
               "roadmap": {"lecture_goal": lec.lecture_goal, "objectives": lec.objectives},
               "segments": segs, "phases": lec.phases, "scoring": scoring, "flags": lec.flags,
               "quality": lec.quality, "origin": lec.origin}
        for e in _leak_errors(R, doc, pos):
            R.flag(lec.id, f"leakage check: {e}")
        doc["flags"] = lec.flags
        doc = fix_math(doc, fixed)
        model = Lecture.model_validate(doc)  # schema check of the whole file
        (out / f"{lec.id}.json").write_text(model.model_dump_json(indent=1), encoding="utf-8")

    final = R.state.snapshot(len(R.lectures))
    course = {"course_id": R.course.course_id, "title": R.course.title, "source": R.course.source,
              "lecture_ids": [l.id for l in R.lectures], "course_goals": R.course_goals,
              "concepts": [{"id": c["id"], "name": c["name"], "aliases": c["aliases"], "definition": c["definition"],
                            "introduced": c["introduced"], "mentions": c["mentions"], "salience": c["salience"]}
                           for c in final["concepts"].values()],
              "edges": [{k: v for k, v in e.items() if k != "pos"} for e in final["edges"]],
              "embedding_model": EMBED_MODEL,
              "concept_embeddings": {cid: [round(float(x), 5) for x in c.emb] for cid, c in R.state.concepts.items()},
              "origin": R.course_origin}
    course = fix_math(course, fixed)
    (out / "course.json").write_text(Course.model_validate(course).model_dump_json(indent=1), encoding="utf-8")
    if fixed:
        R.log(f"  repaired LaTeX backslashes in {len(fixed)} strings", "ok")
    _write_index(out.parent)
    R.log(f"  wrote course.json and {len(R.lectures)} lecture files to {out}", "ok")


def _write_index(lir_root: Path):
    """lir/index.json lists every built course, for the viewer's home page."""
    courses = []
    for cj in sorted(lir_root.glob("*/course.json")):
        c = json.loads(cj.read_text(encoding="utf-8"))
        lectures = []
        for lid in c["lecture_ids"]:
            lj = cj.parent / f"{lid}.json"
            if lj.exists():
                d = json.loads(lj.read_text(encoding="utf-8"))
                lectures.append({"lecture_id": lid, "title": d["title"], "duration_s": d["duration_s"],
                                 "lecture_goal": d["roadmap"]["lecture_goal"], "video": d.get("video"),
                                 "segments": len(d["segments"])})
        courses.append({"course_id": c["course_id"], "title": c["title"], "source": c["source"],
                        "path": f"lir/{cj.parent.name}", "course_goals": c["course_goals"], "lectures": lectures})
    (lir_root / "index.json").write_text(json.dumps({"courses": courses}, indent=1, ensure_ascii=False), encoding="utf-8")
