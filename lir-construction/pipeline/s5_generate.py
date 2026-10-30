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
MAP_MAX_LECTURE_NODES, N_OPEN_QUESTIONS = 15, 4
FAILURE = re.compile(r"\b(fail\w*|error\w*|mistake\w*|wrong|pitfall\w*|bug\w*|careful|break\w*|diverg\w*|"
                     r"go(es)? wrong|doesn'?t work|won'?t work|problem with)\b", re.I)


def _rng(key: str) -> random.Random:
    return random.Random(zlib.crc32(key.encode()))


def _jump(c: dict) -> dict:
    i = c["introduced"]
    return {"lecture_id": i["lecture_id"], "t": i["t"], "sentence_id": i["sentence_id"]}


# ------------------------------------------------------------------ primer
def _recall_call(R: Run, lec: Lec, pos: int):
    prev, now = R.state.snapshot(pos - 1), R.state.snapshot(pos)
    new = {cid for cid, c in now["concepts"].items() if c["intro_pos"] == pos}
    links = {}  # earlier concept -> (new concept, rel, evidence)
    # rule: follow "earlier prerequisite_of / used_in new" edges; other links only if there are none
    for e in now["edges"]:
        if e["rel"] in ("prerequisite_of", "used_in") and e["src"] in prev["concepts"] and e["dst"] in new:
            links.setdefault(e["src"], (e["dst"], e["rel"], e["evidence"]["sentence_ids"]))
    if not links:
        for e in now["edges"]:
            for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
                if a in prev["concepts"] and b in new:
                    links.setdefault(a, (b, "linked", e["evidence"]["sentence_ids"]))
    earlier = sorted(links, key=lambda c: -prev["concepts"][c]["salience"])[:MAX_RECALL]
    if not earlier:
        return None
    lines = []
    for cid in earlier:
        c, (nb, rel, _) = prev["concepts"][cid], links[cid]
        lines.append(f"{cid}: {c['name']} (lecture {c['introduced']['lecture_id']}): "
                     f"{c['definition'] or '(no definition recorded)'} | needed for: {now['concepts'][nb]['name']}")
    schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
        "items": {"type": "array", "minItems": len(earlier), "maxItems": len(earlier), "items": {
            "type": "object", "additionalProperties": False, "required": ["concept_id", "question", "recap"],
            "properties": {"concept_id": {"type": "string", "enum": earlier},
                           "question": {"type": "string", "maxLength": 250},
                           "recap": {"type": "string", "maxLength": 300}}}}}}

    def check(x):
        got = [i["concept_id"] for i in x["items"]]
        return [] if sorted(got) == sorted(earlier) else [f"give exactly one item for each of {earlier}"]

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
            why = (f"{now['concepts'][nb]['name']} builds on it ({rel.replace('_', ' ')} edge)"
                   if rel != "linked" else f"it is linked to {now['concepts'][nb]['name']}, new in this lecture")
            recall.append({"concept_id": cid, "concept": c["name"], "for_new_concept_id": nb,
                           "question": it["question"].strip(), "recap": it["recap"].strip(), "jump_to": _jump(c),
                           "intent": intent(["prior_knowledge_activation", "retrieval_practice"], "active", "remember",
                                            f"primer.recall.{rel}_edge", f"{c['name']} is recalled because {why}.",
                                            ev)})
    rationale = (f"Objectives and {len(key_terms)} new key terms are shown before the lecture as an advance organizer"
                 + (f"; {len(recall)} recall items reactivate earlier concepts the lecture builds on." if recall
                    else "; no earlier concept links into this lecture, so there are no recall items."))
    return {"type": "primer",
            "intent": intent(["advance_organizer"] + (["prior_knowledge_activation"] if recall else []),
                             "active" if recall else "passive", "remember", "primer.standard", rationale),
            "lecture_goal": lec.lecture_goal, "objectives": lec.objectives, "key_terms": key_terms, "recall": recall}


# ------------------------------------------------------------------ quiz
QUIZ_TYPES = ["multiple_choice", "multiple_choice", "true_false", "yes_no"]
QUIZ_RULES = ("Rules: the item must be answerable from the material it tests; test understanding, not wording trivia; "
              "do not copy the point; multiple choice has exactly 4 options and exactly one correct option, wrong "
              "options are plausible misconceptions of similar length, no \"all/none of the above\", correct option "
              "first; multiple-choice and yes/no stems are questions ending with \"?\"; give a one-sentence "
              "explanation for every option.")
