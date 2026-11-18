"""Activities per part: one call writes the quiz (0-4 items on the key points worth testing, each with its type and
reason), the recap (2-3 sentences) and a check-yourself question for each key point the quiz does not test. Code
checks each item's format (options distinct, the correct one not much longer than the others, "?" where a question
is asked) and drops the ones that fail; it puts the correct option of a multiple-choice item at a fixed
pseudo-random position. One judge call checks every item of the part; failed items are rewritten once and judged
again; a quiz item or review question that still fails is dropped, a recap falls back to the key points.

Needs only the part's transcript and judged key points, so it runs from the start of the run, filling the GPU.
Items are tagged with concepts at the end (activities.tag), once the registry exists.
"""
from __future__ import annotations

import random
import re
import zlib

from pipeline.llm import Call
from pipeline.s2_annotate import strip_ids

from . import prompts as P
from .context import Lecture, Part, Run
from .judge import Item, judge_unit, rewrite_items
from .s2_parts import prefix

MAX_QUIZ = 4
TYPES = ["multiple_choice", "true_false", "yes_no"]
LETTERS = "ABCD"
QUIZ_PROPS = {"type": {"type": "string", "enum": TYPES}, "stem": {"type": "string"}, "correct": {"type": "string"},
              "wrong": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
              "explanation_correct": {"type": "string"},
              "explanations_wrong": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}}


