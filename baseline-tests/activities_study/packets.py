"""CPU: blind packets for the Sonnet judge, and the key that unblinds them (kept outside the packet folder).

    python3 packets.py

Writes out/sonnet/ (give the judge only this folder):
  INSTRUCTIONS.md         the task, the criteria and the exact output format
  packets/lec_<n>.md      one per lecture: its title, goal and objectives (knowledge/goals.json), the titles of the
                          earlier lectures, then one unit per kind; a unit holds sets X, Y, Z, W (one per system
                          that makes the kind: 4 for the model-made kinds, 3 for concept_map and recall; assigned at
                          random per unit) of items rendered alike (no fact, concept or relationship IDs)
  transcripts/lec_<n>.txt the lecture's transcript, sentences numbered
and out/sonnet_key.json: per unit its lecture, kind, the system behind each set and the source of each item.
At most CAP items per set (a seeded random sample in item order, the same cap for every system): ours' concept maps
have 100 to 270 edges, its quizzes up to 34 questions.
"""
from __future__ import annotations

import json
import random

import study as st

CAP = 12
GOALS = json.loads((st.DATA / "knowledge" / "goals.json").read_text())
SONNET = st.OUT / "sonnet"

INSTRUCTIONS = """# Judging learning activities (blind)

Each file in `packets/` is one lecture of the NPTEL course "Foundation for Virtual and Augmented Reality Systems":
its title, goal and objectives, the titles of the earlier lectures, then units. A unit is one kind of activity; it
holds three or four sets (X, Y, Z, W) made for the same lecture by different systems, in no particular order. The
lecture's transcript (the lecturer's words, human-written subtitles, sentences numbered) is in
`transcripts/lec_<n>.txt`: read it before judging the lecture.

Judge every item of every set on its own (do not rank the sets). For each item answer:

- `correct` (true / false): what the item marks as right is right: the quiz option marked correct (and only it),
  the odd item and its reason, the order of the steps, the reference answer, the recap point or text, the recall
  answer, the concept-map edge as stated (from --label--> to). Judge by the transcript and sound subject knowledge.
- `grounded` ("yes" / "partly" / "no"): the item is taught in this lecture's transcript ("partly": some of it is,
  some is added from elsewhere). For a recall item (shown before the lecture, on a concept from an earlier
  lecture): "yes" when this lecture uses the concept and the named earlier lecture, by its title, is a plausible
  place where it was taught.
- `distractors` ("good" / "weak" / "poor" / null): quiz wrong options and odd-one-out items only (null otherwise).
  good: tempting to a learner who half understood, clearly wrong to one who understood, same form as the key;
  weak: some can be struck out without understanding, or the key stands out by its form; poor: absurd or off-topic
  options, or more than one defensible answer.
- `goals` ("yes" / "partly" / "no"): the item serves the lecture's goal or one of its objectives as stated in the
  packet (not trivia, not off the lecture's point).
- `cross_lecture` ("yes" / "no" / "wrong"): "yes" when the item correctly links this lecture to another lecture of
  the course (a concept taught earlier, a lecture named rightly), "no" when it makes no such link, "wrong" when it
  makes a link that is false (a wrong lecture, a concept the lecture does not use).
- `reason`: one short sentence, required whenever an answer is not the best one (false, "partly", "no", "weak",
  "poor", "wrong").

## Output

One JSON object per line, one line per item, in a file `judgments.jsonl` (write it next to this file):

{"unit": "U01", "item": "X3", "correct": true, "grounded": "yes", "distractors": null, "goals": "partly", "cross_lecture": "no", "reason": "..."}

- `unit`: the unit's ID as given ("U01"); `item`: the item's label as given ("X3").
- `correct`: true or false; `grounded`: "yes" | "partly" | "no"; `distractors`: "good" | "weak" | "poor" | null;
  `goals`: "yes" | "partly" | "no"; `cross_lecture`: "yes" | "no" | "wrong"; `reason`: a string ("" when nothing
  is wrong).
- Every item of every unit gets exactly one line. No other output in the file.
"""


