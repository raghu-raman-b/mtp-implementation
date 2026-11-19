"""CPU: code checks of every item of ours, B1 and B2 in the sample. Writes out/checks/items.jsonl (one line per item).

    python3 checks.py

Per item:
  schema_ok    the item has the contract's fields and types (quiz/odd: 4 distinct options and an index in range;
               put_in_order: 3 to 8 steps; recall: a lecture key; concept_map: both ends are nodes of the map)
  duplicate    it repeats an earlier item of the same system, lecture and kind (content-word Jaccard >= 0.6 of the
               question / point / options / steps; concept_map: the same from-label-to; recall: the same concept)
  cited        it names its sources: ours / ours_gemma fact IDs that exist in knowledge/facts.json; B2 transcript sentences;
               B1 never; ours' recall: a concept of the layer (the activity carries its definition facts)
  overlap      share of the content words of its key text (quiz: the correct option; recap: the point or text;
               open_question: the reference answer; odd_one_out: the reason; put_in_order: the steps;
               concept_map: "from label to"; recall: the answer) found in the best window of 3 consecutive
               sentences of the lecture transcript (recall: of the transcript of the lecture it names as its source);
               traceable: overlap >= 0.6 (study.TRACE_MIN); the rule of baseline-tests/citations.py's auto_overlap
  kind extras  quiz: answer position, correct option strictly the longest, "all/none of the above", source talk
               (s5's patterns); concept_map: both end labels found within one 3-sentence window; recall: names an
               earlier lecture, the concept's words found in that lecture's transcript
"""
from __future__ import annotations

import json

import study as st
from study import s5

FACTS = json.loads((st.DATA / "knowledge" / "facts.json").read_text())
CARDS = json.loads((st.DATA / "knowledge" / "concepts.json").read_text())
MAIN = {"quiz": lambda q: q.get("question", ""), "open_question": lambda q: q.get("question", ""),
        "odd_one_out": lambda it: " ".join(it.get("options", [])), "put_in_order": lambda it: " ".join(it.get("steps", [])),
        "recap": lambda p: p}
KEY = {"quiz": lambda q: q["options"][q["answer"]], "open_question": lambda q: q.get("reference_answer", ""),
       "odd_one_out": lambda it: it.get("reason", ""), "put_in_order": lambda it: " ".join(it.get("steps", [])),
       "recap": lambda p: p, "recall": lambda it: it.get("answer", "")}


def strs(x, n=None):
    return isinstance(x, list) and all(isinstance(s, str) and s.strip() for s in x) and (n is None or len(x) == n)


def schema_ok(kind: str, it, nodes: set) -> bool:
    if kind == "quiz":
        return isinstance(it, dict) and isinstance(it.get("question"), str) and strs(it.get("options"), 4) and \
            len({s5.norm(o) for o in it["options"]}) == 4 and it.get("answer") in range(4) and \
            isinstance(it.get("explanation"), str)
    if kind == "recap":
        return isinstance(it, str) and bool(it.strip())
    if kind == "open_question":
        return isinstance(it, dict) and bool(s5.txt(it.get("question"))) and bool(s5.txt(it.get("reference_answer")))
    if kind == "odd_one_out":
        return isinstance(it, dict) and strs(it.get("options"), 4) and len({s5.norm(o) for o in it["options"]}) == 4 \
            and it.get("odd") in range(4) and bool(s5.txt(it.get("reason")))
    if kind == "put_in_order":
        return isinstance(it, dict) and bool(s5.txt(it.get("title"))) and strs(it.get("steps")) and \
            3 <= len(it["steps"]) <= 8
    if kind == "recall":
        return isinstance(it, dict) and all(s5.txt(it.get(f)) for f in ("prompt", "answer")) and \
            str(it.get("from_lecture")) in st.KEYS
    if kind == "concept_map":
        return isinstance(it, dict) and it.get("from") in nodes and it.get("to") in nodes and bool(s5.txt(it.get("label")))
    return False


def cited(system: str, kind: str, it) -> bool:
    fs = (it.get("key_facts") if kind == "open_question" else it.get("facts")) if isinstance(it, dict) else None
    if system in st.LAYERED:
        if kind == "recall":                 # a concept card and its definition facts (on the activity)
            return it.get("concept") in CARDS
        return bool(fs) and all(f in FACTS for f in fs)
    return bool(fs)


