"""Stage 5: generate the learning components.

Code assembles most of each component from stages 2-4 and decides targets, item types and question types;
the LLM writes only the wording. All calls of all lectures go to the server as one batch.

Leakage rule: lecture k reads only state[k] and its own annotations; the primer reads state[k-1].
"""
from __future__ import annotations

import random
import re
import zlib

from . import prompts as P
from . import validate as V
from .context import Lec, Run, Seg, intent
from .llm import Call
from .s2_annotate import prefix

MAX_RECALL, MAX_KEY_TERMS, MAX_SUMMARY_CONCEPTS, MAX_EARLIER_LINKS = 4, 8, 8, 6
MAP_MAX_NODES, MAP_MAX_EARLIER, N_OPEN_QUESTIONS = 14, 4, 4
FAILURE = re.compile(r"\b(fail\w*|error\w*|mistake\w*|wrong|pitfall\w*|bug\w*|careful|break\w*|diverg\w*|"
                     r"go(es)? wrong|doesn'?t work|won'?t work|problem with)\b", re.I)


def _rng(key: str) -> random.Random:
    return random.Random(zlib.crc32(key.encode()))


def _jump(c: dict) -> dict:
    i = c["introduced"]
    return {"lecture_id": i["lecture_id"], "t": i["t"], "sentence_id": i["sentence_id"]}


# ------------------------------------------------------------------ primer
RECALL_RANK = {"prerequisite_of": 0, "used_in": 0, "linked": 1, "mentioned": 2}


def _recall_candidates(R: Run, lec: Lec, pos: int) -> dict:
    """Earlier concepts this lecture builds on, best first: concepts with a prerequisite / used-in edge into this
    lecture's concepts, then any other edge, then earlier concepts the lecture mentions again. Reads state[k-1] for
    what the learner knows, plus lecture k's own annotations (its mentions and edges)."""
    prev, now = R.state.snapshot(pos - 1), R.state.snapshot(pos)
    known = {cid: c for cid, c in prev["concepts"].items() if c["definition"]}
    here = {cid for cid, c in now["concepts"].items() if any(m["lecture_id"] == lec.id for m in c["mentions"])}
    cands = {}  # earlier concept -> (concept here, rule, evidence sentence ids)

    def add(a, b, rule, ev):
        if a in known and (a not in cands or RECALL_RANK[rule] < RECALL_RANK[cands[a][1]]):
            cands[a] = (b, rule, ev)

    for e in now["edges"]:
        if e["evidence"]["lecture_id"] != lec.id:
            continue
        if e["rel"] in ("prerequisite_of", "used_in") and e["dst"] in here and e["src"] not in here - set(known):
            add(e["src"], e["dst"], e["rel"], e["evidence"]["sentence_ids"])
        for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
            if b in here and b != a:
                add(a, b, "linked", e["evidence"]["sentence_ids"])
    for cid in here & set(known):
        ms = [m for m in now["concepts"][cid]["mentions"] if m["lecture_id"] == lec.id]
        add(cid, None, "mentioned", sorted({i for m in ms for i in m["sentence_ids"]})[:4])
    n_segs = lambda cid: len({m["segment_id"] for m in now["concepts"][cid]["mentions"] if m["lecture_id"] == lec.id})
    order = sorted(cands, key=lambda c: (RECALL_RANK[cands[c][1]], -n_segs(c), -known[c]["salience"]))
    return {c: cands[c] for c in order[:MAX_RECALL]}


def _recall_call(R: Run, lec: Lec, pos: int):
    links = _recall_candidates(R, lec, pos)
    if not links:
        return None
    prev, now = R.state.snapshot(pos - 1), R.state.snapshot(pos)
    earlier = list(links)
    lines = []
    for cid in earlier:
        c, (nb, rule, _) = prev["concepts"][cid], links[cid]
        why = f"needed for: {now['concepts'][nb]['name']}" if nb else "used again in this lecture"
        lines.append(f"{cid}: {c['name']} (lecture {c['introduced']['lecture_id']}): {c['definition']} | {why}")
    schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
        "items": {"type": "array", "minItems": len(earlier), "maxItems": len(earlier), "items": {
            "type": "object", "additionalProperties": False, "required": ["concept_id", "question", "recap"],
            "properties": {"concept_id": {"type": "string", "enum": earlier},
                           "question": {"type": "string", "maxLength": 250},
                           "recap": {"type": "string", "maxLength": 400}}}}}}

    def check(x):
        got = [i["concept_id"] for i in x["items"]]
        errs = [] if sorted(got) == sorted(earlier) else [f"give exactly one item for each of {earlier}"]
        for i in x["items"]:
            errs += V.check_subject_question(i["question"], f"question about {i['concept_id']}")
        return errs

    prompt = P.RECALL[2].format(role=P.ROLE, lecture_id=lec.id, title=lec.inp.title, items="\n".join(lines))
    return Call(key=f"{lec.id}/recall", lecture_id=lec.id, prompt=prompt, schema=schema, prompt_id=P.RECALL[0],
                prompt_version=P.RECALL[1], check=check, required=False, stage="stage5_primer",
                ctx={"kind": "recall", "links": links, "prev": prev, "now": now})


