"""CPU: joins generation, code checks, Gemma judges and (when present) the Sonnet judgments into tables per kind and
system, plus the list of what only the knowledge layer makes possible. Writes out/summary.md and out/summary.json.

    python3 summarize.py [--sonnet out/sonnet/judgments.jsonl]
"""
from __future__ import annotations

import argparse
import collections
import json

import study as st

SYS = st.SYSTEMS
NAME = {"ours": "ours (layer, shipped)", "ours_gemma": "ours on Gemma (layer)", "b1": "B1 plain", "b2": "B2 prompt-fair"}


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def table(head: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + \
        ["| " + " | ".join(str(x) for x in r) + " |" for r in rows] + [""]


def jl(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def generation() -> tuple[list[str], dict]:
    rows, js = [], {}
    for s in ("b1", "b2"):
        for kind in st.KINDS:
            c = collections.Counter()
            for k in st.sample():
                u = st.gen_info(s, k).get(kind)
                c[u["status"] if u else "missing"] += 1
                c["dropped"] += len((u or {}).get("dropped") or [])
                c["retried"] += bool((u or {}).get("retry"))
            js[f"{s}/{kind}"] = dict(c)
            rows.append([NAME[s], kind, c["ok"], c["unresolved"], c["no_answer"], c["missing"], c["retried"], c["dropped"]])
    return ["## Generation (baselines; units = lectures)", ""] + table(
        ["system", "kind", "ok", "unresolved", "no answer", "not run", "retried", "items dropped (hard checks)"],
        rows), js


def code_checks() -> tuple[list[str], dict]:
    rows = jl(st.OUT / "checks" / "items.jsonl")
    g = collections.defaultdict(list)
    for r in rows:
        g[(r["kind"], r["system"])].append(r)
    out, js = ["## Code checks (every item; traceable = >= 60% of the key's content words in one 3-sentence window "
               "of the transcript)", ""], {}
    t = []
    for kind in st.KINDS:
        for s in SYS:
            rs = g.get((kind, s), [])
            n = len(rs)
            ov = [r["overlap"] for r in rs if r.get("overlap") is not None]
            extra = ""
            if kind == "quiz" and rs:
                pos = collections.Counter(r.get("answer_pos") for r in rs if "answer_pos" in r)
                extra = (f"key longest {pct(sum(r.get('correct_longest', 0) for r in rs), n)}; key position "
                         f"A/B/C/D {'/'.join(str(pos[i]) for i in range(4))}; all/none-of-the-above "
                         f"{sum(r.get('above', 0) for r in rs)}")
            elif kind == "concept_map" and rs:
                extra = (f"ends found together {pct(sum(r['ends_together'] for r in rs), n)}; typed relation (R..) "
                         f"{pct(sum(r['typed_relation'] for r in rs), n)}")
            elif kind == "recall" and rs:
                extra = (f"names an earlier lecture {pct(sum(r['earlier_lecture'] for r in rs), n)}; concept found in "
                         f"that lecture {pct(sum(r['concept_in_source'] for r in rs), n)}")
            d = {"items": n, "schema_ok": sum(r["schema_ok"] for r in rs), "duplicate": sum(r["duplicate"] for r in rs),
                 "cited": sum(r["cited"] for r in rs), "traceable": sum(r["traceable"] for r in rs),
                 "mean_overlap": round(sum(ov) / len(ov), 3) if ov else None,
                 "source_talk": sum(r.get("source_talk", False) for r in rs)}
            js[f"{kind}/{s}"] = {**d, "extra": extra}
            t.append([kind, NAME[s], n, pct(d["schema_ok"], n), pct(d["duplicate"], n), pct(d["cited"], n),
                      pct(d["traceable"], n), d["mean_overlap"] if d["mean_overlap"] is not None else "-",
                      d["source_talk"], extra])
    return out + table(["kind", "system", "items", "schema ok", "duplicate", "cites sources", "traceable",
                        "mean overlap", "source talk", "kind checks"], t), js


def gemma() -> tuple[list[str], dict]:
    recs = jl(st.OUT / "judge" / "gemma.jsonl")
    g = collections.defaultdict(lambda: {"n": 0, "pass": 0, "missing": 0, "units_not_ok": 0,
                                         "failed": collections.Counter()})
    for r in recs:
        x = g[(r["kind"], r["system"])]
        x["units_not_ok"] += r["round"].get("status") != "ok"
        for v in r["round"].get("verdicts", []):
            if v.get("missing"):
                x["missing"] += 1
                continue
            x["n"] += 1
            x["pass"] += bool(v.get("pass"))
            x["failed"].update(v.get("failed") or [])
    t, js = [], {}
    for kind in st.JUDGED:
        for s in SYS:
            x = g.get((kind, s))
            if not x:
                t.append([kind, NAME[s], 0, "-", "-", "-", ""])
                continue
            top = ", ".join(f"{c} {m}" for c, m in x["failed"].most_common(4))
            js[f"{kind}/{s}"] = {**{k: v for k, v in x.items() if k != "failed"}, "failed": dict(x["failed"])}
            t.append([kind, NAME[s], x["n"], pct(x["pass"], x["n"]), x["missing"], x["units_not_ok"], top])
    return ["## Pipeline judges (Gemma 4 12B, prompts/activity_judge_<kind>.txt; recap items: points and the text)", ""] \
        + table(["kind", "system", "items judged", "pass", "no verdict", "units not ok", "most failed criteria"], t), js


def sonnet(path) -> tuple[list[str], dict]:
    key = json.loads((st.OUT / "sonnet_key.json").read_text()) if (st.OUT / "sonnet_key.json").exists() else None
    recs = jl(path)
    if not key or not recs:
        return ["## Sonnet judge", "", "(no judgments yet: " + str(path) + ")", ""], {}
    g = collections.defaultdict(collections.Counter)
    expected = {(u, i) for u, x in key["units"].items() for i in x["items"]}
    seen = set()
    for r in recs:
        u = key["units"].get(r.get("unit"))
        if not u or r.get("item") not in u["items"]:
            continue
        seen.add((r["unit"], r["item"]))
        c = g[(u["kind"], u["sets"][r["item"][0]])]
        c["n"] += 1
        c["correct"] += r.get("correct") is True
        c["grounded_yes"] += r.get("grounded") == "yes"
        c["grounded_no"] += r.get("grounded") == "no"
        if r.get("distractors") is not None:
            c["d_n"] += 1
            c["d_good"] += r["distractors"] == "good"
        c["goals_yes"] += r.get("goals") == "yes"
        c["link_yes"] += r.get("cross_lecture") == "yes"
        c["link_wrong"] += r.get("cross_lecture") == "wrong"
    t, js = [], {}
    for kind in st.KINDS:
        for s in SYS:
            c = g.get((kind, s), collections.Counter())
            js[f"{kind}/{s}"] = dict(c)
            n = c["n"]
            t.append([kind, NAME[s], n, pct(c["correct"], n), pct(c["grounded_yes"], n), pct(c["grounded_no"], n),
                      pct(c["d_good"], c["d_n"]), pct(c["goals_yes"], n), pct(c["link_yes"], n), pct(c["link_wrong"], n)])
    miss = len(expected - seen)
    return ["## Sonnet judge (blind; at most " + str(key["cap"]) + " items per set)", "",
            f"Judged {len(seen)} of {len(expected)} items" + (f" ({miss} missing)" if miss else "") + ".", ""] + \
        table(["kind", "system", "items", "correct", "grounded", "not grounded", "distractors good", "serves goals",
               "links lectures", "wrong link"], t), js


def layer_only() -> tuple[list[str], dict]:
    """What ours carries that needs the knowledge layer, counted over the whole course and the sample."""
    keys = [k for k in st.KEYS if (st.DATA / "activities" / f"{st.lec.stem_of(k)}.json").exists()]
    sample = set(st.sample())
    facts = json.loads((st.DATA / "knowledge" / "facts.json").read_text())
    c = {"all": collections.Counter(), "sample": collections.Counter()}
    for k in keys:
        for a in st.ours_file(k)["activities"]:
            for scope in ("all", "sample") if k in sample else ("all",):
                x, kind, d = c[scope], a["kind"], a["data"]
                x[f"act:{kind}"] += 1
                x["acts_with_facts"] += bool(a.get("facts"))
                x["acts_with_concepts"] += bool(a.get("concepts"))
                x["acts"] += 1
                if kind == "recall":
                    x["recall_items"] += len(d["items"])
                elif kind in ("concept_map", "complete_map"):
                    x[f"{kind}_edges"] += len(d["edges"])
                    x[f"{kind}_typed"] += sum(str(e.get("relation", "")).startswith("R") for e in d["edges"])
                    x["blanks"] += len(d.get("blanks", []))
                elif kind == "match_pairs":
                    x["pairs"] += len(d["pairs"])
                elif kind == "crossword":
                    x["entries"] += len(d["entries"])
                elif kind == "open_question":
                    for q in d["questions"]:
                        x["oq"] += 1
                        x["oq_earlier"] += any(facts.get(f, {}).get("lecture") not in (None, k) for f in q["key_facts"])
                        x["oq_concepts"] += bool(q.get("concepts"))
                if kind in ("quiz", "odd_one_out", "put_in_order"):
                    for it in st.items_of(kind, d):
                        x["items_with_fact_ids"] += bool(it.get("facts"))
                        x["fact_items"] += 1
    cards = len(json.loads((st.DATA / "activities" / "course.json").read_text())["spaced_review"]["cards"])
    A, S = c["all"], c["sample"]

    def both(f, g=None):
        return f"{A[f]} (sample {S[f]})" if g is None else f"{A[f]} / {A[g]} (sample {S[f]} / {S[g]})"
    lines = ["## Only possible with the knowledge layer (counts from ours: whole course of "
             f"{len(keys)} lectures; the sample in brackets)", "",
             f"- recall, before each lecture (lecture graph: which earlier lectures it needs; concepts; their 4a "
             f"definitions as answers): {both('act:recall')} activities, {both('recall_items')} items. The "
             f"baselines attempted it from the titles of the earlier lectures (see the checks and Sonnet tables).",
             f"- concept_map with typed relationships (concepts C.., relationships R.. with their facts): "
             f"{both('act:concept_map')} maps, {both('concept_map_typed', 'concept_map_edges')} edges typed. The "
             f"baselines drew maps from the transcript, with no relationship IDs or facts.",
             f"- complete_map (the map with blanks; options from the lecture's other labels and concepts): "
             f"{both('act:complete_map')} activities, {both('blanks')} blanks. Not attempted by the baselines.",
             f"- match_pairs (glossary: concept and its definition): {both('act:match_pairs')} activities, "
             f"{both('pairs')} pairs. Not attempted.",
             f"- crossword (concepts with definitions; clues judged against the definition): "
             f"{both('act:crossword')} grids, {both('entries')} entries. Not attempted.",
             f"- spaced_review cards (one per defined concept, with every lecture that uses it): {cards} cards "
             f"(course-wide).",
             f"- fact IDs (time links into the video; the judge checks each item against its cited facts): "
             f"{both('acts_with_facts', 'acts')} activities carry facts; "
             f"{both('items_with_fact_ids', 'fact_items')} quiz / odd-one-out / put-in-order items cite their own "
             f"facts. B2 cites transcript sentences; B1 cites nothing.",
             f"- concepts on activities (glossary links in the viewer): {both('acts_with_concepts', 'acts')}.",
             f"- open questions built on an earlier lecture's facts (lecture graph): "
             f"{both('oq_earlier', 'oq')} questions; with concept links {both('oq_concepts', 'oq')}.", ""]
    return lines, {"all": dict(A), "sample": dict(S), "spaced_review_cards": cards}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sonnet", default=str(st.OUT / "sonnet" / "judgments.jsonl"))
    a = ap.parse_args()
    from pathlib import Path
    head = ["# Activities study: ours vs baselines", "",
            f"Sample (lectures): {', '.join(st.sample())}. Systems: {', '.join(NAME.values())}. Model of the "
            f"baselines and of the Gemma judges: {st.LLM_CFG.name}. Ours: the existing activities "
            "(pipeline/output/nptel_vr/activities).", ""]
    parts, js = [], {"sample": st.sample()}
    for name, f in (("generation", generation), ("code_checks", code_checks), ("gemma_judge", gemma),
                    ("sonnet", lambda: sonnet(Path(a.sonnet))), ("layer_only", layer_only)):
        lines, d = f()
        parts += lines
        js[name] = d
    (st.OUT / "summary.md").write_text("\n".join(head + parts))
    (st.OUT / "summary.json").write_text(json.dumps(js, indent=1))
    print(f"summary -> {st.OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
