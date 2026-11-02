"""Recall before lecture k: the concepts that the lecture map carries into k, strongest link first, at most MAX_RECALL.
One item per concept: a question and its answer, from what the learner knew before lecture k (the definition as of
lecture k-1 and earlier facets), with a jump back to where the concept was introduced."""
from __future__ import annotations

from pydantic import BaseModel

from pipeline.llm import Call

from . import prompts as P
from .context import Lecture, Run
from .judge import judge_fix, rewrite_call

MAX_RECALL = 4


class RecallQA(BaseModel):
    question: str
    answer: str


def targets(R: Run, lec: Lecture) -> list[str]:
    C = R.registry.concepts
    taught_here = lambda cid: sum(1 for f in C[cid].facets if not f["only_mentioned"] and f["part"].startswith(lec.id + "/"))
    out = []
    for link in sorted((l for l in R.lecture_map if l["dst"] == lec.id), key=lambda l: -l["weight"]):
        for cid in sorted(link["concepts"], key=lambda c: -taught_here(c)):
            if cid not in out:
                out.append(cid)
    return out[:MAX_RECALL]


def _prev(R: Run, lec: Lecture) -> str | None:
    return next((l.id for l in R.lectures if l.pos == lec.pos - 1), None)


def material(R: Run, lec: Lecture, cid: str) -> tuple[str, list[str]]:
    c = R.registry.concepts[cid]
    prev = _prev(R, lec)
    d = c.definition_as_of(R, prev) if prev else None
    facets = [f for f in c.facets if not f["only_mentioned"] and R.pos(f["part"].split("/")[0]) < lec.pos][-6:]
    lines = ([f"- Definition (as of lecture {d['as_of']}): {d['text']}"] if d else []) + \
            [f"- In lecture {f['part'].split('/')[0]}: {f['says']}" for f in facets]
    sources = list(dict.fromkeys((d["sources"][:4] if d else []) + [s for f in facets for s in f["sentences"][:2]]))
    return "\n".join(lines), sources


def _pre(R: Run, lec: Lecture, cid: str, mat: str) -> str:
    c = R.registry.concepts[cid]
    return (f"{P.ROLE}\n\nThe learner is about to watch lecture {lec.id}: \"{lec.inp.title}\". It builds on "
            f"\"{c.name}\"{c.alias_text()}, which they met in earlier lectures.\nWhat they learned about it before "
            f"this lecture:\n{mat}\n\n")


def calls(R: Run) -> list[tuple[str, Call]]:
    out = []
    for lec in R.lectures:
        for cid in targets(R, lec):
            mat, sources = material(R, lec, cid)
            if not mat:
                continue
            c = R.registry.concepts[cid]
            prompt = P.RECALL[2].format(role=P.ROLE, lid=lec.id, title=lec.inp.title, name=c.name,
                                        aliases=c.alias_text(), material=mat)
            out.append(("recall", Call(key=f"{lec.id}/recall/{cid}", lecture_id=lec.id, prompt=prompt, schema=RecallQA,
                                       prompt_id=P.RECALL[0], prompt_version=P.RECALL[1],
                                       check=lambda x: [] if x.question.strip() and x.answer.strip() else ["empty"],
                                       ctx={"kind": "recall", "lec": lec, "cid": cid, "mat": mat, "sources": sources})))
    return out


def take(R: Run, o):
    lec, cid = o.call.ctx["lec"], o.call.ctx["cid"]
    if o.parsed is None:
        R.decisions.add("recall", [cid], "no item", f"no usable answer: {o.errors}", o)
        return
    R.acts[lec.id]["recall"].append({"concept_ids": [cid], "question": o.parsed.question.strip(),
                                     "answer": o.parsed.answer.strip(), "sources": o.call.ctx["sources"],
                                     "jump_to": R.registry.concepts[cid].introduced,
                                     "_prompt": o.call.prompt, "_mat": o.call.ctx["mat"]})


def judge_job(R: Run, lec: Lecture, llm):
    def job(send):
        kept = []
        for it in R.acts[lec.id]["recall"]:
            cid = it["concept_ids"][0]
            pre = _pre(R, lec, cid, it["_mat"])

            def rw(x, reason, it=it):
                y = rewrite_call(send, R, llm, key=f"{lec.id}/recall/{cid}", lid=lec.id, prompt=it["_prompt"],
                                 spec=P.RECALL, schema=RecallQA, previous=f"Q: {x['question']} A: {x['answer']}",
                                 reason=reason)
                return {**x, "question": y.question.strip(), "answer": y.answer.strip()} if y else None
            new, ok = judge_fix(send, R, llm, key=f"{lec.id}/recall/{cid}", lid=lec.id, prefix=pre, item=it,
                                show=lambda x: f'Recall question: "{x["question"]}"\nAnswer: "{x["answer"]}"',
                                criteria="ok is true only if the question makes the learner recall this concept "
                                         "without giving the answer away, and the answer is correct and supported by "
                                         "what the learner learned above.",
                                subject=it["sources"] or [cid], kind="recall", rewrite=rw)
            (kept.append(new) if ok else R.decisions.add("judge", [cid], "recall item dropped",
                                                         "failed the judge after a rewrite", item=f"{lec.id}/recall"))
        for n, it in enumerate(kept, 1):
            it["id"] = f"{lec.id}/R{n}"
        R.acts[lec.id]["recall"] = kept
    return job