def _primer_key_terms(R: Run, pos: int) -> list[dict]:
    now = R.state.snapshot(pos)
    new = [c for c in now["concepts"].values() if c["intro_pos"] == pos and c["definition"]]
    new.sort(key=lambda c: -c["salience"])
    return [{"concept_id": c["id"], "term": c["name"], "definition": c["definition"], "salience": c["salience"],
             "introduced": _jump(c)} for c in new[:MAX_KEY_TERMS]]


def _primer(R: Run, lec: Lec, pos: int, recall_out) -> dict:
    now = R.state.snapshot(pos)
    key_terms = _primer_key_terms(R, pos)
    recall = []
    if recall_out is not None and recall_out.parsed:
        R.record(recall_out, "stage5_primer", f"{lec.id}.primer.recall")
        links, prev = recall_out.call.ctx["links"], recall_out.call.ctx["prev"]
        for it in recall_out.parsed["items"]:
            cid = it["concept_id"]
            if cid not in links or any(r["concept_id"] == cid for r in recall):
                continue
            c = prev["concepts"][cid]
            nb, rel, ev = links[cid]
            if R.state.pos_of[c["introduced"]["lecture_id"]] >= pos:  # recall must point to an earlier lecture
                continue
            why = {"linked": lambda: f"it is linked to {now['concepts'][nb]['name']} in this lecture",
                   "mentioned": lambda: "this lecture uses it again"}.get(
                rel, lambda: f"{now['concepts'][nb]['name']} builds on it ({rel.replace('_', ' ')} edge)")()
            recall.append({"concept_id": cid, "concept": c["name"], "for_new_concept_id": nb,
                           "question": it["question"].strip(), "recap": it["recap"].strip(), "jump_to": _jump(c),
                           "intent": intent(["prior_knowledge_activation", "retrieval_practice"], "active", "remember",
                                            f"primer.recall.{rel}" + ("" if rel == "mentioned" else "_edge"),
                                            f"{c['name']} is recalled because {why}.",
                                            ev)})
    rationale = (f"Objectives and {len(key_terms)} new key terms are shown before the lecture as an advance organizer"
                 + (f"; {len(recall)} recall items reactivate earlier concepts the lecture builds on." if recall
                    else "; no earlier concept links into this lecture, so there are no recall items."))
    return {"type": "primer",
            "intent": intent(["advance_organizer"] + (["prior_knowledge_activation"] if recall else []),
                             "active" if recall else "passive", "remember", "primer.standard", rationale),
            "lecture_goal": lec.lecture_goal, "objectives": lec.objectives, "key_terms": key_terms, "recall": recall}


# ------------------------------------------------------------------ quiz
MAX_QUIZ = 4
QUIZ_RULES = ("Rules: the item must be answerable from the material it tests; test understanding of the subject, "
              "not what the course, lecture or instructor says, and never what an abbreviation stands for; do not "
              "copy the point; multiple choice has exactly 4 options and exactly one correct option, wrong options "
              "are plausible misconceptions of similar length, no \"all/none of the above\", correct option first; "
              "multiple-choice and yes/no stems are questions ending with \"?\"; give a one-sentence explanation "
              "for every option.")
_s = lambda n: {"type": "string", "maxLength": n}
MCQ = {"type": "object", "additionalProperties": False, "required": ["stem", "options", "explanations"],
       "properties": {"stem": _s(300), "options": {"type": "array", "minItems": 4, "maxItems": 4, "items": _s(200)},
                      "explanations": {"type": "array", "minItems": 4, "maxItems": 4, "items": _s(300)}}}
TF = {"type": "object", "additionalProperties": False, "required": ["statement", "explanation_true", "explanation_false"],
      "properties": {"statement": _s(300), "explanation_true": _s(300), "explanation_false": _s(300)}}
YN = {"type": "object", "additionalProperties": False, "required": ["question", "explanation_yes", "explanation_no"],
      "properties": {"question": _s(300), "explanation_yes": _s(300), "explanation_no": _s(300)}}
ITEM = {"type": "object", "additionalProperties": False,
        "required": ["key_point", "type", "question", "options", "correct_answer", "explanations"],
        "properties": {"key_point": {"type": "string"},
                       "type": {"type": "string", "enum": ["multiple_choice", "true_false", "yes_no"]},
                       "question": _s(300),
                       "options": {"type": "array", "maxItems": 4, "items": _s(200)},
                       "correct_answer": {"type": "string", "enum": ["first option", "True", "False", "Yes", "No"]},
                       "explanations": {"type": "array", "minItems": 2, "maxItems": 4, "items": _s(300)}}}


def _item_errors(t: str, q: dict, point: str, label: str) -> list[str]:
    """Checks for the single-item formats (MCQ / TF / YN), used by the judge's repair step."""
    errs = []
    stem = q.get("stem") or q.get("statement") or q.get("question") or ""
    if t == "multiple_choice":
        errs += V.check_quiz_options(q["options"], 0, label)
    if t != "true_false" and not stem.strip().endswith("?"):
        errs.append(f"{label}: write the stem as a question ending with '?'")
    if t != "true_false" and point and V.similar(stem, point) > 0.9:
        errs.append(f"{label}: the stem copies the point it tests; ask about it instead")
    return errs + V.check_subject_question(stem, label)