_s = lambda n: {"type": "string", "maxLength": n}
MCQ = {"type": "object", "additionalProperties": False, "required": ["stem", "options", "explanations"],
       "properties": {"stem": _s(300), "options": {"type": "array", "minItems": 4, "maxItems": 4, "items": _s(200)},
                      "explanations": {"type": "array", "minItems": 4, "maxItems": 4, "items": _s(300)}}}
TF = {"type": "object", "additionalProperties": False, "required": ["statement", "explanation_true", "explanation_false"],
      "properties": {"statement": _s(300), "explanation_true": _s(300), "explanation_false": _s(300)}}
YN = {"type": "object", "additionalProperties": False, "required": ["question", "explanation_yes", "explanation_no"],
      "properties": {"question": _s(300), "explanation_yes": _s(300), "explanation_no": _s(300)}}


def _item_errors(t: str, q: dict, point: str, label: str) -> list[str]:
    errs = []
    stem = q.get("stem") or q.get("statement") or q.get("question") or ""
    if t == "multiple_choice":
        errs += V.check_quiz_options(q["options"], 0, label)
    if t != "true_false" and not stem.strip().endswith("?"):
        errs.append(f"{label}: write the stem as a question ending with '?'")
    if t != "true_false" and V.similar(stem, point) > 0.9:  # a true/false statement may restate its point
        errs.append(f"{label}: the stem copies the point it tests; ask about it instead")
    return errs


def single_item_schema(t: str, correct: str):
    """Schema and checks for regenerating one quiz item (used by the judge's repair step)."""
    if t == "multiple_choice":
        return ("multiple-choice item (4 options, correct option first)", MCQ,
                lambda x: _item_errors(t, x, "", "item"))
    if t == "true_false":
        return (f"true/false statement whose correct answer is {correct}", TF, lambda x: [])
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


def _interleave_target(R: Run, lec: Lec, seg: Seg, pos: int) -> dict | None:
    """At most one quiz item per segment reviews an earlier lecture: an earlier concept linked to this segment."""
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


def _quiz_call(R: Run, lec: Lec, seg: Seg, pos: int) -> Call:
    kps = seg.key_points
    targets = [kps[i % len(kps)] for i in range(4)]
    inter = _interleave_target(R, lec, seg, pos)
    rng = _rng(f"{lec.id}/{seg.id}/answers")
    tf_answer, yn_answer = rng.choice(["True", "False"]), rng.choice(["Yes", "No"])
    points = [kp["text"] for kp in targets]
    if inter:  # q2 reviews the earlier concept (interleaving)
        points[1] = f"{inter['concept']}: {inter['definition']}"
    lines = []
    for i, (t, point) in enumerate(zip(QUIZ_TYPES, points), 1):
        kind = {"multiple_choice": "multiple choice, 4 options",
                "true_false": f"true/false statement, correct answer: {tf_answer}",
                "yes_no": f"yes/no question, correct answer: {yn_answer}"}[t]
        src = (f"testing this point from an earlier lecture ({inter['lecture_id']}), which the learner has seen"
               if inter and i == 2 else "testing this key point")
        lines.append(f"q{i} ({kind}), {src}: {point}")
    schema = {"type": "object", "additionalProperties": False, "required": ["q1", "q2", "q3", "q4"],
              "properties": {"q1": MCQ, "q2": MCQ, "q3": TF, "q4": YN}}

    def check(x):
        errs = []
        for i, (t, point) in enumerate(zip(QUIZ_TYPES, points), 1):
            errs += _item_errors(t, x[f"q{i}"], point, f"q{i}")
        stems = [x["q1"]["stem"], x["q2"]["stem"], x["q3"]["statement"], x["q4"]["question"]]
        if len({re.sub(r"\W+", " ", t.lower()) for t in stems}) < 4:
            errs.append("the four items must be different questions")
        return errs

    return Call(key=f"{lec.id}/{seg.id}/quiz", lecture_id=lec.id,
                prompt=prefix(R, lec, seg) + P.QUIZ[2].format(items="\n".join(lines)), schema=schema,
                prompt_id=P.QUIZ[0], prompt_version=P.QUIZ[1], check=check, stage="stage5_quiz",
                ctx={"kind": "quiz", "seg": seg, "targets": targets, "tf": tf_answer, "yn": yn_answer, "inter": inter})


