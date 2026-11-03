"""Write LIR v2.1 (knowledge layer and activities) to lir-v2/<course>/ and validate it against lir2_schema.py."""
from __future__ import annotations

import json
import shutil

from lir2_schema import Course, Lecture, LectureActivities
from pipeline.embed import EMBED_MODEL

from .context import Run


def _lecture(R: Run, lec) -> dict:
    s = lec.s
    parts = []
    for p in lec.parts:
        parts.append({
            "id": p.id, "first": s(p.a), "last": s(p.b), "start": p.start, "end": p.end,
            "objective": p.objective, "objective_id": p.objective_id,
            "key_points": [{"id": k["id"], "text": k["text"], "sources": [s(i) for i in k["sentences"]],
                            "concept_ids": R.matcher.find(k["text"], lec.pos) if getattr(R, "matcher", None) else []}
                           for k in p.key_points],
            "terms": [{"id": t["id"], "surface": t["surface"], "name": t["name"], "abbreviation": t["abbreviation"],
                       "abbreviation_at": t["abbreviation_at"], "definition": t["definition"],
                       "sources": [s(i) for i in t["sentences"]], "concept_id": t["concept_id"],
                       "concept_name": t["concept_name"]}
                      for t in p.terms if t["concept_id"]]})
    inp = lec.inp
    return {"course_id": R.course.course_id, "lecture_id": lec.id, "index": inp.index, "title": inp.title,
            "source_file": str(inp.srt.name if inp.srt else inp.txt.name), "timing_source": inp.timing_source,
            "youtube_id": inp.youtube_id or None, "duration_s": inp.duration,
            "sentences": [{"id": s(x.id), "start": x.start, "end": x.end, "text": x.text} for x in lec.sentences],
            "parts": parts, "objectives": lec.objectives, "lecture_goal": lec.lecture_goal, "flags": lec.flags,
            "origin": lec.origin}


def _course(R: Run) -> dict:
    C = R.registry.concepts
    index: dict[str, list[str]] = {}
    for c in C.values():
        for n in [c.name] + [a["text"] for a in c.aliases]:
            ids = index.setdefault(n.lower(), [])
            if c.id not in ids:
                ids.append(c.id)
    return {"course_id": R.course.course_id, "title": R.course.title, "source": R.course.source,
            "lectures": [{"id": l.id, "index": l.inp.index, "title": l.inp.title, "duration_s": l.inp.duration,
                          "youtube_id": l.inp.youtube_id or None} for l in R.lectures],
            "course_goals": R.course_goals,
            "concepts": [{"id": c.id, "name": c.name, "aliases": c.aliases, "introduced": c.introduced,
                          "introduced_part": c.introduced_part, "terms": c.terms, "definition": c.definition,
                          "reason": c.reason, "sources": c.sources,
                          "facets": [{k: v for k, v in f.items() if k not in ("draft", "_cid")}
                                     for f in sorted(c.facets, key=lambda f: (R.pos(f["part"].split("/")[0]), f["part"]))]}
                         for c in C.values()],
            "edges": R.edges, "lecture_map": R.lecture_map, "alias_index": dict(sorted(index.items())),
            "embedding_model": EMBED_MODEL, "origin": R.course_origin}


def _public(x):
    """Drop the working fields (keys starting with "_")."""
    if isinstance(x, dict):
        return {k: _public(v) for k, v in x.items() if not k.startswith("_")}
    if isinstance(x, list):
        return [_public(v) for v in x]
    return x


def _activities(R: Run, lec) -> dict:
    a = R.acts[lec.id]
    seq = [{"type": "recall"}] if a["recall"] else []
    for p in lec.parts:
        seq += [{"type": "watch", "part_id": p.id}]
        pa = a["parts"][p.id]
        if pa["quiz"] or any(x["default"] for x in pa["spaced_review"]):   # spaced review follows the part's quiz
            seq.append({"type": "quiz", "part_id": p.id})
        if pa["recap"] or pa["review"]:
            seq.append({"type": "summary", "part_id": p.id})
    seq += [{"type": "concept_map"}] + ([{"type": "open_questions"}] if a["open_questions"] else [])
    return _public({"course_id": R.course.course_id, "lecture_id": lec.id, "sequence": seq, "recall": a["recall"],
                    "parts": [{"part_id": pid, **pa} for pid, pa in a["parts"].items()],
                    "concept_map": a["concept_map"], "open_questions": a["open_questions"], "scoring": R.scoring})


def run(R: Run, lir_dir):
    tmp = lir_dir.with_name(lir_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    for lec in R.lectures:
        d = Lecture.model_validate(_lecture(R, lec)).model_dump()
        (tmp / f"{lec.id}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    course = Course.model_validate(_course(R)).model_dump()
    (tmp / "course.json").write_text(json.dumps(course, ensure_ascii=False, indent=1), encoding="utf-8")
    embs = {c.id: [round(float(x), 5) for x in c.emb] for c in R.registry.concepts.values() if c.emb is not None}
    (tmp / "embeddings.json").write_text(json.dumps({"model": EMBED_MODEL, "concepts": embs}), encoding="utf-8")
    if R.acts:
        (tmp / "activities").mkdir()
        for lec in R.lectures:
            d = LectureActivities.model_validate(_activities(R, lec)).model_dump()
            (tmp / "activities" / f"{lec.id}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                                                encoding="utf-8")
    R.decisions.write(tmp / "decisions.jsonl")
    if lir_dir.exists():
        shutil.rmtree(lir_dir)
    tmp.rename(lir_dir)
    R.log(f"  wrote {len(R.lectures)} lectures, {len(course['concepts'])} concepts, {len(course['edges'])} edges, "
          f"{len(R.decisions.items)} decisions → {lir_dir}")