def _gen_item_errors(q: dict, point: str, label: str) -> list[str]:
    """Checks for one item of the quiz call, where the model chose the item type."""
    t, stem, ans = q["type"], q["question"].strip(), q["correct_answer"]
    errs = []
    if t == "multiple_choice":
        if len(q["options"]) != 4 or len(q["explanations"]) != 4:
            errs.append(f"{label}: multiple choice needs exactly 4 options and 4 explanations")
        else:
            errs += V.check_quiz_options(q["options"], 0, label)
        if ans != "first option":
            errs.append(f'{label}: for multiple choice, put the correct option first and set correct_answer to "first option"')
    else:
        want = ("True", "False") if t == "true_false" else ("Yes", "No")
        if ans not in want:
            errs.append(f"{label}: correct_answer must be {want[0]} or {want[1]}")
        if len(q["explanations"]) != 2:
            errs.append(f"{label}: give 2 explanations, for {want[0]} then {want[1]}")
    if t != "true_false" and not stem.endswith("?"):
        errs.append(f"{label}: write the question so it ends with '?'")
    if t == "true_false" and stem.endswith("?"):
        errs.append(f"{label}: a true/false item is a statement, not a question")
    if t != "true_false" and V.similar(stem, point) > 0.9:
        errs.append(f"{label}: the question copies the key point it tests; ask about it instead")
    return errs + V.check_subject_question(stem, label)


def single_item_schema(t: str, correct: str):
    """Schema and checks for regenerating one quiz item (used by the judge's repair step)."""
    if t == "multiple_choice":
        return ("multiple-choice item (4 options, correct option first)", MCQ,
                lambda x: _item_errors(t, x, "", "item"))
    if t == "true_false":
        return (f"true/false statement whose correct answer is {correct}", TF,
                lambda x: V.check_subject_question(x["statement"], "item")
                + (["item: a true/false item is a statement, not a question"] if x["statement"].strip().endswith("?") else []))
    return (f"yes/no question whose correct answer is {correct}", YN, lambda x: _item_errors(t, x, "", "item"))


def single_item_fields(t: str, q: dict, key: str, correct: str) -> dict:
    """Turn a generated item into LIR fields; code decides where the correct option goes."""
    if t == "multiple_choice":
        order = list(range(4))
        _rng(key).shuffle(order)
        return {"stem": q["stem"].strip(), "options": [q["options"][j].strip() for j in order],
                "correct_index": order.index(0), "explanations": [q["explanations"][j].strip() for j in order]}
    if t == "true_false":
        opts = ["True", "False"]
        return {"stem": q["statement"].strip(), "options": opts, "correct_index": opts.index(correct),
                "explanations": [q["explanation_true"].strip(), q["explanation_false"].strip()]}
    opts = ["Yes", "No"]
    return {"stem": q["question"].strip(), "options": opts, "correct_index": opts.index(correct),
            "explanations": [q["explanation_yes"].strip(), q["explanation_no"].strip()]}


def _fields_from_generated(q: dict, key: str) -> dict:
    t = q["type"]
    if t == "multiple_choice":
        return single_item_fields(t, {"stem": q["question"], "options": q["options"], "explanations": q["explanations"]},
                                  key, "")
    if t == "true_false":
        return single_item_fields(t, {"statement": q["question"], "explanation_true": q["explanations"][0],
                                      "explanation_false": q["explanations"][1]}, key, q["correct_answer"])
    return single_item_fields(t, {"question": q["question"], "explanation_yes": q["explanations"][0],
                                  "explanation_no": q["explanations"][1]}, key, q["correct_answer"])


def _interleave_target(R: Run, lec: Lec, seg: Seg, pos: int) -> dict | None:
    """At most one quiz item per segment may review an earlier lecture: an earlier concept linked to this segment."""
    if pos <= 1:
        return None
    now = R.state.snapshot(pos)
    C = now["concepts"]
    here = set(seg.concept_ids)
    best = None
    for e in now["edges"]:
        for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
            if b in here and a in C and C[a]["intro_pos"] < pos and C[a]["definition"]:
                if best is None or C[a]["salience"] > C[best]["salience"]:
                    best = a
    if best is None:
        return None
    c = C[best]
    return {"concept_id": best, "concept": c["name"], "definition": c["definition"],
            "lecture_id": c["introduced"]["lecture_id"], "t": c["introduced"]["t"]}


def quiz_points(seg: Seg) -> list[dict]:
    """Key points worth quizzing: the subject ones (course logistics are never quizzed)."""
    return [kp for kp in seg.key_points if kp.get("about", "subject") == "subject"]


def _quiz_call(R: Run, lec: Lec, seg: Seg, pos: int) -> Call | None:
    kps = quiz_points(seg)
    if not kps:
        return None
    inter = _interleave_target(R, lec, seg, pos)
    lines = [f"{kp['id']}: {kp['text']}" for kp in kps]
    if inter:
        lines.append(f"R (optional: a concept from an earlier lecture ({inter['lecture_id']}) that the learner has seen; "
                     f"use it only if a good question connects it to this segment): {inter['concept']}: "
                     f"{inter['definition']}")
    ids = [kp["id"] for kp in kps] + (["R"] if inter else [])
    hi = min(MAX_QUIZ, len(ids))
    item = {**ITEM, "properties": {**ITEM["properties"], "key_point": {"type": "string", "enum": ids}}}
    schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
        "items": {"type": "array", "minItems": 1, "maxItems": hi, "items": item}}}
    point_of = {kp["id"]: kp["text"] for kp in kps}
    if inter:
        point_of["R"] = f"{inter['concept']}: {inter['definition']}"

    def check(x):
        errs = []
        for i, q in enumerate(x["items"], 1):
            errs += _gen_item_errors(q, point_of.get(q["key_point"], ""), f"question {i}")
        used = [q["key_point"] for q in x["items"]]
        if len(set(used)) < len(used):
            errs.append("each question must test a different key point")
        if len({re.sub(r"\W+", " ", q["question"].lower()) for q in x["items"]}) < len(x["items"]):
            errs.append("the questions must all be different")
        return errs

    prompt = prefix(R, lec, seg) + P.QUIZ[2].format(points="\n".join(lines), lo=1, hi=hi)
    return Call(key=f"{lec.id}/{seg.id}/quiz", lecture_id=lec.id, prompt=prompt, schema=schema,
                prompt_id=P.QUIZ[0], prompt_version=P.QUIZ[1], check=check, stage="stage5_quiz",
                ctx={"kind": "quiz", "seg": seg, "inter": inter})


