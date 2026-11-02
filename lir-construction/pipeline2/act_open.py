"""Open questions per lecture.

    plan    the model picks the questions from the lecture's content: type (the kind of thinking), the parts they draw
            on, and a focus; how many scales with the lecture's length (QUESTIONS_PER_MIN, between MIN_Q and MAX_Q)
    write   question, reference answer, 3-5 key points with keywords (word for word in the reference answer) and
            cited sentences, from the transcript of the chosen parts
    judge   answerable from those parts, of the planned kind, reference answer right and supported, key points match
"""
from __future__ import annotations


from pydantic import BaseModel, Field

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids
from pipeline.s5_generate import _clean_keywords

from . import prompts as P
from .context import Lecture, Run
from .judge import judge_fix, rewrite_call
from .judge_knowledge import _lecture_block

MIN_Q, MAX_Q, MIN_PER_Q = 2, 6, 15     # about one question per 15 minutes of video


class OQKP(BaseModel):
    text: str
    keywords: list[str] = Field(min_length=2, max_length=6)
    sentence_ids: list[int] = Field(min_length=1, max_length=8)


class OQ(BaseModel):
    question: str
    reference_answer: str
    key_points: list[OQKP] = Field(min_length=3, max_length=5)


def bounds(lec: Lecture) -> tuple[int, int]:
    hi = max(MIN_Q, min(MAX_Q, round(lec.inp.duration / 60 / MIN_PER_Q)))
    return min(MIN_Q, hi), hi


def plan_calls(R: Run) -> list[tuple[str, Call]]:
    out = []
    types = "\n".join(f"  {k}: {v}" for k, v in P.OQ_TYPES.items())
    for lec in R.lectures:
        lo, hi = bounds(lec)
        pids = [p.id for p in lec.parts]
        schema = {"type": "object", "additionalProperties": False, "required": ["questions"], "properties": {
            "questions": {"type": "array", "minItems": lo, "maxItems": hi, "items": {
                "type": "object", "additionalProperties": False, "required": ["type", "parts", "focus", "reason"],
                "properties": {"type": {"type": "string", "enum": list(P.OQ_TYPES)},
                               "parts": {"type": "array", "minItems": 1, "maxItems": 3,
                                         "items": {"type": "string", "enum": pids}},
                               "focus": {"type": "string"}, "reason": {"type": "string"}}}}}}
        parts = _lecture_block(R, lec).split("Its parts, each with its goal and key points:\n", 1)[1].strip()
        out.append(("oq_plan", Call(key=f"{lec.id}/oq_plan", lecture_id=lec.id, schema=schema,
                                    prompt=P.OQ_PLAN[2].format(role=P.ROLE, title=lec.inp.title, parts=parts, lo=lo,
                                                               hi=hi, types=types),
                                    prompt_id=P.OQ_PLAN[0], prompt_version=P.OQ_PLAN[1],
                                    ctx={"kind": "oq_plan", "lec": lec})))
    return out


def take_plan(R: Run, o):
    lec = o.call.ctx["lec"]
    plan = o.parsed["questions"] if o.parsed else []
    R.acts[lec.id]["_oq_plan"] = plan
    R.decisions.add("oq_plan", [lec.id], f"{len(plan)} question(s)",
                    "; ".join(f"{q['type']} on {q['parts']}: {q['reason']}" for q in plan) or f"no plan: {o.errors}", o)


def _block(R: Run, lec: Lecture, pids: list[str]) -> str:
    parts = sorted((lec.part(p) for p in dict.fromkeys(pids)), key=lambda p: p.n)
    text = "\n...\n".join(lec.numbered(p.a, p.b) for p in parts)
    return P.excerpt_block(R.course.title, lec.inp.title, text, "parts of the lecture")


