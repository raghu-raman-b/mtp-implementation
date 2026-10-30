"""Stage 6 (layer 3): a larger model judges every generated item; failures are repaired and judged again.

    judge (12B)  ->  repair failures (E4B, with the judge's reason)  ->  judge the repairs  ->  ... (2 repair rounds)

What is judged (the design doc's questions, plus the other generated text):
    segment   sub-goal describes the segment? each definition faithful to its cited sentences? each quiz item
              answerable from the segment alone, and is the marked answer right (and the only right one)?
              summary recap supported by the segment?
    question  open question answerable from the lecture, reference answer correct, key points match it?
    lecture   recall items ask about their concept and recap it correctly? each edge true in its direction?

Whatever still fails after the last round is resolved by code, never left for a human:
    quiz item, open question, recall item, edge, key term  -> dropped
    summary recap                                          -> replaced by the segment's key points
    sub-goal                                               -> replaced by the first key point, verb-led
Only one model fits on the GPU, so the generator and judge servers are swapped as needed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import prompts as P
from . import s5_generate as S5
from . import validate as V
from .context import Lec, Run, Seg
from .llm import Call
from .s2_annotate import prefix, strip_ids
from .transcript import numbered

ROUNDS = 2
EDGE_GROUP = 6   # edges judged per call
JUDGE_ROLE = ("You are a strict reviewer of learning material that was generated automatically from a lecture "
              "transcript. An item passes only if the transcript supports it.")
VERDICT = {"type": "object", "additionalProperties": False, "required": ["reason", "ok"],
           "properties": {"reason": {"type": "string", "maxLength": 300}, "ok": {"type": "boolean"}}}
QUIZ_VERDICT = {"type": "object", "additionalProperties": False, "required": ["reason", "answerable", "correct"],
                "properties": {"reason": {"type": "string", "maxLength": 300}, "answerable": {"type": "boolean"},
                               "correct": {"type": "boolean"}}}
LETTERS = "ABCD"


@dataclass
class Item:
    kind: str                 # subgoal | term | quiz | summary | oq | recall | edge
    lid: str
    sid: str | None           # segment (None for lecture-level items)
    key: str                  # unique: "L03/S2/quiz/q1"
    ref: dict = field(default_factory=dict)   # what the item points at (e.g. {"index": 0})
    reason: str = ""


def _active(lec: Lec, sid: str) -> dict:
    return next(p for p in lec.phases if p["type"] == "active" and p["segment_id"] == sid)


def _constructive(lec: Lec) -> dict:
    return next(p for p in lec.phases if p["type"] == "constructive")


def _primer(lec: Lec) -> dict:
    return lec.phases[0]


# ------------------------------------------------------------------ collecting items
def _all_items(R: Run) -> list[Item]:
    items = []
    for lec in R.lectures:
        for seg in lec.segments:
            items.append(Item("subgoal", lec.id, seg.id, f"{lec.id}/{seg.id}/subgoal"))
            for t in seg.key_terms:
                items.append(Item("term", lec.id, seg.id, f"{lec.id}/{seg.id}/term/{t['term']}", {"term": t["term"]}))
            for q in _active(lec, seg.id)["quiz"]["items"]:
                items.append(Item("quiz", lec.id, seg.id, f"{lec.id}/{q['id']}", {"id": q["id"]}))
            if _active(lec, seg.id)["summary"]["recap"]:
                items.append(Item("summary", lec.id, seg.id, f"{lec.id}/{seg.id}/summary"))
        for q in _constructive(lec)["open_questions"]:
            items.append(Item("oq", lec.id, q["segment_ids"][0], f"{lec.id}/{q['id']}", {"id": q["id"]}))
        for r in _primer(lec)["recall"]:
            items.append(Item("recall", lec.id, None, f"{lec.id}/recall/{r['concept_id']}", {"cid": r["concept_id"]}))
        for k, e in enumerate(R.state.edges):
            if e["evidence"]["lecture_id"] == lec.id:
                items.append(Item("edge", lec.id, None, f"{lec.id}/edge/{e['src']}-{e['rel']}-{e['dst']}",
                                  {"edge": (e["src"], e["rel"], e["dst"])}))
    return items


def _find_quiz(lec: Lec, qid: str) -> dict | None:
    sid = qid.split(".")[0]
    return next((q for q in _active(lec, sid)["quiz"]["items"] if q["id"] == qid), None)


def _find_oq(lec: Lec, oid: str) -> dict | None:
    return next((q for q in _constructive(lec)["open_questions"] if q["id"] == oid), None)


def _find_edge(R: Run, t: tuple) -> dict | None:
    return next((e for e in R.state.edges if (e["src"], e["rel"], e["dst"]) == t), None)


# ------------------------------------------------------------------ judge prompts
def _seg_judge_call(R: Run, lec: Lec, seg: Seg, items: list[Item]) -> Call:
    lines, props = [], {}
    for it in items:
        if it.kind == "subgoal":
            lines.append(f'subgoal: "{seg.subgoal}"\n  ok = the sub-goal accurately describes what this segment teaches.')
            props["subgoal"] = VERDICT
        elif it.kind == "term":
            t = next(x for x in seg.key_terms if x["term"] == it.ref["term"])
            k = f"term_{len([p for p in props if p.startswith('term_')]) + 1}"
            it.ref["slot"] = k
            cited = " ".join(f"[{i}]" for i in t["sentence_ids"])
            lines.append(f'{k}: "{t["term"]}" defined as "{t["definition"]}" (cited sentences {cited})\n'
                         f"  ok = the definition is faithful to the cited sentences: nothing contradicts them and "
                         f"nothing important is invented.")
            props[k] = VERDICT
        elif it.kind == "quiz":
            q = _find_quiz(lec, it.ref["id"])
            k = q["id"].split(".")[1].lower()
            it.ref["slot"] = k
            opts = "  ".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(q["options"]))
            extra = ""
            if q.get("interleaved_from"):
                f = q["interleaved_from"]
                extra = (f"\n  This item reviews an earlier lecture ({f['lecture_id']}), so judge answerability "
                         f"against this definition instead of the transcript: {f['concept']}: {f['definition']}")
            lines.append(f'{k} ({q["item_type"].replace("_", " ")}): "{q["stem"]}"\n  {opts}\n'
                         f'  Marked correct: {LETTERS[q["correct_index"]]}){extra}\n'
                         f"  answerable = a learner who watched only this segment can answer it; correct = the "
                         f"marked option is right and no other option is also right.")
            props[k] = QUIZ_VERDICT
        elif it.kind == "summary":
            lines.append(f'summary: "{_active(lec, seg.id)["summary"]["recap"]}"\n'
                         f"  ok = every statement in the recap is supported by the transcript.")
            props["summary"] = VERDICT
        elif it.kind == "oq":
            q = _find_oq(lec, it.ref["id"])
            k = f"question_{q['id'][2:]}"
            it.ref["slot"] = k
            kps = "; ".join(x["text"] for x in q["key_points"])
            lines.append(f'{k} (open question for the learner): "{q["prompt"]}"\n  reference answer: "{q["reference_answer"]}"\n'
                         f"  key points: {kps}\n"
                         f"  ok = a learner who watched the lecture can answer it, the reference answer is correct and "
                         f"supported by the transcript, and the key points match the reference answer.")
            props[k] = VERDICT
    prompt = (f"{JUDGE_ROLE}\n\nCourse: {R.course.title}\nLecture: {lec.inp.title}\n\n"
              f"Transcript of one segment, one sentence per line with its ID in brackets:\n"
              f"{numbered(lec.sentences[seg.a:seg.b + 1])}\n\n"
              f"Check each item below against this transcript.\n\n" + "\n\n".join(lines) +
              "\n\nFor every item give a short reason first (what is wrong, or \"fine\"), then the verdict.")
    schema = {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
    return Call(key=f"{lec.id}/{seg.id}/judge", lecture_id=lec.id, prompt=prompt, schema=schema,
                prompt_id="judge.segment", prompt_version="1", stage="stage6_judge", ctx={"items": items})


def _oq_judge_call(R: Run, lec: Lec, it: Item) -> Call:
    q = _find_oq(lec, it.ref["id"])
    seg = lec.seg(q["segment_ids"][0])
    kps = "\n".join(f"- {k['text']}" for k in q["key_points"])
    prompt = (f"{JUDGE_ROLE}\n\nCourse: {R.course.title}\nLecture: {lec.inp.title}\n\n"
              f"Transcript of one segment, one sentence per line with its ID in brackets:\n"
              f"{numbered(lec.sentences[seg.a:seg.b + 1])}\n\n"
              f"Open-ended question for the learner:\n{q['prompt']}\n\nReference answer:\n{q['reference_answer']}\n\n"
              f"Key points a good answer must contain:\n{kps}\n\n"
              f"ok = a learner who watched this lecture can answer the question, the reference answer is correct and "
              f"supported by the transcript, and the key points match the reference answer. Give a short reason "
              f"first, then the verdict.")
    return Call(key=f"{lec.id}/{q['id']}/judge", lecture_id=lec.id, prompt=prompt, schema=VERDICT,
                prompt_id="judge.open_question", prompt_version="1", stage="stage6_judge", ctx={"items": [it]})


def _lecture_judge_call(R: Run, lec: Lec, items: list[Item]) -> Call:
    st = R.state
    pos = st.pos_of[lec.id]
    snap = st.snapshot(pos)
    C = snap["concepts"]
    lines, props, cids = [], {}, set()
    for it in items:
        if it.kind == "recall":
            r = next(x for x in _primer(lec)["recall"] if x["concept_id"] == it.ref["cid"])
            k = f"recall_{len([p for p in props if p.startswith('recall_')]) + 1}"
            it.ref["slot"] = k
            cids.add(r["concept_id"])
            lines.append(f'{k}: recall item about "{r["concept"]}"\n  question: {r["question"]}\n  recap: {r["recap"]}\n'
                         f"  ok = the question asks about this concept (its answer is the concept's definition) and "
                         f"the recap states the definition correctly.")
        else:
            e = _find_edge(R, it.ref["edge"])
            k = f"edge_{len([p for p in props if p.startswith('edge_')]) + 1}"
            it.ref["slot"] = k
            cids.update([e["src"], e["dst"]])
            ev = " ".join(f"[{i}] {lec.sentences[i].text}" for i in e["evidence"]["sentence_ids"]
                          if 0 <= i < len(lec.sentences))
            lines.append(f'{k}: "{C[e["src"]]["name"]}" {e["rel"]} "{C[e["dst"]]["name"]}" (map label: '
                         f'"{e["label"]}")\n  evidence: {ev}\n'
                         f"  ok = the evidence or the definitions support this relation in this direction.")
        props[k] = VERDICT
    defs = "\n".join(f"- {C[c]['name']}: {C[c]['definition'] or '(no definition recorded)'}" for c in sorted(cids)
                     if c in C)
    prompt = (f"{JUDGE_ROLE}\n\nCourse: {R.course.title}\nLecture {lec.id}: {lec.inp.title}\n\nConcepts:\n{defs}\n\n"
              f"Relation types: prerequisite_of (src must be understood before dst), part_of (src is a component of "
              f"dst), example_of (src is an instance of dst), contrasts_with, leads_to (src causes or produces dst), "
              f"used_in (src is a tool or step in dst).\n\nCheck each item:\n\n" + "\n\n".join(lines) +
              "\n\nFor every item give a short reason first, then the verdict.")
    schema = {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
    return Call(key=f"{lec.id}/lecture/judge", lecture_id=lec.id, prompt=prompt, schema=schema,
                prompt_id="judge.lecture", prompt_version="1", stage="stage6_judge", ctx={"items": items})


def _judge(R: Run, items: list[Item], rnd: int) -> list[Item]:
    """Judge the items; return those that fail, with the judge's reason."""
    by_seg, lec_items, calls = defaultdict(list), defaultdict(list), []
    for it in items:
        if it.kind in ("recall", "edge"):
            lec_items[it.lid].append(it)
        else:
            by_seg[(it.lid, it.sid)].append(it)
    for (lid, sid), its in by_seg.items():
        lec = R.lec(lid)
        calls.append(_seg_judge_call(R, lec, lec.seg(sid), its))
    for lid, its in lec_items.items():  # small groups: a long list of edges makes the judge think for too long
        recall = [i for i in its if i.kind == "recall"]
        edges = [i for i in its if i.kind == "edge"]
        groups = ([recall] if recall else []) + [edges[k:k + EDGE_GROUP] for k in range(0, len(edges), EDGE_GROUP)]
        for g, grp in enumerate(groups):
            c = _lecture_judge_call(R, R.lec(lid), grp)
            c.key = f"{lid}/lecture/judge/{g}"
            calls.append(c)
    failed = []
    for o in R.judge.run("stage6_judge", calls, f"judge round {rnd + 1}: {len(items)} items"):
        R.record(o, "stage6_judge", f"{o.call.key}.r{rnd + 1}", llm=R.judge)
        if o.parsed is None and any(e.startswith("budget:") for e in o.errors):
            for it in o.call.ctx["items"]:  # never sent: the API budget ran out
                it.reason = "not judged: API budget reached"
                R.unjudged.append(it)
            continue
        for it in o.call.ctx["items"]:
            if o.parsed is None:
                it.reason = "the judge's answer was unusable"
                failed.append(it)
                continue
            v = o.parsed[it.ref.get("slot", it.kind)]
            ok = (v["answerable"] and v["correct"]) if it.kind == "quiz" else v["ok"]
            if not ok:
                it.reason = v["reason"]
                failed.append(it)
    return failed


