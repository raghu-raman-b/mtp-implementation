"""Recall before lecture k: the concepts that the lecture map carries into k, strongest link first, at most MAX_RECALL.
One call for the lecture writes a question and answer per concept, from what the learner knew before lecture k only:
the definitions the earlier lectures gave (term definitions, not the course-wide canonical one) and every earlier
facet. Each item jumps back to where the concept was introduced. One judge call; failed items are rewritten once and
judged again, then dropped."""
from __future__ import annotations

from pipeline.llm import Call

from . import addr as A
from . import prompts as P
from .context import Lecture, Run
from .judge import Item, judge_unit, rewrite_items
from .s5_facets import earlier
from .s8_lecture_map import incoming

MAX_RECALL = 4


def targets(R: Run, lec: Lecture) -> list[str]:
    C = R.registry.concepts
    with R.lock:
        taught = {cid: sum(1 for f in C[cid].facets if not f["only_mentioned"] and A.lecture_of(f["part"]) == lec.id)
                  for cid in C}
    out = []
    for link in incoming(R, lec):
        for cid in sorted(link["concepts"], key=lambda c: -taught[c]):
            if cid not in out:
                out.append(cid)
    return out[:MAX_RECALL]


def material(R: Run, lec: Lecture, cid: str) -> tuple[str, list[str]]:
    c = R.registry.concepts[cid]
    terms = {t["id"]: (l, t) for l in R.lectures if l.pos < lec.pos for p in l.parts for t in p.terms}
    defs = [(l, t) for tid in c.terms if tid in terms for l, t in [terms[tid]]]
    facets = [f for f in earlier(R, cid, lec.pos) if not f["only_mentioned"] and f["says"]]
    lines = [f"  - definition given in lecture {l.id}: {t['definition']}" for l, t in defs[-3:]]
    lines += [f"  - {f['part']}: {f['says']}" for f in facets]
    sources = list(dict.fromkeys([l.s(i) for l, t in defs[-3:] for i in t["sentences"][:2]]
                                 + [s for f in facets for s in f["sentences"][:2]]))
    return "\n".join(lines), sources


def run_lecture(R: Run, lec: Lecture):
    C = R.registry.concepts
    got = [(cid, *material(R, lec, cid)) for cid in targets(R, lec)]
    got = [g for g in got if g[1]]
    if not got:
        return
    text = "\n\n".join(f'C{k}: "{C[cid].name}"{C[cid].alias_text()}\n{mat}' for k, (cid, mat, _) in enumerate(got, 1))
    labels = [f"C{k}" for k in range(1, len(got) + 1)]
    schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
        "items": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["concept", "question", "answer"], "properties": {
                                                 "concept": {"type": "string", "enum": labels},
                                                 "question": {"type": "string"}, "answer": {"type": "string"}}}}}}
    prompt = P.RECALL[2].format(role=P.ROLE, lid=lec.id, title=lec.inp.title, concepts=text)
    o = R.send("recall", Call(key=f"{lec.id}/recall", lecture_id=lec.id, schema=schema, prompt=prompt,
                              prompt_id=P.RECALL[0], prompt_version=P.RECALL[1]))
    items, seen = [], set()
    for x in (o.parsed or {}).get("items", []):
        k = int(x["concept"][1:]) - 1
        if k in seen or not x["question"].strip() or not x["answer"].strip():
            continue
        seen.add(k)
        cid, mat, sources = got[k]
        items.append({"concept_ids": [cid], "question": x["question"].strip(), "answer": x["answer"].strip(),
                      "sources": sources, "jump_to": C[cid].introduced, "_mat": mat})
    if not items:
        R.decisions.add("recall", [lec.id], "no items", f"no usable answer: {o.errors}", o, R.model_of("recall"))
    pre = prompt.split("Task:", 1)[0]

    def show(it: Item) -> str:
        return (f'Recall question on "{C[it.obj["concept_ids"][0]].name}": "{it.obj["question"]}"\n'
                f'Answer: "{it.obj["answer"]}"')

    def rewrite(failed):
        r = rewrite_items(R, key=f"{lec.id}/recall", lid=lec.id, prefix=pre, failed=failed, show=show,
                          item_schema={"properties": {"question": {"type": "string"}, "answer": {"type": "string"}}},
                          rules="The question makes the learner retrieve what they learned about the concept without "
                                "giving it away; the answer (one or two sentences) rests only on what they learned "
                                "before this lecture.",
                          check=lambda it, x: [] if x["question"].strip() and x["answer"].strip() else ["empty"])
        return {k: {**failed[k].obj, "question": x["question"].strip(), "answer": x["answer"].strip()}
                for k, x in r.items()}

    judged = judge_unit(R, key=f"{lec.id}/recall", lid=lec.id, prefix=pre, show=show, rewrite=rewrite,
                        criteria="Recall item: ok only if the question makes the learner recall this concept without "
                                 "giving the answer away, and the answer is correct and supported by what the learner "
                                 "learned above.",
                        items=[Item(it, "recall", it["sources"] or it["concept_ids"]) for it in items])
    kept = [it.obj for it in judged if it.ok]
    for it in judged:
        if not it.ok:
            R.decisions.add("judge", it.obj["concept_ids"], "recall item dropped", "failed the judge after a rewrite")
    for n, it in enumerate(kept, 1):
        it["id"] = f"{lec.id}/R{n}"
    R.acts[lec.id]["recall"] = kept
