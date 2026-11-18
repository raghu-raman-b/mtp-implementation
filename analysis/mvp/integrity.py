"""Independent, read-only integrity check of the MVP activities against the knowledge layer (analysis/mvp)."""
import json, glob, re, collections, sys
from pathlib import Path
R = Path(__file__).resolve().parents[2] / "pipeline/output/nptel_vr"
K = R / "knowledge"
facts = json.load(open(K / "facts.json")); concepts = json.load(open(K / "concepts.json"))
rels = json.load(open(K / "relations.json"))
lectures = {p.stem.split("_")[1]: json.load(open(p)) for p in (K / "lectures").glob("lec_*.json")}
P = collections.defaultdict(list); stats = collections.Counter(); pos = collections.Counter()
longest = 0; nq = 0
def bad(kind, msg): P[kind].append(msg)
for p in sorted((R / "activities").glob("lec_*.json"), key=lambda p: int(p.stem.split("_")[1])):
    d = json.load(open(p)); L = d["lecture"]
    segs = lectures[L]["segments"]
    for a in d["activities"]:
        aid, kind, data = a["id"], a["kind"], a["data"]
        stats[kind] += 1
        for f in a["facts"]:
            if f not in facts: bad("missing_fact", f"{aid} {f}")
        for c in a["concepts"]:
            if c not in concepts: bad("missing_concept", f"{aid} {c}")
        if not a["facts"] and kind != "recall": bad("no_facts", aid)
        if a["scope"] == "segment" and a["segment"] not in segs: bad("bad_segment", aid)
        # facts of segment activities in that segment
        if a["scope"] == "segment":
            out = [f for f in a["facts"] if facts.get(f, {}).get("segment") != a["segment"]]
            if out: stats["seg_act_cites_other_segment"] += 1
        af = set(a["facts"])
        def sub(items, where):
            for i, it in enumerate(items):
                for f in it.get("facts", []) + it.get("key_facts", []):
                    if f not in af: bad("item_fact_not_in_activity", f"{aid} {where}#{i} {f}")
                    if f not in facts: bad("missing_fact", f"{aid} {where}#{i} {f}")
                for c in it.get("concepts", []) + ([it["concept"]] if it.get("concept") else []):
                    if c not in concepts: bad("missing_concept", f"{aid} {where}#{i} {c}")
        if kind == "quiz":
            sub(data["questions"], "q")
            for i, q in enumerate(data["questions"]):
                nq += 1; o = q["options"]
                if len(o) != 4 or len(set(o)) != 4 or not 0 <= q["answer"] < 4: bad("quiz_shape", f"{aid} q{i}")
                pos[q["answer"]] += 1
                lens = [len(x) for x in o]
                if lens[q["answer"]] == max(lens) and lens.count(max(lens)) == 1: longest += 1
        elif kind == "open_question":
            sub(data["questions"], "q")
            for i, q in enumerate(data["questions"]):
                if len(q["key_facts"]) < 2: bad("open_lt2_keyfacts", f"{aid} q{i}")
        elif kind in ("odd_one_out", "put_in_order", "match_pairs"):
            sub(data.get("items", data.get("pairs", [])), "i")
        elif kind == "recall":
            sub(data["items"], "i")
        elif kind in ("concept_map", "complete_map"):
            ids = {n["id"] for n in data["nodes"]}
            for n in ids:
                if n not in concepts: bad("missing_concept", f"{aid} node {n}")
            for i, e in enumerate(data["edges"]):
                if e["from"] not in ids or e["to"] not in ids: bad("edge_end_not_node", f"{aid} e{i}")
                r = rels.get(e["relation"])
                if not r: bad("missing_relation", f"{aid} {e['relation']}")
                elif (r["subject"], r["object"]) != (e["from"], e["to"]): bad("edge_relation_mismatch", f"{aid} e{i}")
            sub(data["edges"], "e")
            if kind == "complete_map":
                for b in data["blanks"]:
                    e = data["edges"][b["edge"]]
                    truth = e["label"] if b["hide"] == "label" else next(n["label"] for n in data["nodes"] if n["id"] == e[b["hide"]])
                    if b["answer"] != truth: bad("blank_answer_wrong", f"{aid} {b}")
                    if b["answer"] not in b["options"]: bad("blank_answer_not_option", f"{aid}")
                    if b["hide"] != "label":
                        other = sum(1 for e2 in data["edges"] if e[b['hide']] in (e2["from"], e2["to"]))
                        if other > 1: bad("blank_concept_visible_elsewhere", f"{aid}")
        elif kind == "crossword":
            sub(data["entries"], "e")
            grid = {}
            for e in data["entries"]:
                if not re.fullmatch(r"[A-Z]+", e["answer"]): bad("cw_answer", f"{aid} {e['answer']}")
                for j, ch in enumerate(e["answer"]):
                    rc = (e["row"] + (j if e["direction"] == "down" else 0), e["col"] + (j if e["direction"] == "across" else 0))
                    if grid.get(rc, ch) != ch: bad("cw_clash", f"{aid} {rc}")
                    grid[rc] = ch
                if "___" in e["clue"]: stats["cw_clue_masked"] += 1
                words = re.findall(r"[a-z]+", e["clue"].lower())
                name = concepts[e["concept"]]["name"].lower()
                if any(w in words for w in re.findall(r"[a-z]{4,}", name)): bad("cw_clue_contains_answer_word", f"{aid} {e['answer']}: {e['clue']}")
        elif kind == "recap":
            if not data["text"].strip() or not data["points"]: bad("recap_empty", aid)
print("activities", sum(stats[k] for k in stats if not k.startswith(("seg_", "cw_"))), dict(stats))
print("quiz questions", nq, "answer positions", dict(pos), f"correct is the unique longest: {longest} ({longest/nq:.0%})")
print("problems:", {k: len(v) for k, v in P.items()} or "none")
for k, v in P.items():
    for m in v[:8]: print(" ", k, m)