# ------------------------------------------------------------------ repairs (generator model)
def _repair_calls(R: Run, failed: list[Item]) -> list[Call]:
    calls = []
    for it in failed:
        lec = R.lec(it.lid)
        if it.kind in ("recall", "edge"):
            continue  # optional items are dropped, not repaired
        seg = lec.seg(it.sid)
        pre = prefix(R, lec, seg)
        head = "A reviewer rejected material generated for this segment.\n"
        if it.kind == "subgoal":
            task = (f'{head}Rejected sub-goal: "{seg.subgoal}"\nReason: {it.reason}\n\nTask: write a new sub-goal: what '
                    f"the learner achieves in this segment, one short phrase that starts with a verb, at most 15 words.")
            schema = {"type": "object", "additionalProperties": False, "required": ["subgoal"],
                      "properties": {"subgoal": {"type": "string", "maxLength": 160}}}
            check = lambda x: V.check_verb_first(x["subgoal"], "subgoal")
        elif it.kind == "term":
            t = next(x for x in seg.key_terms if x["term"] == it.ref["term"])
            task = (f'{head}Rejected definition of "{t["term"]}": "{t["definition"]}"\nReason: {it.reason}\n\nTask: write '
                    f"a one-sentence definition of \"{t['term']}\" that is faithful to sentences {t['sentence_ids']}.")
            schema = {"type": "object", "additionalProperties": False, "required": ["definition"],
                      "properties": {"definition": {"type": "string", "maxLength": 300}}}
            check = None
        elif it.kind == "quiz":
            q = _find_quiz(lec, it.ref["id"])
            kp = next((k for k in seg.key_points if k["id"] == q["target_key_point"]), None)
            point = (f"{q['interleaved_from']['concept']}: {q['interleaved_from']['definition']} (from lecture "
                     f"{q['interleaved_from']['lecture_id']})" if q.get("interleaved_from") else
                     (kp["text"] if kp else seg.key_points[0]["text"]))
            kind, schema, check = S5.single_item_schema(q["item_type"], q["options"][q["correct_index"]])
            opts = " | ".join(q["options"])
            task = (f'{head}Rejected quiz item ({q["item_type"].replace("_", " ")}): "{q["stem"]}" options: {opts}; marked '
                    f'correct: "{q["options"][q["correct_index"]]}"\nReason: {it.reason}\n\nTask: write a replacement '
                    f"{kind} that tests this point: {point}\n" + S5.QUIZ_RULES)
        elif it.kind == "summary":
            task = (f'{head}Rejected recap: "{_active(lec, seg.id)["summary"]["recap"]}"\nReason: {it.reason}\n\nTask: '
                    f"write a new recap of this segment: 2 to 3 sentences, plain language, only what the segment says.")
            schema = {"type": "object", "additionalProperties": False, "required": ["recap"],
                      "properties": {"recap": {"type": "string", "maxLength": 700}}}
            check = lambda x: ([] if 2 <= V.sentence_count(x["recap"]) <= 3 else ["write 2 to 3 sentences"])
        elif it.kind == "oq":
            q = _find_oq(lec, it.ref["id"])
            plan = R.oq_plans[lec.id][int(q["id"][2:]) - 1]
            call = S5.oq_call(R, lec, int(q["id"][2:]), plan)
            call.prompt += (f'\n\nA previous version was rejected by a reviewer.\nRejected question: "{q["prompt"]}"\n'
                            f"Reason: {it.reason}\nWrite a better one.")
            call.key, call.stage, call.ctx = f"{it.key}/repair", "stage6_repair", {"item": it, **call.ctx}
            calls.append(call)
            continue
        calls.append(Call(key=f"{it.key}/repair", lecture_id=lec.id, prompt=pre + task, schema=schema,
                          prompt_id=f"repair.{it.kind}", prompt_version="1", check=check, stage="stage6_repair",
                          ctx={"item": it}))
    return calls