def found_together(a: str, b: str, k: str) -> bool:
    wa, wb = st.words(a), st.words(b)
    sw = [st.words(t) for _, t in st.sentences(k)]
    for i in range(len(sw)):
        w = set().union(*sw[i:i + 3])
        if wa and wb and wa <= w and wb <= w:
            return True
    return False


def in_lecture(term: str, k: str) -> bool:
    tw = st.words(term)
    return bool(tw) and any(tw <= st.words(t) for _, t in st.sentences(k))


def items(system: str, k: str):
    """(kind, activity, item index, item, part) for every item; recap texts are items with part "text"."""
    for a in st.activities(system, k):
        kind, d = a["kind"], a["data"]
        if kind == "recap":
            for i, p in enumerate(d.get("points", [])):
                yield kind, a, i, p, "point"
            if d.get("text"):
                yield kind, a, len(d.get("points", [])), d["text"], "text"
        else:
            for i, it in enumerate(st.items_of(kind, d)):
                yield kind, a, i, it, "item"


def check(system: str, k: str) -> list[dict]:
    out, seen = [], {}
    for kind, a, i, it, part in items(system, k):
        d = a["data"]
        nodes = {n.get("id"): n.get("label", "") for n in d.get("nodes", [])} if kind == "concept_map" else {}
        r = {"system": system, "lecture": k, "kind": kind, "activity": a["id"], "item": i, "part": part,
             "schema_ok": schema_ok(kind, it, set(nodes))}
        if kind == "recap":
            r["cited"] = bool(a.get("facts")) if system != "b1" else False   # recap: the activity's facts
        else:
            r["cited"] = cited(system, kind, it)
        prev = seen.setdefault(kind, [])
        if kind == "concept_map":
            sig = (s5.norm(nodes.get(it.get("from"), "")), s5.norm(it.get("label", "")), s5.norm(nodes.get(it.get("to"), "")))
            r["duplicate"] = sig in prev
            prev.append(sig)
            fl, tl = nodes.get(it.get("from"), ""), nodes.get(it.get("to"), "")
            r["overlap"] = st.overlap(f"{fl} {it.get('label', '')} {tl}", k)[0]
            r["ends_together"] = found_together(fl, tl, k)
            r["typed_relation"] = str(it.get("relation", "")).startswith("R")
        elif kind == "recall":
            sig = s5.norm(it.get("concept") or it.get("prompt", ""))
            r["duplicate"] = sig in prev
            prev.append(sig)
            src = str(it.get("from_lecture"))
            ok = src in st.KEYS and st.lec.order(src) < st.lec.order(k)
            r["earlier_lecture"] = ok
            name = s5.txt(it.get("concept")) or s5.txt(it.get("prompt")).removeprefix("What is ").rstrip("?")
            if system in st.LAYERED:
                name = CARDS.get(it.get("concept"), {}).get("name", name)
            r["concept_in_source"] = ok and in_lecture(name, src)
            r["overlap"] = st.overlap(it.get("answer", ""), src)[0] if ok else 0.0
        else:
            w = s5.content_tokens(MAIN[kind](it)) if (kind == "recap" or r["schema_ok"]) else []
            r["duplicate"] = bool(w) and any(s5.jaccard(w, p) >= 0.6 for p in prev)
            prev.append(w)
            r["overlap"] = st.overlap(KEY[kind](it), k)[0] if (kind == "recap" or r["schema_ok"]) else None
        if kind == "quiz" and r["schema_ok"]:
            opts, ans = it["options"], it["answer"]
            r["answer_pos"] = ans
            r["correct_longest"] = all(len(opts[ans]) > len(o) for j, o in enumerate(opts) if j != ans)
            r["above"] = any(s5.ABOVE.search(o) for o in opts)
        if isinstance(it, (dict, str)):
            text = it if isinstance(it, str) else " ".join(str(v) for v in it.values() if isinstance(v, str))
            r["source_talk"] = bool(s5.source_talk("item", text))
        r["traceable"] = r.get("overlap") is not None and r["overlap"] >= st.TRACE_MIN
        out.append(r)
    return out


def main():
    rows = [r for system in st.SYSTEMS for k in st.sample() for r in check(system, k)]
    p = st.OUT / "checks" / "items.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"checks: {len(rows)} items -> {p}")


if __name__ == "__main__":
    main()
