"""Summary per part: a recap (2-3 sentences) and check-yourself questions on the key points the quiz does not test.
A recap that still fails the judge falls back to the part's key points; a review question that still fails is dropped.
"""
from __future__ import annotations

from pydantic import BaseModel

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Lecture, Part, Run
from .judge import judge_fix, rewrite_call
from .s2_parts import prefix


class Recap(BaseModel):
    recap: str


class Review(BaseModel):
    question: str
    answer: str


def _points(p: Part) -> str:
    return "\n".join(f"- {k['text']}" for k in p.key_points) or "(none listed: tie together what the part says)"


def recap_calls(R: Run) -> list[tuple[str, Call]]:
    return [("recap", Call(key=f"{p.id}/recap", lecture_id=lec.id, group=p.id,
                           prompt=prefix(R, lec, p) + P.RECAP[2].format(points=_points(p)), schema=Recap,
                           prompt_id=P.RECAP[0], prompt_version=P.RECAP[1],
                           check=lambda x: [] if x.recap.strip() else ["the recap is empty"],
                           ctx={"kind": "recap", "lec": lec, "part": p}))
            for lec in R.lectures for p in lec.parts]


def _sources(lec: Lecture, p: Part) -> list[str]:
    return [lec.s(i) for i in sorted({i for k in p.key_points for i in k["sentences"]})] or [lec.s(p.a)]


def take_recap(R: Run, o):
    lec, p = o.call.ctx["lec"], o.call.ctx["part"]
    acts = R.acts[lec.id]["parts"][p.id]
    if o.parsed is None:
        acts["recap"] = _fallback(lec, p)
        R.decisions.add("recap", [p.id], "key points used", f"no usable recap: {o.errors}", o)
        return
    acts["recap"] = {"text": strip_ids(o.parsed.recap), "sources": _sources(lec, p), "source": "generated",
                     "_prompt": o.call.prompt}


def _fallback(lec: Lecture, p: Part) -> dict | None:
    if not p.key_points:
        return None
    return {"text": " ".join(k["text"].rstrip(".") + "." for k in p.key_points), "sources": _sources(lec, p),
            "source": "key_points"}


def review_calls(R: Run) -> list[tuple[str, Call]]:
    out = []
    for lec in R.lectures:
        for p in lec.parts:
            tested = {i["key_point"] for i in R.acts[lec.id]["parts"][p.id].get("_plan", [])}
            for k in p.key_points:
                if k["id"] in tested:
                    continue
                out.append(("review", Call(key=f"{k['id']}/review", lecture_id=lec.id, group=p.id,
                                           prompt=prefix(R, lec, p) + P.REVIEW[2].format(point=k["text"]),
                                           schema=Review, prompt_id=P.REVIEW[0], prompt_version=P.REVIEW[1],
                                           check=lambda x: [] if x.question.strip().endswith("?") and x.answer.strip()
                                           else ['the question must end with "?" and the answer must not be empty'],
                                           ctx={"kind": "review", "lec": lec, "part": p, "kp": k})))
    return out


def take_review(R: Run, o):
    lec, p, k = o.call.ctx["lec"], o.call.ctx["part"], o.call.ctx["kp"]
    if o.parsed is None or not o.ok:
        R.decisions.add("review", [k["id"]], "no question", f"failed the format checks: {o.errors}", o)
        return
    R.acts[lec.id]["parts"][p.id]["review"].append({
        "key_point": k["id"], "concept_ids": R.matcher.find(k["text"] + " " + o.parsed.question, lec.pos),
        "question": o.parsed.question.strip(), "answer": o.parsed.answer.strip(),
        "sources": [lec.s(i) for i in k["sentences"]], "_prompt": o.call.prompt})


def judge_part(send, R: Run, lec: Lecture, p: Part, llm):
    acts = R.acts[lec.id]["parts"][p.id]
    pre = prefix(R, lec, p)
    rc = acts.get("recap")
    if rc and rc["source"] == "generated":
        def rw(x, reason):
            y = rewrite_call(send, R, llm, key=f"{p.id}/recap", lid=lec.id, prompt=x["_prompt"], spec=P.RECAP,
                             schema=Recap, previous=x["text"], reason=reason)
            return {**x, "text": strip_ids(y.recap)} if y else None
        new, ok = judge_fix(send, R, llm, key=f"{p.id}/recap", lid=lec.id, prefix=pre, item=rc,
                            show=lambda x: f'Recap of this part: "{x["text"]}"',
                            criteria="ok is true only if every statement in the recap is supported by this part and "
                                     "the recap ties together what the part teaches, in plain language.",
                            subject=[p.id], kind="recap", rewrite=rw)
        acts["recap"] = new if ok else _fallback(lec, p)
        if not ok:
            R.decisions.add("judge", [p.id], "recap replaced by the key points", "failed the judge after a rewrite")
    kept = []
    for it in acts["review"]:
        def rw(x, reason, it=it):
            y = rewrite_call(send, R, llm, key=f"{it['key_point']}/review", lid=lec.id, prompt=it["_prompt"],
                             spec=P.REVIEW, schema=Review, previous=f"Q: {x['question']} A: {x['answer']}",
                             reason=reason)
            return {**x, "question": y.question.strip(), "answer": y.answer.strip()} if y else None
        new, ok = judge_fix(send, R, llm, key=f"{it['key_point']}/review", lid=lec.id, prefix=pre, item=it,
                            show=lambda x: f'Check-yourself question: "{x["question"]}"\nAnswer: "{x["answer"]}"',
                            criteria="ok is true only if the question asks about the subject (not about the lecture) "
                                     "without giving the answer away, and the answer is correct and supported by "
                                     "this part.",
                            subject=it["sources"], kind="review", rewrite=rw)
        if ok:
            kept.append(new)
        else:
            R.decisions.add("judge", it["sources"], "review question dropped", "failed the judge after a rewrite",
                            item=it["key_point"])
    for n, it in enumerate(kept, 1):
        it["id"] = f"{p.id}/V{n}"
    acts["review"] = kept