def _apply_repair(R: Run, it: Item, x) -> bool:
    lec = R.lec(it.lid)
    seg = lec.seg(it.sid) if it.sid else None
    if it.kind == "subgoal":
        seg.subgoal = x["subgoal"].strip().rstrip(".")
        seg.subgoal = seg.subgoal[:1].upper() + seg.subgoal[1:]
        for p in lec.phases:
            if p["type"] == "segment" and p["segment_id"] == seg.id:
                p["subgoal"] = seg.subgoal
    elif it.kind == "term":
        t = next(x2 for x2 in seg.key_terms if x2["term"] == it.ref["term"])
        _replace_definition(R, lec, t, strip_ids(x["definition"]))
    elif it.kind == "quiz":
        q = _find_quiz(lec, it.ref["id"])
        q.update(S5.single_item_fields(q["item_type"], x, f"{lec.id}/{q['id']}/repair", q["options"][q["correct_index"]]))
    elif it.kind == "summary":
        _active(lec, seg.id)["summary"]["recap"] = x["recap"].strip()
    elif it.kind == "oq":
        q = _find_oq(lec, it.ref["id"])
        new = S5.oq_from(lec, x, R.oq_plans[lec.id][int(q["id"][2:]) - 1], int(q["id"][2:]))
        q.update(new)
    return True