def _quiz(lec: Lec, seg: Seg, o) -> dict | None:
    x = o.parsed
    if x is None:
        return None
    items = []
    inter = o.call.ctx["inter"]
    for i, (t, kp) in enumerate(zip(QUIZ_TYPES, o.call.ctx["targets"]), 1):
        correct = {"true_false": o.call.ctx["tf"], "yes_no": o.call.ctx["yn"]}.get(t, "")
        item = {"id": f"{seg.id}.Q{i}", "item_type": t, "target_key_point": kp["id"],
                **single_item_fields(t, x[f"q{i}"], f"{o.call.key}/q{i}", correct)}
        bloom = "understand" if t == "multiple_choice" else "remember"
        if inter and i == 2:
            item["target_key_point"] = f"{inter['lecture_id']}:{inter['concept_id']}"
            item["interleaved_from"] = inter
            item["intent"] = intent("retrieval_practice", "active", bloom, "quiz.interleave.earlier_concept",
                                    f"Interleaved review of {inter['concept']} from {inter['lecture_id']}, which this "
                                    f"segment builds on.", [])
        else:
            item["intent"] = intent("retrieval_practice", "active", bloom, f"quiz.target_key_point.{t}",
                                    f"Tests key point {kp['id']}: {kp['text'][:120]}", kp["sentence_ids"])
        items.append(item)
    return {"items": items, "explanations_shown": "after_all_items"}


# ------------------------------------------------------------------ summary
def _summary_parts(R: Run, lec: Lec, seg: Seg, pos: int):
    now = R.state.snapshot(pos)
    cs = [now["concepts"][c] for c in seg.concept_ids if c in now["concepts"]]
    cs.sort(key=lambda c: -c["salience"])
    cs = cs[:MAX_SUMMARY_CONCEPTS]
    need = [c for c in cs if not c["definition"]]
    return now, cs, need