def render(kind: str, it, part: str) -> list[str]:
    if kind == "quiz":
        return [it["question"]] + [f"   {'ABCD'[j]}. {o}" for j, o in enumerate(it["options"])] + \
            [f"   Marked correct: {'ABCD'[it['answer']]}", f"   Explanation: {it.get('explanation', '')}"]
    if kind == "recap":
        return [("Summary text: " if part == "text" else "Point: ") + it]
    if kind == "open_question":
        return [f"Question: {it['question']}", f"   Reference answer: {it['reference_answer']}"]
    if kind == "odd_one_out":
        return ["Items: " + " | ".join(it["options"]), f"   Marked odd: {it['options'][it['odd']]}",
                f"   Reason: {it['reason']}"]
    if kind == "put_in_order":
        return [f"Title: {it['title']}"] + [f"   {j}. {s}" for j, s in enumerate(it["steps"], 1)]
    if kind == "recall":
        src = str(it.get("from_lecture"))
        return [f"Prompt: {it.get('prompt', '')}", f"   Answer: {it.get('answer', '')}",
                f"   Taught in: lecture {src}" + (f" ({st.TITLES[src]})" if src in st.TITLES else " (no such lecture)")]
    raise ValueError(kind)


def set_items(system: str, k: str, kind: str) -> list[tuple[list[str], dict]]:
    out = []
    for a in st.activities(system, k):
        if a["kind"] != kind:
            continue
        d = a["data"]
        if kind == "concept_map":
            lab = {n.get("id"): n.get("label", "?") for n in d.get("nodes", [])}
            for i, e in enumerate(d.get("edges", [])):
                out.append(([f"{lab.get(e.get('from'), '?')} --{e.get('label', '')}--> {lab.get(e.get('to'), '?')}"],
                            {"activity": a["id"], "item": i, "part": "item"}))
            continue
        if kind == "recap":
            seq = [(p, "point") for p in d.get("points", [])] + ([(d["text"], "text")] if d.get("text") else [])
        else:
            seq = [(it, "item") for it in st.items_of(kind, d)]
        for i, (it, part) in enumerate(seq):
            try:
                out.append((render(kind, it, part), {"activity": a["id"], "item": i, "part": part}))
            except (KeyError, IndexError, TypeError):
                continue                     # malformed (counted by checks.py)
    return out


def main():
    (SONNET / "packets").mkdir(parents=True, exist_ok=True)
    (SONNET / "transcripts").mkdir(parents=True, exist_ok=True)
    (SONNET / "INSTRUCTIONS.md").write_text(INSTRUCTIONS)
    key, n = {"cap": CAP, "units": {}}, 0
    for k in st.sample():
        stem = st.lec.stem_of(k)
        (SONNET / "transcripts" / f"{stem}.txt").write_text(st.numbered(k) + "\n")
        lg = GOALS["lecture_goals"].get(f"{k}/G", {})
        objs = [o["goal"] for o in GOALS["objectives"].values() if o["lecture"] == k]
        lines = [f"# Lecture {k}: {st.TITLES[k]}", "", f"Transcript: transcripts/{stem}.txt", "",
                 f"Goal: {lg.get('goal', '(none)')}", "", "Objectives:"] + [f"- {o}" for o in objs] + \
                ["", "Earlier lectures: " + ("; ".join(f"{x}: {st.TITLES[x]}" for x in st.earlier(k)) or "(none)"), ""]
        for kind in st.KINDS:
            n += 1
            uid = f"U{n:02d}"
            systems = [s for s in st.SYSTEMS if kind in st.KINDS_OF[s]]
            random.Random(f"act-study:{uid}").shuffle(systems)
            ku = key["units"][uid] = {"lecture": k, "kind": kind, "sets": {}, "items": {}}
            lines += [f"## Unit {uid}: {kind.replace('_', ' ')}", ""]
            for letter, system in zip("XYZW", systems):
                ku["sets"][letter] = system
                its = set_items(system, k, kind)
                if len(its) > CAP:
                    keep = sorted(random.Random(f"act-study:{uid}:{system}").sample(range(len(its)), CAP))
                    its = [its[i] for i in keep]
                lines += [f"### Set {letter}", ""]
                if not its:
                    lines += ["(no items: this system made none)", ""]
                for j, (r, src) in enumerate(its, 1):
                    label = f"{letter}{j}"
                    ku["items"][label] = src
                    lines += [f"{label}. {r[0]}"] + r[1:] + [""]
        (SONNET / "packets" / f"{stem}.md").write_text("\n".join(lines))
    (st.OUT / "sonnet_key.json").write_text(json.dumps(key, indent=1))
    total = sum(len(u["items"]) for u in key["units"].values())
    print(f"packets: {n} units, {total} items -> {SONNET}; key -> {st.OUT / 'sonnet_key.json'}")


if __name__ == "__main__":
    main()