def _replace_definition(R: Run, lec: Lec, t: dict, new: str | None):
    """Change (or with None, remove) a key term's definition everywhere it was copied to."""
    old = t["definition"]
    cid = t.get("concept_id")
    if new:
        t["definition"] = new
    if cid and cid in R.state.concepts:
        c = R.state.concepts[cid]
        c.definitions = [(p, l, (new if d == old else d)) for p, l, d in c.definitions if new or d != old]
        R.state.snapshots.clear()


# ------------------------------------------------------------------ final resolution by code
def _resolve(R: Run, it: Item):
    lec = R.lec(it.lid)
    seg = lec.seg(it.sid) if it.sid else None
    if it.kind == "quiz":
        quiz = _active(lec, seg.id)["quiz"]
        quiz["items"] = [q for q in quiz["items"] if q["id"] != it.ref["id"]]
        return "dropped"
    if it.kind == "oq":
        cp = _constructive(lec)
        cp["open_questions"] = [q for q in cp["open_questions"] if q["id"] != it.ref["id"]]
        return "dropped"
    if it.kind == "recall":
        pr = _primer(lec)
        pr["recall"] = [r for r in pr["recall"] if r["concept_id"] != it.ref["cid"]]
        return "dropped"
    if it.kind == "edge":
        R.state.edges = [e for e in R.state.edges if (e["src"], e["rel"], e["dst"]) != it.ref["edge"]]
        R.state.snapshots.clear()
        return "dropped"
    if it.kind == "term":
        t = next(x for x in seg.key_terms if x["term"] == it.ref["term"])
        _replace_definition(R, lec, t, None)
        seg.key_terms = [x for x in seg.key_terms if x["term"] != it.ref["term"]]
        return "dropped"
    if it.kind == "summary":
        _active(lec, seg.id)["summary"]["recap"] = " ".join(k["text"].rstrip(".") + "." for k in seg.key_points[:3])
        return "replaced by key points"
    if it.kind == "subgoal":
        kp = seg.key_points[0]["text"].rstrip(".")
        seg.subgoal = "Understand that " + kp[:1].lower() + kp[1:] if kp else seg.subgoal
        for p in lec.phases:
            if p["type"] == "segment" and p["segment_id"] == seg.id:
                p["subgoal"] = seg.subgoal
        return "replaced by key point"
    return "kept"


