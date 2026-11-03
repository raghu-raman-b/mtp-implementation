"""Open questions per lecture, from everything known about it: goal, objectives, each part's objective and key points
(with their sentences), key terms with the lecture's definitions, facets, and the links found in the lecture.

    write   one call: 2 to 6 questions (about one per 15 minutes of video), each of a type the content supports, with a
            reference answer and 3-5 key points (keywords word for word in the reference answer, cited sentences).
            Code checks the keywords and sentences; a key point that fails is dropped, a question left with fewer than
            MIN_KP key points is dropped
    judge   one call for the lecture's questions; failed ones are rewritten once and judged again, then dropped
"""
from __future__ import annotations

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids
from pipeline.s5_generate import _clean_keywords

from . import addr as A
from . import prompts as P
from .context import Lecture, Run
from .judge import Item, judge_unit, rewrite_items

MIN_Q, MAX_Q, MIN_PER_Q, MIN_KP = 2, 6, 15, 3     # about one question per 15 minutes of video


def bounds(lec: Lecture) -> tuple[int, int]:
    hi = max(MIN_Q, min(MAX_Q, round(lec.inp.duration / 60 / MIN_PER_Q)))
    return min(MIN_Q, hi), hi


def knowledge(R: Run, lec: Lecture) -> tuple[str, set[int]]:
    """The lecture's knowledge as text, and the sentence numbers shown."""
    C = R.registry.concepts
    shown: set[int] = set()
    lines = [f"Goal of the lecture: {lec.lecture_goal}", "Learning objectives (you'll be able to ...):"]
    lines += [f"- {o['text']}" for o in lec.objectives]
    lines.append("\nParts:")
    for p in lec.parts:
        lines.append(f"{p.id}: {p.objective}")
        if p.key_points:
            lines.append("  Key points:")
            for k in p.key_points:
                lines.append(f"   - {k['text']} (sentences {k['sentences']})")
                shown |= set(k["sentences"])
        if p.terms:
            lines.append("  Key terms:")
            for t in p.terms:
                lines.append(f"   - {t['concept_name'] or t['name']}: {t['definition']} (sentences {t['sentences']})")
                shown |= set(t["sentences"])
        taught = [f for f in p.facets if not f["only_mentioned"]]
        if taught:
            lines.append("  What it teaches about concepts:")
            for f in taught:
                ids = [A.parse_sent(s)[1] for s in f["sentences"]]
                lines.append(f"   - {C[f['_cid']].name}: {f['says']} (sentences {ids})")
                shown |= set(ids)
    if lec.links:
        lines.append("\nLinks between concepts in this lecture:")
        lines += [f'- "{C[e["src"]].name} {e["label"]} {C[e["dst"]].name}"' for e in lec.links]
    lines.append("\nThe sentences cited above, by number:")
    lines += [f"[{i}] {lec.sentences[i].text}" for i in sorted(shown)]
    text = (f"{P.ROLE}\n\nCourse: {R.course.title}\nLecture: {lec.inp.title}\n\nWhat the lecture teaches:\n"
            + "\n".join(lines) + "\n\n")
    return text, shown


KP_PROPS = {"text": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}},
            "sentence_ids": {"type": "array", "items": {"type": "integer"}}}


def _q_props(pids: list[str]) -> dict:
    return {"type": {"type": "string", "enum": list(P.OQ_TYPES)},
            "parts": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "enum": pids}},
            "question": {"type": "string"}, "reference_answer": {"type": "string"},
            "key_points": {"type": "array", "minItems": 3, "maxItems": 5, "items": {
                "type": "object", "additionalProperties": False, "required": list(KP_PROPS), "properties": KP_PROPS}}}


def _build(R: Run, lec: Lecture, x: dict, shown: set[int], key: str) -> tuple[dict | None, list[str]]:
    kps, errs = [], []
    for j, k in enumerate(x["key_points"], 1):
        kw = _clean_keywords(k["keywords"], x["reference_answer"])
        ids = sorted({i for i in k["sentence_ids"] if i in shown})
        if len(kw) < 2:
            errs.append(f"key point {j} needs at least 2 keywords that appear word for word in the reference answer")
            continue
        if not ids:
            errs.append(f"key point {j} cites no sentence shown above")
            continue
        kps.append({"text": strip_ids(k["text"]), "keywords": kw, "sources": [lec.s(i) for i in ids]})
    if len(kps) < MIN_KP:
        return None, errs or [f"fewer than {MIN_KP} key points"]
    pids = sorted(set(x["parts"]), key=lambda p: lec.part(p).n)
    return {"type": x["type"], "prompt": strip_ids(x["question"]), "reference_answer": strip_ids(x["reference_answer"]),
            "key_points": kps, "part_ids": pids, "concept_ids": [], "_key": key,
            "_raw": {k: x[k] for k in ("type", "parts", "question", "reference_answer", "key_points")}}, errs