def _quiz(lec: Lec, seg: Seg, o) -> dict | None:
    x = o.parsed
    if x is None:
        return None
    items = []
    inter = o.call.ctx["inter"]
    kp_of = {kp["id"]: kp for kp in seg.key_points}
    for i, q in enumerate(x["items"], 1):
        if _gen_item_errors(q, "", "item"):
            continue  # after the retries, an item that still fails the checks is dropped (the others stay)
        t = q["type"]
        item = {"id": f"{seg.id}.Q{len(items) + 1}", "item_type": t, "target_key_point": q["key_point"],
                **_fields_from_generated(q, f"{o.call.key}/q{i}")}
        bloom = "understand" if t == "multiple_choice" else "remember"
        if q["key_point"] == "R" and inter:
            item["target_key_point"] = f"{inter['lecture_id']}:{inter['concept_id']}"
            item["interleaved_from"] = inter
            item["intent"] = intent("retrieval_practice", "active", bloom, "quiz.interleave.earlier_concept",
                                    f"Interleaved review of {inter['concept']} from {inter['lecture_id']}, which this "
                                    f"segment builds on.", [])
        elif q["key_point"] in kp_of:
            kp = kp_of[q["key_point"]]
            item["intent"] = intent("retrieval_practice", "active", bloom, f"quiz.target_key_point.{t}",
                                    f"Tests key point {kp['id']}: {kp['text'][:120]}. The model chose {len(x['items'])} "
                                    f"item(s) for {len(quiz_points(seg))} subject key point(s) and the "
                                    f"{t.replace('_', ' ')} type for this one.", kp["sentence_ids"])
        else:
            continue
        items.append(item)
    return {"items": items, "explanations_shown": "after_item_resolved", "tries": 2}


# ------------------------------------------------------------------ summary
def _summary_parts(R: Run, lec: Lec, seg: Seg, pos: int):
    now = R.state.snapshot(pos)
    cs = [now["concepts"][c] for c in seg.concept_ids if c in now["concepts"]]
    cs.sort(key=lambda c: -c["salience"])
    cs = cs[:MAX_SUMMARY_CONCEPTS]
    need = [c for c in cs if not c["definition"]]
    return now, cs, need


def review_points(seg: Seg) -> list[dict]:
    """Key points that get a check-yourself question in the summary: the subject ones, else all of them."""
    return quiz_points(seg)


def summary_call(R: Run, lec: Lec, seg: Seg, pos: int) -> Call:
    now, cs, need = _summary_parts(R, lec, seg, pos)
    names = [c["name"] for c in need]
    kps = review_points(seg)
    ids = [kp["id"] for kp in kps]
    explain = ("- explanations: for each of these concepts used in the segment, a one-sentence explanation of it as "
               "it is used here: " + "; ".join(names)) if names else ""
    schema = {"type": "object", "additionalProperties": False, "required": ["recap", "review", "explanations"],
              "properties": {
        "recap": {"type": "string", "maxLength": 700},
        "review": {"type": "array", "minItems": len(ids), "maxItems": len(ids), "items": {
            "type": "object", "additionalProperties": False, "required": ["key_point", "question", "answer"],
            "properties": {"key_point": {"type": "string", "enum": ids or ["-"]}, "question": {"type": "string", "maxLength": 250},
                           "answer": {"type": "string", "maxLength": 400}}}},
        "explanations": {"type": "array", "minItems": len(names), "maxItems": len(names), "items": {
            "type": "object", "additionalProperties": False, "required": ["concept", "explanation"],
            "properties": {"concept": {"type": "string", "enum": names or ["-"]},
                           "explanation": {"type": "string", "maxLength": 300}}}}}}

    def check(x):
        errs = []
        n = V.sentence_count(x["recap"])
        if not 2 <= n <= 3:
            errs.append(f"the recap has {n} sentences; write 2 to 3")
        if sorted(r["key_point"] for r in x["review"]) != sorted(ids):
            errs.append(f"write exactly one review question for each key point: {ids}")
        for r in x["review"]:
            if not r["question"].strip().endswith("?"):
                errs.append(f"review question for {r['key_point']} must end with '?'")
            errs += V.check_subject_question(r["question"], f"review question for {r['key_point']}")
            if V.sentence_count(r["answer"]) > 3:
                errs.append(f"the answer for {r['key_point']} is too long; 1 or 2 sentences")
        if sorted(e["concept"] for e in x["explanations"]) != sorted(names):
            errs.append(f"explain each of these concepts exactly once: {names}")
        return errs

    points = "\n".join(f"{kp['id']}: {kp['text']}" for kp in kps) or "(none: this segment is about the course itself, so write no review questions)"
    return Call(key=f"{lec.id}/{seg.id}/summary", lecture_id=lec.id,
                prompt=prefix(R, lec, seg) + P.SUMMARY[2].format(points=points, explain=explain), schema=schema,
                prompt_id=P.SUMMARY[0], prompt_version=P.SUMMARY[1], check=check, stage="stage5_summary",
                ctx={"kind": "summary", "seg": seg, "pos": pos})