def run(R: Run, start_judge, start_generator):
    items = _all_items(R)
    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # lid -> kind -> counter
    for it in items:
        stats[it.lid][it.kind]["judged"] += 1
    R.unjudged = []
    R.log(f"  {len(items)} items to judge across {len(R.lectures)} lectures", "judge")
    pending = items
    resolved_log = defaultdict(list)
    for rnd in range(ROUNDS + 1):
        start_judge()
        failed = _judge(R, pending, rnd)
        for it in pending:
            if it in R.unjudged:
                continue
            if it not in failed:
                stats[it.lid][it.kind]["passed_first" if rnd == 0 else "repaired"] += 1
        R.log(f"  round {rnd + 1}: {len(pending) - len(failed)}/{len(pending)} passed", "judge")
        if not failed:
            break
        optional = [it for it in failed if it.kind in ("recall", "edge")]
        for it in optional:
            _resolve(R, it)
            stats[it.lid][it.kind]["dropped"] += 1
            resolved_log[it.lid].append({"item": it.key, "reason": it.reason, "action": "dropped"})
        failed = [it for it in failed if it not in optional]
        if rnd == ROUNDS or not failed:
            for it in failed:
                action = _resolve(R, it)
                stats[it.lid][it.kind]["dropped" if action == "dropped" else "replaced_by_code"] += 1
                resolved_log[it.lid].append({"item": it.key, "reason": it.reason, "action": action})
            break
        start_generator()
        outs = R.llm.run("stage6_repair", _repair_calls(R, failed), f"repair round {rnd + 1}: {len(failed)} items")
        pending = []
        for o in outs:
            it = o.call.ctx["item"]
            R.record(o, "stage6_repair", f"{o.call.key}.r{rnd + 1}")
            if o.parsed is not None and o.ok and _apply_repair(R, it, o.parsed):
                pending.append(it)
            else:  # the repair itself failed the code checks: resolve now
                action = _resolve(R, it)
                stats[it.lid][it.kind]["dropped" if action == "dropped" else "replaced_by_code"] += 1
                resolved_log[it.lid].append({"item": it.key, "reason": it.reason, "action": action})
        if not pending:
            break
    for it in R.unjudged:
        stats[it.lid][it.kind]["not_judged_budget"] += 1
    if R.unjudged:
        R.log(f"  ! API budget reached: {len(R.unjudged)} items were not judged (they passed the code checks)", "warn")
    for lec in R.lectures:
        lec.quality = {"judge_model": R.judge.model, "rounds": ROUNDS,
                       "checks": {k: dict(v) for k, v in stats[lec.id].items()},
                       "resolved_by_code": resolved_log[lec.id]}
    S5.refresh_derived(R)  # dropped edges and definitions change maps, links and primers
    R.dump("stage6_judge", {l.id: l.quality for l in R.lectures})