def _check(lec: Lecture, pids: list[str]):
    parts = [lec.part(p) for p in pids]

    def check(x: OQ) -> list[str]:
        errs = []
        for j, k in enumerate(x.key_points, 1):
            if len(_clean_keywords(k.keywords, x.reference_answer)) < 2:
                errs.append(f"key point {j} needs at least 2 keywords that appear word for word in the reference answer")
            if any(not any(p.contains(i) for p in parts) for i in k.sentence_ids):
                errs.append(f"key point {j} cites sentences that are not shown above")
        return errs
    return check


def write_calls(R: Run) -> list[tuple[str, Call]]:
    out = []
    for lec in R.lectures:
        for n, q in enumerate(R.acts[lec.id].get("_oq_plan", []), 1):
            block = _block(R, lec, q["parts"])
            prompt = block + P.OQ_WRITE[2].format(type_text=P.OQ_TYPES[q["type"]], focus=q["focus"])
            out.append(("oq", Call(key=f"{lec.id}/oq/{n}", lecture_id=lec.id, prompt=prompt, schema=OQ,
                                   prompt_id=P.OQ_WRITE[0], prompt_version=P.OQ_WRITE[1], check=_check(lec, q["parts"]),
                                   ctx={"kind": "oq", "lec": lec, "plan": q, "block": block})))
    return out


def _build(R: Run, lec: Lecture, q: dict, x: OQ) -> dict:
    kps = []
    for k in x.key_points:
        kw = _clean_keywords(k.keywords, x.reference_answer)
        kps.append({"text": strip_ids(k.text), "keywords": kw if len(kw) >= 2 else [w.strip() for w in k.keywords],
                    "sources": [lec.s(i) for i in sorted(set(k.sentence_ids))]})
    return {"type": q["type"], "prompt": strip_ids(x.question), "reference_answer": strip_ids(x.reference_answer),
            "key_points": kps, "part_ids": sorted(set(q["parts"]), key=lambda p: lec.part(p).n),
            "concept_ids": R.matcher.find(x.question + " " + x.reference_answer, lec.pos)}


def take_write(R: Run, o):
    lec, q = o.call.ctx["lec"], o.call.ctx["plan"]
    if o.parsed is None or not o.ok:
        R.decisions.add("oq", [lec.id], "question dropped", f"failed the checks: {o.errors}", o, plan=q)
        return
    item = _build(R, lec, q, o.parsed)
    item.update({"_key": o.call.key, "_prompt": o.call.prompt, "_block": o.call.ctx["block"], "_plan": q,
                 "_raw": o.parsed.model_dump_json()})
    R.acts[lec.id]["open_questions"].append(item)


def _show(it: dict) -> str:
    kps = "\n".join(f"- {k['text']} (keywords: {', '.join(k['keywords'])})" for k in it["key_points"])
    return (f"Open question (asks the learner to {P.OQ_TYPES[it['type']]}): {it['prompt']}\n"
            f"Reference answer: {it['reference_answer']}\nKey points a good answer contains:\n{kps}")


def judge_job(R: Run, lec: Lecture, it: dict, llm):
    def job(send):
        def rw(x, reason):
            y = rewrite_call(send, R, llm, key=x["_key"], lid=lec.id, prompt=x["_prompt"], spec=P.OQ_WRITE, schema=OQ,
                             previous=x["_raw"], reason=reason, check=_check(lec, x["_plan"]["parts"]))
            return {**_build(R, lec, x["_plan"], y), **{k: v for k, v in x.items() if k.startswith("_")},
                    "_raw": y.model_dump_json()} if y else None
        new, ok = judge_fix(send, R, llm, key=it["_key"], lid=lec.id, prefix=it["_block"], item=it, show=_show,
                            criteria="ok is true only if the question is answerable from these sentences and asks for "
                                     "the kind of thinking stated, the reference answer is correct and supported by "
                                     "the sentences, and the key points match the reference answer and are what a "
                                     "good answer must contain.",
                            subject=[s for k in it["key_points"] for s in k["sources"]], kind="open_question",
                            rewrite=rw)
        if not ok:
            R.decisions.add("judge", [lec.id], "open question dropped", "failed the judge after a rewrite",
                            item=it["_key"])
        return new if ok else None
    return job