def review_items(lec: Lec, seg: Seg, x: dict | None) -> list[dict]:
    kp_of = {kp["id"]: kp for kp in seg.key_points}
    out = []
    for r in (x or {}).get("review", []):
        kp = kp_of.get(r["key_point"])
        if not kp:
            continue
        sid = kp["sentence_ids"][0]
        out.append({"key_point": kp["id"], "question": r["question"].strip(), "answer": r["answer"].strip(),
                    "sentence_ids": kp["sentence_ids"], "t": lec.sentences[sid].start})
    return out


def _earlier_links(lec: Lec, seg: Seg, pos: int, now: dict) -> list[dict]:
    """Concepts introduced earlier (earlier lecture, or earlier in this one) with an edge into this segment."""
    seg_order = [s.id for s in lec.segments]
    here = set(seg.concept_ids)

    def is_earlier(c):
        i = c["introduced"]
        if c["intro_pos"] < pos:
            return True
        return i["lecture_id"] == lec.id and seg_order.index(i["segment_id"]) < seg_order.index(seg.id)

    links = []
    for e in now["edges"]:
        for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
            if b in here and a not in here and a in now["concepts"] and is_earlier(now["concepts"][a]):
                if not any(l["concept_id"] == a for l in links):
                    c = now["concepts"][a]
                    links.append({"concept_id": a, "name": c["name"], "relation": e["rel"], "label": e["label"],
                                  "to_concept_id": b, "jump_to": _jump(c),
                                  "direction": "from_earlier" if a == e["src"] else "to_earlier"})
    return links[:MAX_EARLIER_LINKS]


def _summary(R: Run, lec: Lec, seg: Seg, pos: int, o) -> dict:
    now, cs, need = _summary_parts(R, lec, seg, pos)
    gen = {e["concept"]: e["explanation"].strip() for e in (o.parsed or {}).get("explanations", [])}
    concepts = []
    for c in cs:
        if c["definition"]:
            concepts.append({"concept_id": c["id"], "name": c["name"], "explanation": c["definition"],
                             "explanation_source": "registry_definition"})
        elif c["name"] in gen:
            concepts.append({"concept_id": c["id"], "name": c["name"], "explanation": gen[c["name"]],
                             "explanation_source": "generated"})
    links = _earlier_links(lec, seg, pos, now)
    key_terms = [{"concept_id": t.get("concept_id", ""), "term": t["term"], "definition": t["definition"],
                  "sentence_ids": t["sentence_ids"]} for t in seg.key_terms]
    recap = (o.parsed or {}).get("recap", "").strip()
    return {"recap": recap, "review": review_items(lec, seg, o.parsed), "key_concepts": concepts, "key_terms": key_terms, "earlier_links": links[:MAX_EARLIER_LINKS],
            "learner_highlights": {"source": "ui", "keyed_by": "sentence_id"},
            "intent": intent("summarizing", "passive", "understand", "summary.segment",
                             f"Summary of {seg.id} with {len(concepts)} key concepts and {len(links[:MAX_EARLIER_LINKS])} "
                             f"links to earlier material.", [seg.a, seg.b])}


# ------------------------------------------------------------------ open questions
OQ_RULES = [
    # (question type, rule_id, principles, bloom, content types that trigger it)
    ("fill_in_steps", "oq.fill_steps.derivation_or_procedure", ["worked_example_completion"], "apply",
     {"derivation_or_proof", "procedure_or_algorithm"}),
    ("compare_contrast", "oq.compare.contrasts_edge", ["elaboration"], "analyze", {"comparison"}),
    ("self_explanation", "oq.self_explain.mechanism", ["self_explanation"], "understand", {"mechanism_explanation"}),
    ("apply_new_case", "oq.transfer.example_or_application", ["transfer"], "apply",
     {"worked_example", "application_or_demo"}),
    ("troubleshooting", "oq.troubleshoot.failure_mode", ["elaboration", "transfer"], "analyze",
     {"procedure_or_algorithm", "worked_example"}),
]
FALLBACK = ("explain_to_someone", "oq.explain.fallback", ["generative_learning"], "understand", set())


