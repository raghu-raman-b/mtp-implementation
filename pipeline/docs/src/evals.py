"""HTML for the Evaluation part, computed from the evaluation sets and runs in the repository."""
import csv
import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

E = html.escape


def table(head, rows, num=()):
    h = "".join(f'<th{" class=n" if i in num else ""}>{E(str(x))}</th>' for i, x in enumerate(head))
    b = "".join("<tr>" + "".join(f'<td{" class=n" if i in num else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>"
                for r in rows)
    return f'<div class="tablewrap"><table><tr>{h}</tr>{b}</table></div>'


def det(summary, meta, inner, open_=False):
    return (f'<details{" open" if open_ else ""}><summary>{summary} <span class="meta">{E(meta)}</span></summary>'
            f'{inner}</details>')


def build(WT, HERE):
    A = WT / "analysis"
    O = WT / "pipeline/output/nptel_vr"
    X = {}

    def J(p):
        return json.loads(Path(p).read_text())

    # ---------------- segmentation: human annotation of lecture 1, run-to-run seeds
    ann = J(WT / "lec1__P01__both.json")
    b = ann["boundaries"]

    def fmt(t):
        return f"{int(t // 60)}:{int(t % 60):02d}"
    X["seg_human"] = det(
        "Human annotation of lecture 1 (participant P01)", "lec1__P01__both.json",
        f"<p>Video {fmt(ann['video']['duration'])} long. Coarse boundaries ({len(b['coarse'])}, the reference of the "
        f"comparison): " + ", ".join(fmt(t) for t in b["coarse"]) + f".</p><p>Fine boundaries ({len(b['fine'])}): "
        + ", ".join(fmt(t) for t in b["fine"]) + ".</p>")
    rows = {}
    for r in csv.DictReader(open(A / "segmentation/data/run_to_run_lectures.csv")):
        rows.setdefault(r["lecture"], {})[r["stage"]] = r
    trs = []
    for lec, d in sorted(rows.items(), key=lambda x: int(x[0])):
        a, v = d.get("1a"), d.get("1b")
        trs.append([lec, a["seeds"], f'{a["segments_min"]}–{a["segments_max"]}', f'{v["segments_min"]}–{v["segments_max"]}',
                    a["boundary_f1_mean"], f'<b>{v["boundary_f1_mean"]}</b>', a["window_diff_mean"], v["window_diff_mean"],
                    f'{a["longest_min"]} → {v["longest_min"]}'])
    X["seg_seeds"] = table(["Lecture", "Seeds", "Segments 1a", "Segments 1b", "F1 1a", "F1 1b", "WD 1a", "WD 1b",
                            "Longest (min)"], trs, num=(1, 4, 5, 6, 7))

    # ---------------- fact judge sets
    gold = J(A / "fact_judge/gold.json")["facts"]
    fm = {}
    for f in (O / "stage_2a_fact_extraction/fact_maps").glob("lec_*.json"):
        fm.update(J(f))
    names = {1: "Significant", 2: "Whole", 3: "Established", 4: "Grounded", 5: "Self-contained", 6: "Terms in full",
             7: "On the subject", 8: "Faithful"}
    trs = []
    for fid, g in gold.items():
        lab = '<span style="color:var(--ok)">pass</span>' if g["pass"] else '<b style="color:var(--bad)">fail</b>'
        if g.get("borderline"):
            lab += " · borderline"
        fails = ", ".join(names.get(p, str(p)) for p in g.get("fails", []))
        trs.append([f"<code>{fid}</code>", E(fm.get(fid, {}).get("text", "")), lab, E(fails), E(g.get("note", ""))])
    npass = sum(g["pass"] for g in gold.values())
    X["gold_facts"] = det(f"Gold labels for the {len(gold)} facts of lectures 1, 4 and 16 ({npass} pass, {len(gold) - npass} fail)",
                          "analysis/fact_judge/gold.json", table(["Fact", "Text (stage 2a)", "Label", "Fails", "Note"], trs))
    for key, path, title in (("seeded", "seeded.json", "Seeded errors: facts made wrong on purpose"),
                             ("subtle", "seeded_subtle.json", "Subtle seeded errors (review 1, change 9)")):
        d = J(A / "fact_judge" / path)["errors"]
        trs = []
        for e in d:
            txt = E(" / ".join(f["text"] for f in e.get("facts", [])))
            if e.get("changed"):
                txt += f'<br><span class="muted small">{E(e["changed"])}</span>'
            trs.append([e["id"], f'<code>{e["segment"]}</code>', E(e["kind"]),
                        E(", ".join(names.get(p, str(p)) for p in e.get("breaks", []))), txt])
        X[key] = det(f"{title} ({len(d)})", f"analysis/fact_judge/{path}",
                     table(["ID", "Segment", "Kind", "Breaks", "The wrong fact"], trs))
    gr = J(A / "fact_judge/gold_rewrites.json")["facts"]
    trs = [[f"<code>{k}</code>", E(v.get("text", "")), ("pass" if v.get("pass") else "<b>fail</b>"), E(v.get("note", ""))]
           for k, v in gr.items()]
    X["gold_rewrites"] = det(f"Gold for the {len(gr)} rewritten facts", "analysis/fact_judge/gold_rewrites.json",
                             table(["Rewrite of", "Text", "Label", "Note"], trs))
    ms = J(A / "fact_judge/missed.json")
    trs = [[f'<code>{m["segment"]}</code>', E(", ".join(m["sentences"])), E(m["weight"]), E(m.get("state", "")), E(m["point"])]
           for m in ms["missed"]]
    X["missed"] = det(f"Points 2a missed ({len(ms['missed'])}, after reading {len(ms['segments_read'])} segments)",
                      "analysis/fact_judge/missed.json", table(["Segment", "Sentences", "Weight", "State", "The point"], trs))

    # ---------------- activities: judge criteria by kind, code flags, trial
    t = J(O / "activities/checks.json")["totals"]
    crit = defaultdict(dict)
    for k, n in t["judge"]["failed"].items():
        kind, c = k.split(".")
        crit[kind][c] = n
    trs = []
    for kind in ("quiz", "recap", "open_question", "odd_one_out", "put_in_order", "crossword"):
        cs = sorted(crit[kind].items(), key=lambda x: -x[1])
        trs.append([kind.replace("_", " "), ", ".join(f"{c} <b>{n}</b>" for c, n in cs)])
    X["judge_crit"] = table(["Kind", "Criteria failed at the first judgement (number of items)"], trs)
    trs = [[k.split(".")[0].replace("_", " "), f"<code>{k.split('.')[1]}</code>", n]
           for k, n in sorted(t["flags"].items()) if "judge_failed" not in k]
    X["code_flags"] = table(["Kind", "Report-only flag", "Items"], trs, num=(2,))
    tr = J(A / "activities/trial_v3_lectures_1_4_16/checks.json")
    tj = tr["totals"]["judge"]
    X["trial"] = ("<p>Trial on lectures 1, 4 and 16 before the full run (<code>analysis/activities/trial_v3_lectures_1_4_16/</code>): "
                  f"{tr['run']['calls']} writer and {tr['run']['judge_calls']} judge calls in {tr['run']['seconds']:.0f} s; "
                  f"the judge failed {tj['failed_items']} of {tj['items']} items: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(tj['failed'].items(), key=lambda x: -x[1])) + ".</p>")

    # ---------------- QA bench: every question, per variant
    variants = [("before", "bench_before.jsonl", "local, old layer, before the speed fixes"),
                ("after", "bench_after.jsonl", "local, old layer, round-0 thinking + early exit"),
                ("shipped", "bench_think_newlayer.jsonl", "local, rebuilt layer, shipped"),
                ("no think", "bench_nothink.jsonl", "local, thinking off everywhere (not shipped)"),
                ("vLLM", "bench_vllm_shipped.jsonl", "vLLM on the RTX PRO 6000, shipped"),
                ("vLLM fast", "bench_vllm_fast.jsonl", "vLLM, thinking off + forced tool call (not shipped)")]
    data = {}
    for name, f, _ in variants:
        for line in (A / "qa" / f).read_text().splitlines():
            r = json.loads(line)
            data.setdefault(r["id"], {"q": r["question"], "kind": r["kind"]}).setdefault(name, []).append(r)
    trs = []
    for qid in sorted(data):
        d = data[qid]
        row = [qid, E(d["kind"]), E(d["q"])]
        for name, _, _ in variants:
            rs = d.get(name, [])
            if not rs:
                row.append("—")
                continue
            secs = " / ".join(f"{r['seconds']:.1f}" for r in rs)
            cov = "".join("✓" if r.get("covered") else "✗" for r in rs)
            notool = any(not r.get("steps") for r in rs)
            row.append(f"{secs}<br><span class='small muted'>covered {cov}{' · no tool call' if notool else ''}</span>")
        trs.append(row)
    med = []
    for name, f, _ in variants:
        s = [json.loads(line)["seconds"] for line in (A / "qa" / f).read_text().splitlines()]
        med.append(f"{statistics.median(s):.1f} (n {len(s)})")
    trs.append(["", "", "<b>median over the answers</b>"] + [f"<b>{m}</b>" for m in med])
    X["bench"] = (table(["ID", "Kind", "Question"] + [v[0] for v in variants], trs)
                  + "<p class='small muted'>Seconds per run (two runs where two were made); “covered” is the answer's COVERED "
                  "line (✓ yes or partly). Variants: " + "; ".join(f"<b>{E(n)}</b>: {E(d)}" for n, _, d in variants)
                  + ". Files: <code>analysis/qa/bench_*.jsonl</code>; the questions are in <code>analysis/qa/bench.py</code>. "
                  "Grounding was checked by reading every answer (<code>analysis/qa/STATE.md</code>): no wrong citation was seen "
                  "in the shipped variants.</p>")

    cal = J(A / "qa/calibration.json")
    trs = [[E(r["label"]), E(r["kind"]), E(r["q"]), f"{r['score']:.3f}", f"<code>{E(r['top_fact'])}</code>"]
           for r in sorted(cal["rows"], key=lambda r: -r["score"])]
    X["calib"] = det("Calibration queries (80: 38 in course, 3 partly, 39 out), by score",
                     "analysis/qa/calibration_queries.json, calibration.json",
                     table(["Label", "Kind", "Query", "Best score", "Top fact"], trs, num=(3,)))

    mvp = [json.loads(line) for line in (A / "mvp/qa_run/results.jsonl").read_text().splitlines()]
    trs = [[r["id"], E(r["kind"]), E(r["question"]), f"{r['seconds']}", "✓" if r.get("covered") else "✗",
            E(", ".join(r.get("tools", [])))] for r in mvp]
    X["mvpqa"] = det(f"MVP test questions ({len(mvp)}, 2026-11-13, old layer, GPU shared with a running job)",
                     "analysis/mvp/qa_run/results.jsonl", table(["ID", "Kind", "Question", "s", "Covered", "Tools"], trs, num=(3,)))

    qs = J(HERE / "qa_questions.json")
    trs = [[q["id"], E(q["kind"]), E(q["question"]), "yes" if q["covered"] else "<b>no</b>", E(q.get("reference_answer", "")),
            E(", ".join(str(x) for x in q.get("lectures", [])))] for q in qs["questions"]]
    cnt = Counter(q["kind"] for q in qs["questions"])
    X["qset"] = det(f"Block 6 question set, first draft ({len(qs['questions'])} questions: "
                    + ", ".join(f"{k} {v}" for k, v in cnt.items()) + ")",
                    "branch fable-gold-sets, analysis/qa/questions.json (not merged; not yet checked)",
                    table(["ID", "Kind", "Question", "Covered", "Reference answer", "Lectures"], trs))
    return X