def _summary_call(R: Run, lec: Lec, seg: Seg, pos: int) -> Call:
    now, cs, need = _summary_parts(R, lec, seg, pos)
    names = [c["name"] for c in need]
    explain = ("Also, for each of these concepts used in the segment, write a one-sentence explanation of it as "
               "it is used here: " + "; ".join(names)) if names else ""
    schema = {"type": "object", "additionalProperties": False, "required": ["recap", "explanations"], "properties": {
        "recap": {"type": "string", "maxLength": 700},
        "explanations": {"type": "array", "minItems": len(names), "maxItems": len(names), "items": {
            "type": "object", "additionalProperties": False, "required": ["concept", "explanation"],
            "properties": {"concept": {"type": "string", "enum": names or ["-"]},
                           "explanation": {"type": "string", "maxLength": 300}}}}}}

    def check(x):
        errs = []
        n = V.sentence_count(x["recap"])
        if not 2 <= n <= 3:
            errs.append(f"the recap has {n} sentences; write 2 to 3")
        if sorted(e["concept"] for e in x["explanations"]) != sorted(names):
            errs.append(f"explain each of these concepts exactly once: {names}")
        return errs

    return Call(key=f"{lec.id}/{seg.id}/summary", lecture_id=lec.id,
                prompt=prefix(R, lec, seg) + P.SUMMARY[2].format(explain=explain), schema=schema,
                prompt_id=P.SUMMARY[0], prompt_version=P.SUMMARY[1], check=check, stage="stage5_summary",
                ctx={"kind": "summary", "seg": seg, "pos": pos})


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
                                  "to_concept_id": b, "jump_to": _jump(c)})
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
    return {"recap": recap, "key_concepts": concepts, "key_terms": key_terms, "earlier_links": links[:MAX_EARLIER_LINKS],
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
    now = R.state.snapshot(pos)
    C = now["concepts"]
    here = [c for c in C.values() if any(m["lecture_id"] == lec.id for m in c["mentions"])]
    here.sort(key=lambda c: -c["salience"])
    here_ids = {c["id"] for c in here}
    touching = [e for e in now["edges"] if e["src"] in here_ids or e["dst"] in here_ids]
    with_edges = {x for e in touching for x in (e["src"], e["dst"]) if x in here_ids}
    keep = [c for c in here if c["id"] in with_edges][:MAP_MAX_LECTURE_NODES]
    keep += [c for c in here if c not in keep][:max(0, MAP_MAX_LECTURE_NODES - len(keep))]
    keep_ids = {c["id"] for c in keep}
    earlier_ids = {x for e in touching for x in (e["src"], e["dst"])
                   if x not in here_ids and x in C and C[x]["intro_pos"] < pos
                   and (e["src"] in keep_ids or e["dst"] in keep_ids)}
    nodes = keep + [C[x] for x in earlier_ids]
    node_ids = {c["id"] for c in nodes}
    edges = [{"src": e["src"], "rel": e["rel"], "dst": e["dst"], "label": e["label"]}
             for e in now["edges"] if e["src"] in node_ids and e["dst"] in node_ids]
    # seeds: the lecture's own top concepts (introduced here first), plus 1 or 2 earlier anchors
    own = [c for c in keep if c["intro_pos"] == pos] + [c for c in keep if c["intro_pos"] != pos]
    seeds = [c["id"] for c in own[:4]]
    earlier_nodes = [c["id"] for c in nodes if c["intro_pos"] < pos and c["id"] not in seeds]
    anchors = sorted(earlier_nodes, key=lambda x: -C[x]["salience"])[:2]
    seeds += anchors
    node = lambda c: {"concept_id": c["id"], "name": c["name"], "lecture_id": c["introduced"]["lecture_id"],
                      "is_seed": c["id"] in seeds}
    ev = sorted({i for e in now["edges"] if e["evidence"]["lecture_id"] == lec.id
                 and e["src"] in node_ids and e["dst"] in node_ids for i in e["evidence"]["sentence_ids"]})
    return {"instructions": "Build a concept map of this lecture. Start from the seed concepts: add the concepts you "
                            "think belong to the lecture, draw links between related concepts, and label each link "
                            "with a short phrase (for example \"is part of\" or \"is used in\"). Then compare your map "
                            "with the reference map.",
            "seeds": [node(C[x]) for x in seeds], "reference_nodes": [node(c) for c in nodes],
            "reference_edges": edges,
            "intent": intent("concept_mapping", "constructive", "analyze", "cmap.state_k.one_edge",
                             f"Concept map with {len(seeds)} seeds ({len(anchors)} from earlier lectures); the reference "
                             f"has {len(nodes)} nodes and {len(edges)} links, built from state[{lec.id}].", ev)}


# ------------------------------------------------------------------ after the judge
def refresh_derived(R: Run):
    """Rebuild the code-built parts after the judge dropped edges or changed definitions."""
    R.state.snapshots.clear()
    for pos, lec in enumerate(R.lectures, 1):
        now = R.state.snapshot(pos)
        edges = {frozenset((e["src"], e["dst"])) for e in now["edges"]}
        primer = lec.phases[0]
        primer["key_terms"] = _primer_key_terms(R, pos)
        primer["recall"] = [r for r in primer["recall"]
                            if frozenset((r["concept_id"], r["for_new_concept_id"])) in edges]
        for ph in lec.phases:
            if ph["type"] == "active":
                seg = lec.seg(ph["segment_id"])
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
            calls.append(_quiz_call(R, lec, seg, pos))
            calls.append(_summary_call(R, lec, seg, pos))
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
            qo, so = by[f"{lec.id}/{seg.id}/quiz"], by[f"{lec.id}/{seg.id}/summary"]
            R.record(qo, "stage5_quiz", f"{lec.id}.{seg.id}.quiz")
            R.record(so, "stage5_summary", f"{lec.id}.{seg.id}.summary")
            quiz = _quiz(lec, seg, qo)
            if quiz is None or not qo.ok:
                R.flag(lec.id, f"{seg.id}: quiz failed validation: {qo.errors}")
            if not so.ok:
                R.flag(lec.id, f"{seg.id}: summary failed validation: {so.errors}")
            phases.append({"type": "active", "segment_id": seg.id,
                           "intent": intent(["retrieval_practice", "summarizing"], "active", "understand",
                                            "active.after_segment", f"Quiz and summary after {seg.id}.",
                                            [seg.a, seg.b]),
                           "quiz": quiz or {"items": [], "explanations_shown": "after_all_items"},
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