def _pick_questions(R: Run, lec: Lec, pos: int) -> list[dict]:
    """Code picks the question types from the rule table; returns plans for the LLM calls."""
    now = R.state.snapshot(pos)
    dur = lambda s: s.end - s.start
    seg_text = lambda s: " ".join(x.text for x in lec.sentences[s.a:s.b + 1])
    matches = []
    for qt, rid, pr, bloom, types in OQ_RULES:
        segs = [s for s in lec.segments if s.content_type in types]
        extra = {}
        if qt == "troubleshooting":
            segs = [s for s in segs if FAILURE.search(seg_text(s))]
        if qt == "compare_contrast":
            edges = [e for e in now["edges"] if e["rel"] == "contrasts_with" and e["evidence"]["lecture_id"] == lec.id]
            for e in edges:
                s = lec.seg_of_sentence(e["evidence"]["sentence_ids"][0])
                a, b = now["concepts"][e["src"]]["name"], now["concepts"][e["dst"]]["name"]
                extra[s.id] = (a, b, e["evidence"]["sentence_ids"])
            ids = {s.id for s in segs} | set(extra)
            segs = [s for s in lec.segments if s.id in ids]
        if segs:
            matches.append({"rule": (qt, rid, pr, bloom), "segs": sorted(segs, key=lambda s: -dur(s)),
                            "score": len(segs) + len(extra), "pairs": extra})
    matches.sort(key=lambda m: -m["score"])  # stable: ties keep the table order
    plans, used = [], set()

    def plan(rule, seg, pairs):
        qt, rid, pr, bloom = rule
        pair = pairs.get(seg.id)
        if qt == "compare_contrast" and not pair:
            rid = "oq.compare.comparison_segment"
        rationale = {
            "fill_in_steps": f"Fill-in-the-steps chosen because {seg.id} works through a "
                             f"{seg.content_type.replace('_', ' ')}.",
            "compare_contrast": (f"Compare-and-contrast chosen because the lecture contrasts {pair[0]} with {pair[1]} "
                                 f"({seg.id})." if pair else f"Compare-and-contrast chosen because {seg.id} is a "
                                                             f"comparison segment."),
            "self_explanation": f"Self-explanation chosen because {seg.id} explains how a mechanism works.",
            "apply_new_case": f"Apply-to-a-new-case chosen because {seg.id} is a "
                              f"{seg.content_type.replace('_', ' ')}.",
            "troubleshooting": f"Troubleshooting chosen because {seg.id} describes a procedure and how it can fail.",
            "explain_to_someone": f"Explain-it-to-someone chosen as the fallback question for {seg.id}.",
        }[qt]
        used.add(seg.id)
        return {"qt": qt, "rule_id": rid, "principles": pr, "bloom": bloom, "seg": seg, "pair": pair,
                "rationale": rationale}

    for m in matches:  # the best-matching distinct types first
        if len(plans) == N_OPEN_QUESTIONS:
            break
        seg = next((s for s in m["segs"] if s.id not in used), m["segs"][0])
        plans.append(plan(m["rule"], seg, m["pairs"]))
    by_len = sorted(lec.segments, key=lambda s: -dur(s))
    for s in by_len:  # fallback on segments no question covers yet
        if len(plans) == N_OPEN_QUESTIONS:
            break
        if s.id not in used:
            plans.append(plan(FALLBACK[:4], s, {}))
    for m in matches:  # short lectures: matched types again on other segments
        for s in m["segs"]:
            if len(plans) < N_OPEN_QUESTIONS and not any(p["seg"].id == s.id and p["qt"] == m["rule"][0] for p in plans):
                plans.append(plan(m["rule"], s, m["pairs"]))
    k = 0
    while len(plans) < N_OPEN_QUESTIONS:  # last resort: fallback on the longest segments again
        s = by_len[k % len(by_len)]
        if not any(p["seg"].id == s.id and p["qt"] == FALLBACK[0] for p in plans) or k >= len(by_len):
            plans.append(plan(FALLBACK[:4], s, {}))
        k += 1
    return plans[:N_OPEN_QUESTIONS]


def oq_call(R: Run, lec: Lec, i: int, p: dict) -> Call:
    seg = p["seg"]
    pair = f"{p['pair'][0]} and {p['pair'][1]}" if p["pair"] else "the ideas this segment compares"
    task = P.OQ_TASKS[p["qt"]].format(pair=pair)
    schema = {"type": "object", "additionalProperties": False, "required": ["prompt", "reference_answer", "key_points"],
              "properties": {
                  "prompt": {"type": "string", "maxLength": 900},
                  "reference_answer": {"type": "string", "maxLength": 1500},
                  "key_points": {"type": "array", "minItems": 3, "maxItems": 5, "items": {
                      "type": "object", "additionalProperties": False, "required": ["text", "keywords"],
                      "properties": {"text": {"type": "string", "maxLength": 250},
                                     "keywords": {"type": "array", "minItems": 2, "maxItems": 6,
                                                  "items": {"type": "string", "maxLength": 40}}}}}}}

    def check(x):
        errs = []
        if re.search(r"\bthis (lecture )?segment\b|\bsegment \d", x["prompt"], re.I):
            errs.append("the learner never sees segments: name the topic instead of saying 'this segment'")
        if re.search(r"\bwrite (an? )?(open[- ]ended )?question\b|\bthe learner\b", x["prompt"], re.I):
            errs.append("the prompt must be the question itself, addressed to the learner, not instructions about it")
        for j, kp in enumerate(x["key_points"], 1):
            # code tidies the keywords (drops missing ones, splits long ones); retry only if fewer than 2 survive
            if len(_clean_keywords(kp["keywords"], x["reference_answer"])) < 2:
                miss = V.missing_keywords(kp["keywords"], x["reference_answer"])
                errs.append(f"key point {j} needs at least 2 keywords that appear word for word in the reference "
                            f"answer" + (f"; {miss} do not" if miss else ""))
        return errs

    return Call(key=f"{lec.id}/OQ{i}", lecture_id=lec.id, prompt=prefix(R, lec, seg) + P.OPEN_Q[2].format(task=task),
                schema=schema, prompt_id=P.OPEN_Q[0], prompt_version=P.OPEN_Q[1], check=check,
                stage="stage5_open_questions", ctx={"kind": "oq", "plan": p, "i": i})