def run_lecture(R: Run, lec: Lecture):
    lo, hi = bounds(lec)
    pids = [p.id for p in lec.parts]
    block, shown = knowledge(R, lec)
    types = "\n".join(f"  {k}: {v}" for k, v in P.OQ_TYPES.items())
    schema = {"type": "object", "additionalProperties": False, "required": ["questions"], "properties": {
        "questions": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
            "type": "object", "additionalProperties": False, "required": list(_q_props(pids)),
            "properties": _q_props(pids)}}}}
    o = R.send("oq", Call(key=f"{lec.id}/oq", lecture_id=lec.id, schema=schema, prompt_id=P.OQ[0],
                          prompt_version=P.OQ[1], prompt=block + P.OQ[2].format(lo=lo, hi=hi, types=types)))
    model = R.model_of("oq")
    out = []
    for n, x in enumerate((o.parsed or {}).get("questions", []), 1):
        q, errs = _build(R, lec, x, shown, f"{lec.id}/oq/{n}")
        if q is None:
            R.decisions.add("oq", [lec.id], "question dropped", "; ".join(errs), o, model, question=x["question"])
            continue
        if errs:
            R.decisions.add("oq", [lec.id], "key points dropped", "; ".join(errs), o, model, question=x["question"])
        q["_block"] = block
        out.append(q)
    if o.parsed is None:
        R.flag(lec.id, f"open questions: answer unusable ({o.errors})")
    R.acts[lec.id]["open_questions"] = out
    R.acts[lec.id]["_oq_shown"] = shown


def _show(it: Item) -> str:
    q = it.obj
    kps = "\n".join(f"- {k['text']} (keywords: {', '.join(k['keywords'])})" for k in q["key_points"])
    return (f"Open question (asks the learner to {P.OQ_TYPES[q['type']]}): {q['prompt']}\n"
            f"Reference answer: {q['reference_answer']}\nKey points a good answer contains:\n{kps}")


def judge_lecture(R: Run, lec: Lecture):
    qs = R.acts[lec.id]["open_questions"]
    if not qs:
        return
    block, shown = qs[0]["_block"], R.acts[lec.id]["_oq_shown"]
    pids = [p.id for p in lec.parts]

    def rewrite(failed):
        props = _q_props(pids)
        r = rewrite_items(R, key=f"{lec.id}/oq", lid=lec.id, prefix=block, failed=failed, show=_show,
                          item_schema={"properties": props},
                          rules="Keep the question's type. The question is answerable from what the lecture teaches; "
                                "the reference answer (3 to 6 sentences) rests only on the material above; 3 to 5 key "
                                "points, each with 2 to 6 keywords that appear word for word in the reference answer "
                                "and the numbers of the sentences above that support it.",
                          check=lambda it, x: _build(R, lec, x, shown, it.obj["_key"])[1] if
                          _build(R, lec, x, shown, it.obj["_key"])[0] is None else [])
        return {k: {**_build(R, lec, x, shown, failed[k].obj["_key"])[0], "_block": block} for k, x in r.items()}

    crit = ("Open question: ok only if it is answerable from what the lecture teaches (above) and asks for the kind "
            "of thinking stated, the reference answer is correct and supported by the material above, and the key "
            "points match the reference answer and are what a good answer must contain.")
    items = judge_unit(R, key=f"{lec.id}/oq", lid=lec.id, prefix=block, show=_show, criteria=crit, rewrite=rewrite,
                       items=[Item(q, "open_question", [s for k in q["key_points"] for s in k["sources"]]) for q in qs])
    kept = []
    for it in items:
        if it.ok:
            kept.append(it.obj)
        else:
            R.decisions.add("judge", [lec.id], "open question dropped", "failed the judge after a rewrite",
                            item=it.obj["_key"])
    for n, q in enumerate(kept, 1):
        q["id"] = f"{lec.id}/OQ{n}"
    R.acts[lec.id]["open_questions"] = kept