def _schema(ids: list[str], hi: int) -> dict:
    quiz = {"type": "object", "additionalProperties": False,
            "required": ["key_point", "reason", *QUIZ_PROPS],
            "properties": {"key_point": {"type": "string", "enum": ids}, "reason": {"type": "string"}, **QUIZ_PROPS}}
    review = {"type": "object", "additionalProperties": False, "required": ["key_point", "question", "answer"],
              "properties": {"key_point": {"type": "string", "enum": ids}, "question": {"type": "string"},
                             "answer": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["quiz", "recap", "review"], "properties": {
        "quiz": {"type": "array", "maxItems": hi, "items": quiz}, "recap": {"type": "string"},
        "review": {"type": "array", "items": review}}}


def format_errors(x: dict) -> list[str]:
    """Format only: what a renderer needs to show the item correctly."""
    t, errs = x["type"], []
    stem = x["stem"].strip()
    if t == "multiple_choice":
        opts = [x["correct"]] + x["wrong"]
        if len(x["wrong"]) != 3 or len(x["explanations_wrong"]) != 3:
            errs.append("a multiple-choice item needs exactly 3 wrong options, each with an explanation")
        elif len({re.sub(r"\W+", " ", o.lower()).strip() for o in opts}) < 4:
            errs.append("the four options must all be different")
        else:
            mean_wrong = sum(len(w) for w in x["wrong"]) / 3
            if len(x["correct"]) > 1.4 * mean_wrong + 15:
                errs.append("the correct option is much longer than the wrong ones, which gives it away")
        if not stem.endswith("?"):
            errs.append('the question must end with "?"')
    elif t == "true_false":
        if x["correct"] not in ("True", "False"):
            errs.append('a true/false answer is "True" or "False"')
        if stem.endswith("?"):
            errs.append("a true/false item is a statement, not a question")
    else:
        if x["correct"] not in ("Yes", "No"):
            errs.append('a yes/no answer is "Yes" or "No"')
        if not stem.endswith("?"):
            errs.append('the question must end with "?"')
    return errs


def fields(x: dict, key: str) -> dict:
    t = x["type"]
    if t == "multiple_choice":
        opts = [x["correct"]] + x["wrong"]
        expl = [x["explanation_correct"]] + x["explanations_wrong"]
        order = list(range(4))
        random.Random(zlib.crc32(key.encode())).shuffle(order)
        return {"stem": x["stem"].strip(), "options": [opts[j].strip() for j in order],
                "correct_index": order.index(0), "explanations": [expl[j].strip() for j in order]}
    opts = ["True", "False"] if t == "true_false" else ["Yes", "No"]
    ci = opts.index(x["correct"])
    other = (x["explanations_wrong"] or [""])[0].strip()
    expl = [x["explanation_correct"].strip(), other] if ci == 0 else [other, x["explanation_correct"].strip()]
    return {"stem": x["stem"].strip(), "options": opts, "correct_index": ci, "explanations": expl}


def _quiz_item(lec: Lecture, p: Part, x: dict, key: str) -> dict:
    kp = next(k for k in p.key_points if k["id"] == x["key_point"])
    return {"type": x["type"], "key_point": kp["id"], "concept_ids": [], **fields(x, key),
            "sources": [lec.s(i) for i in kp["sentences"]], "_key": key, "_point": kp["text"],
            "_raw": {k: x[k] for k in QUIZ_PROPS}}


def _fallback(lec: Lecture, p: Part) -> dict | None:
    if not p.key_points:
        return None
    return {"text": " ".join(k["text"].rstrip(".") + "." for k in p.key_points), "sources": _sources(lec, p),
            "source": "key_points"}


def _sources(lec: Lecture, p: Part) -> list[str]:
    return [lec.s(i) for i in sorted({i for k in p.key_points for i in k["sentences"]})] or [lec.s(p.a)]


def run_part(R: Run, lec: Lecture, p: Part):
    acts = R.acts[lec.id]["parts"][p.id]
    if not p.key_points:
        return
    ids = [k["id"] for k in p.key_points]
    points = "\n".join(f"{k['id']}: {k['text']}" for k in p.key_points)
    o = R.send("activities", Call(key=f"{p.id}/activities", lecture_id=lec.id, schema=_schema(ids, min(MAX_QUIZ, len(ids))),
                                  prompt_id=P.ACTIVITIES[0], prompt_version=P.ACTIVITIES[1],
                                  prompt=prefix(R, lec, p) + P.ACTIVITIES[2].format(
                                      points=points, hi=min(MAX_QUIZ, len(ids)), rules=P.QUIZ_RULES)))
    model = R.model_of("activities")
    if o.parsed is None:
        acts["recap"] = _fallback(lec, p)
        R.decisions.add("activities", [p.id], "nothing usable; recap from the key points", f"{o.errors}", o, model)
        return
    x = o.parsed
    tested = set()
    for n, q in enumerate(x["quiz"], 1):
        errs = format_errors(q) + (["a second item on the same key point"] if q["key_point"] in tested else [])
        if errs:
            R.decisions.add("quiz", [p.id], "item dropped", "; ".join(errs), o, model, key_point=q["key_point"])
            continue
        tested.add(q["key_point"])
        R.decisions.add("quiz", [p.id], f"{q['type']} on {q['key_point']}", q["reason"], o, model)
        acts["quiz"].append(_quiz_item(lec, p, q, f"{p.id}/quiz/{n}"))
    acts["recap"] = ({"text": strip_ids(x["recap"]), "sources": _sources(lec, p), "source": "generated"}
                     if x["recap"].strip() else _fallback(lec, p))
    for r in x["review"]:
        if r["key_point"] in tested or not r["question"].strip().endswith("?") or not r["answer"].strip() \
                or any(v["key_point"] == r["key_point"] for v in acts["review"]):
            R.decisions.add("review", [p.id], "question dropped",
                            "its key point is in the quiz, or a second question on it, or no question/answer", o,
                            model, key_point=r["key_point"])
            continue
        kp = next(k for k in p.key_points if k["id"] == r["key_point"])
        acts["review"].append({"key_point": kp["id"], "concept_ids": [], "question": r["question"].strip(),
                               "answer": r["answer"].strip(), "sources": [lec.s(i) for i in kp["sentences"]],
                               "_point": kp["text"]})


def _show(it: Item) -> str:
    x = it.obj
    if it.kind == "quiz":
        opts = "\n".join(f"{LETTERS[k]}. {o}" for k, o in enumerate(x["options"]))
        expl = "\n".join(f"{LETTERS[k]}: {e}" for k, e in enumerate(x["explanations"]))
        return (f"Quiz item ({x['type'].replace('_', ' ')}) testing: {x['_point']}\n{x['stem']}\n{opts}\n"
                f"Marked correct: {LETTERS[x['correct_index']]}\nExplanations:\n{expl}")
    if it.kind == "recap":
        return f'Recap of this part: "{x["text"]}"'
    return f'Check-yourself question on "{x["_point"]}": "{x["question"]}"\nAnswer: "{x["answer"]}"'


CRIT = ("Quiz item: ok only if it is answerable from this part alone, the marked answer is correct and the only "
        "correct one, it tests understanding of the subject that is worth asking (not trivia, not what the lecture or "
        "the instructor says), and every explanation is correct. Recap: ok only if every statement is supported by "
        "this part and it ties together what the part teaches, in plain language. Check-yourself question: ok only "
        "if it asks about the subject (not about the lecture) without giving the answer away, and the answer is "
        "correct and supported by this part.")


def judge_part(R: Run, lec: Lecture, p: Part):
    acts = R.acts[lec.id]["parts"][p.id]
    pre = prefix(R, lec, p)
    items = [Item(q, "quiz", q["sources"]) for q in acts["quiz"]]
    if acts["recap"] and acts["recap"]["source"] == "generated":
        items.append(Item(acts["recap"], "recap", [p.id]))
    items += [Item(v, "review", v["sources"]) for v in acts["review"]]

    def rewrite(failed: list[Item]) -> dict:
        out = {}
        for kind, schema, rules, check, build in [
            ("quiz", {"properties": QUIZ_PROPS}, P.QUIZ_RULES + " Keep the item's type and key point.",
             lambda it, x: format_errors(x) + (["keep the item's type"] if x["type"] != it.obj["type"] else []),
             lambda it, x: {**_quiz_item(lec, p, {**x, "key_point": it.obj["key_point"]}, it.obj["_key"])}),
            ("recap", {"properties": {"recap": {"type": "string"}}},
             "A recap is 2 to 3 plain sentences tying together what this part teaches, nothing else.",
             lambda it, x: [] if x["recap"].strip() else ["empty"],
             lambda it, x: {**it.obj, "text": strip_ids(x["recap"])}),
            ("review", {"properties": {"question": {"type": "string"}, "answer": {"type": "string"}}},
             "A check-yourself question asks about the subject without giving the answer away and ends with \"?\"; "
             "the answer is one or two sentences supported by this part.",
             lambda it, x: [] if x["question"].strip().endswith("?") and x["answer"].strip() else ["format"],
             lambda it, x: {**it.obj, "question": x["question"].strip(), "answer": x["answer"].strip()}),
        ]:
            sel = [(k, it) for k, it in enumerate(failed) if it.kind == kind]
            if not sel:
                continue
            r = rewrite_items(R, key=f"{p.id}/{kind}", lid=lec.id, prefix=pre, failed=[it for _, it in sel],
                              show=_show, item_schema=schema, rules=rules, check=check)
            out.update({sel[k][0]: build(sel[k][1], x) for k, x in r.items()})
        return out

    items = judge_unit(R, key=f"{p.id}/activities", lid=lec.id, prefix=pre, items=items, show=_show, criteria=CRIT,
                       rewrite=rewrite)
    quiz, review = [], []
    for it in items:
        if it.kind == "quiz":
            (quiz.append(it.obj) if it.ok else R.decisions.add("judge", it.subject, "quiz item dropped",
                                                              "failed the judge after a rewrite", item=it.obj["_key"]))
        elif it.kind == "recap":
            acts["recap"] = it.obj if it.ok else _fallback(lec, p)
            if not it.ok:
                R.decisions.add("judge", [p.id], "recap replaced by the key points", "failed the judge after a rewrite")
        else:
            (review.append(it.obj) if it.ok else R.decisions.add("judge", it.subject, "review question dropped",
                                                                "failed the judge after a rewrite"))
    for n, q in enumerate(quiz, 1):
        q["id"] = f"{p.id}/Q{n}"
    for n, v in enumerate(review, 1):
        v["id"] = f"{p.id}/V{n}"
    acts["quiz"], acts["review"] = quiz, review