def _clean_keywords(keywords: list[str], answer: str) -> list[str]:
    """Keep keywords found in the reference answer; a phrase over 3 words becomes its content words."""
    out = []
    for k in (k.strip() for k in keywords):
        parts = [k] if len(k.split()) <= 3 else [w for w in re.findall(r"[A-Za-z0-9'-]+", k)
                                                 if len(w) > 3 and w.lower() not in V.STOP]
        for p in parts:
            if p and not V.missing_keywords([p], answer) and p.lower() not in (o.lower() for o in out):
                out.append(p)
    return out


def _oq(lec: Lec, o) -> dict | None:
    if o.parsed is None:
        return None
    return oq_from(lec, o.parsed, o.call.ctx["plan"], o.call.ctx["i"])


def oq_from(lec: Lec, x: dict, p: dict, i: int) -> dict:
    kps = []
    for kp in x["key_points"]:
        ok = _clean_keywords(kp["keywords"], x["reference_answer"])
        kps.append({"text": kp["text"].strip(), "keywords": ok if len(ok) >= 2 else [k.strip() for k in kp["keywords"]]})
    seg = p["seg"]
    sources = p["pair"][2] if p["pair"] else [i for kp in seg.key_points for i in kp["sentence_ids"]]
    return {"id": f"OQ{i}", "question_type": p["qt"], "prompt": x["prompt"].strip(),
            "reference_answer": x["reference_answer"].strip(), "key_points": kps, "segment_ids": [seg.id],
            "intent": intent(p["principles"], "constructive", p["bloom"], p["rule_id"], p["rationale"], sources)}


# ------------------------------------------------------------------ concept map (code only)
def _concept_map(R: Run, lec: Lec, pos: int) -> dict:
    """Reference map: this lecture's concepts plus earlier concepts one edge away, cut to a readable core of at most
    MAP_MAX_NODES connected concepts (at most MAP_MAX_EARLIER of them from earlier lectures). Only links that come
    from this lecture or touch a concept it introduces are drawn."""
    now = R.state.snapshot(pos)
    C = now["concepts"]
    here_ids = {c["id"] for c in C.values() if any(m["lecture_id"] == lec.id for m in c["mentions"])}
    touching = [e for e in now["edges"] if (e["src"] in here_ids or e["dst"] in here_ids)
                and (e["evidence"]["lecture_id"] == lec.id or C[e["src"]]["intro_pos"] == pos or C[e["dst"]]["intro_pos"] == pos)]
    deg = {}
    for e in touching:
        for x in (e["src"], e["dst"]):
            deg[x] = deg.get(x, 0) + 1
    rank = lambda cid: (-min(deg.get(cid, 0), 5), -C[cid]["salience"])
    own = sorted([x for x in deg if C[x]["intro_pos"] == pos], key=rank)
    earlier = sorted([x for x in deg if C[x]["intro_pos"] < pos], key=rank)
    n_earlier = min(MAP_MAX_EARLIER, len(earlier), max(2, MAP_MAX_NODES - len(own)))
    keep = set(own[:MAP_MAX_NODES - n_earlier] + earlier[:n_earlier])
    edges = [{"src": e["src"], "rel": e["rel"], "dst": e["dst"], "label": e["label"]}
             for e in touching if e["src"] in keep and e["dst"] in keep]
    linked = {x for e in edges for x in (e["src"], e["dst"])}
    # seeds: the lecture's own top concepts (introduced here), plus 1 or 2 earlier anchors
    intro_here = sorted([c["id"] for c in C.values() if c["intro_pos"] == pos],
                        key=lambda cid: (cid not in linked, -C[cid]["salience"]))
    seeds = intro_here[:4]
    anchors = [x for x in sorted(linked, key=rank) if C[x]["intro_pos"] < pos][:2]
    seeds += anchors
    node_ids = linked | set(seeds)
    nodes = sorted((C[x] for x in node_ids), key=lambda c: (c["intro_pos"] < pos, -c["salience"]))
    node = lambda c: {"concept_id": c["id"], "name": c["name"], "lecture_id": c["introduced"]["lecture_id"],
                      "is_seed": c["id"] in seeds}
    ev = sorted({i for e in touching if e["evidence"]["lecture_id"] == lec.id
                 and e["src"] in keep and e["dst"] in keep for i in e["evidence"]["sentence_ids"]})
    return {"instructions": "Build a concept map of this lecture. Start from the seed concepts: add the concepts you "
                            "think belong to the lecture, draw links between related concepts, and label each link "
                            "with a short phrase (for example \"is part of\" or \"is used in\"). Then compare your map "
                            "with the reference map.",
            "seeds": [node(C[x]) for x in seeds], "reference_nodes": [node(c) for c in nodes],
            "reference_edges": edges,
            "intent": intent("concept_mapping", "constructive", "analyze", "cmap.state_k.one_edge",
                             f"Concept map with {len(seeds)} seeds ({len(anchors)} from earlier lectures); the reference "
                             f"keeps the {len(linked)} best-connected concepts and their {len(edges)} links (of "
                             f"{len(touching)} links touching this lecture), built from state[{lec.id}].", ev)}


# ------------------------------------------------------------------ after the judge
def refresh_derived(R: Run):
    """Rebuild the code-built parts after the judge dropped edges or changed definitions."""
    R.state.snapshots.clear()
    for pos, lec in enumerate(R.lectures, 1):
        now = R.state.snapshot(pos)
        edges = {frozenset((e["src"], e["dst"])) for e in now["edges"]}
        primer = lec.phases[0]
        primer["key_terms"] = _primer_key_terms(R, pos)
        primer["recall"] = [r for r in primer["recall"] if r["concept_id"] in now["concepts"]
                            and (r["for_new_concept_id"] is None
                                 or frozenset((r["concept_id"], r["for_new_concept_id"])) in edges)]
        for ph in lec.phases:
            if ph["type"] == "active":
                seg = lec.seg(ph["segment_id"])
                ph["quiz"]["items"] = [q for q in ph["quiz"]["items"] if not q.get("interleaved_from")
                                       or q["interleaved_from"]["concept_id"] in now["concepts"]]
                sm = ph["summary"]
                sm["earlier_links"] = _earlier_links(lec, seg, pos, now)
                kept = []
                for kc in sm["key_concepts"]:
                    c = now["concepts"].get(kc["concept_id"])
                    if kc["explanation_source"] == "registry_definition":
                        if not c or not c["definition"]:
                            continue  # its definition was rejected by the judge
                        kc["explanation"] = c["definition"]
                    kept.append(kc)
                sm["key_concepts"] = kept
                sm["key_terms"] = [{"concept_id": t.get("concept_id", ""), "term": t["term"],
                                    "definition": t["definition"], "sentence_ids": t["sentence_ids"]}
                                   for t in seg.key_terms]
            elif ph["type"] == "constructive":
                ph["concept_map"] = _concept_map(R, lec, pos)


# ------------------------------------------------------------------ run
def run(R: Run):
    calls, plans = [], {}
    for pos, lec in enumerate(R.lectures, 1):
        c = _recall_call(R, lec, pos)
        if c:
            calls.append(c)
        for seg in lec.segments:
            qc = _quiz_call(R, lec, seg, pos)
            if qc:  # a segment with only course logistics gets no quiz
                calls.append(qc)
            calls.append(summary_call(R, lec, seg, pos))
        plans[lec.id] = _pick_questions(R, lec, pos)
        R.oq_plans = plans
        for i, p in enumerate(plans[lec.id], 1):
            calls.append(oq_call(R, lec, i, p))
        R.log(f"  {lec.id}: open questions {[p['rule_id'] for p in plans[lec.id]]}")
    outs = R.llm.run("stage5_generate", calls, "generate components")
    by = {o.call.key: o for o in outs}

    for pos, lec in enumerate(R.lectures, 1):
        phases = [_primer(R, lec, pos, by.get(f"{lec.id}/recall"))]
        for seg in lec.segments:
            phases.append({"type": "segment", "segment_id": seg.id, "objective_id": seg.objective_id,
                           "subgoal": seg.subgoal, "start": seg.start, "end": seg.end,
                           "sentence_range": [seg.a, seg.b], "highlighting": True,
                           "highlights_resurface_in": ["segment_summary", "lecture_end"],
                           "intent": intent("segmenting", "passive", "understand", "segment.stage1.standalone",
                                            f"{seg.id} runs {(seg.end - seg.start) / 60:.1f} min and was cut where "
                                            f"the instructor completes a goal.", [seg.a, seg.b])})
            qo, so = by.get(f"{lec.id}/{seg.id}/quiz"), by[f"{lec.id}/{seg.id}/summary"]
            R.record(so, "stage5_summary", f"{lec.id}.{seg.id}.summary")
            quiz = None
            if qo is not None:
                R.record(qo, "stage5_quiz", f"{lec.id}.{seg.id}.quiz")
                quiz = _quiz(lec, seg, qo)
                if quiz is None or not qo.ok:
                    R.flag(lec.id, f"{seg.id}: quiz failed validation: {qo.errors}")
            if not so.ok:
                R.flag(lec.id, f"{seg.id}: summary failed validation: {so.errors}")
            phases.append({"type": "active", "segment_id": seg.id,
                           "intent": intent(["retrieval_practice", "summarizing"], "active", "understand",
                                            "active.after_segment", f"Quiz and summary after {seg.id}.",
                                            [seg.a, seg.b]),
                           "quiz": quiz or {"items": [], "explanations_shown": "after_item_resolved", "tries": 2},
                           "summary": _summary(R, lec, seg, pos, so)})
        oqs = []
        for i in range(1, len(plans[lec.id]) + 1):
            o = by[f"{lec.id}/OQ{i}"]
            R.record(o, "stage5_open_questions", f"{lec.id}.OQ{i}")
            q = _oq(lec, o)
            if q is None or not o.ok:
                R.flag(lec.id, f"OQ{i}: open question failed validation: {o.errors}")
            if q:
                oqs.append(q)
        phases.append({"type": "constructive",
                       "intent": intent(["concept_mapping", "generative_learning"], "constructive", "analyze",
                                        "constructive.after_lecture",
                                        "Concept map and open questions after the lecture, to connect and explain "
                                        "the lecture's ideas."),
                       "concept_map": _concept_map(R, lec, pos), "open_questions": oqs,
                       "learner_highlights": {"source": "ui", "keyed_by": "sentence_id", "scope": "lecture"}})
        lec.phases = phases
