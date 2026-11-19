"""HTML for the baseline comparison ({{BASE:key}} in the body files), computed from the study's own files.

The files in baselines/ are copies from baseline-tests/ at commit 0d7f665 (branch worktree-agent-ac043cfbb4e8a782d):
questions.jsonl (65 questions), judgments.jsonl (760 Sonnet judgments), summary.json (summarize.py's output), and
answers.jsonl, the run-1 answers of every system to D06, P02, S02 and M08 taken from runs/<system>.jsonl (answer,
seconds, model calls, tool calls; nothing else changed).
"""
import html
import json
import statistics
from pathlib import Path

E = html.escape
SYS = ["ours", "rag", "rag_think", "graphrag_text", "graphrag_notext", "plain", "abl_facts", "abl_graph"]
NAME = {"ours": "Ours", "rag": "RAG", "rag_think": "RAG + thinking", "graphrag_text": "GraphRAG with text",
        "graphrag_notext": "GraphRAG, no text", "plain": "Plain LLM", "abl_facts": "Ours, fact search only",
        "abl_graph": "Ours, graph tools only"}
SHORT = {"ours": "ours", "rag": "RAG", "rag_think": "RAG+think", "graphrag_text": "GraphRAG+text",
         "graphrag_notext": "GraphRAG", "plain": "plain", "abl_facts": "facts only", "abl_graph": "graph only"}
CATS = ["definition", "explanation", "comparison", "list", "formula", "where", "prerequisite", "structure",
        "not_covered", "multihop"]
CATNAME = {"not_covered": "not covered"}
# colours: the page's own tokens; the two ablations are variants of ours, so they keep its hue with another shape
COLOR = {"ours": "var(--accent)", "rag": "var(--c-qa)", "rag_think": "var(--c-judge)",
         "graphrag_text": "var(--c-emb)", "graphrag_notext": "var(--c-emb)", "plain": "var(--c-skip)",
         "abl_facts": "var(--accent)", "abl_graph": "var(--accent)"}


BOLD = ' style="font-weight:650"'


def f2(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def f3(x):
    return str(round(x, 3)) if isinstance(x, float) else str(x)


def table(head, rows, num=(), cls=""):
    h = "".join(f'<th{" class=n" if i in num else ""}>{x}</th>' for i, x in enumerate(head))
    b = "".join(f'<tr{(" class=" + r[1]) if isinstance(r, tuple) else ""}>' +
                "".join(f'<td{" class=n" if i in num else ""}>{c}</td>' for i, c in enumerate(r[0] if isinstance(r, tuple) else r))
                + "</tr>" for r in rows)
    return f'<div class="tablewrap{(" " + cls) if cls else ""}"><table><tr>{h}</tr>{b}</table></div>'


def mark(sysname, cx, cy, r=6.5):
    c = COLOR[sysname]
    if sysname == "abl_facts":
        return f'<rect x="{cx - r + 1:.1f}" y="{cy - r + 1:.1f}" width="{2 * r - 2:.1f}" height="{2 * r - 2:.1f}" rx="1.5" style="fill:var(--surface);stroke:{c};stroke-width:2.2"/>'
    if sysname == "abl_graph":
        return (f'<path d="M{cx:.1f},{cy - r - 1:.1f} L{cx + r + 1:.1f},{cy:.1f} L{cx:.1f},{cy + r + 1:.1f} '
                f'L{cx - r - 1:.1f},{cy:.1f} Z" style="fill:var(--surface);stroke:{c};stroke-width:2.2"/>')
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" style="fill:{c};stroke:var(--surface);stroke-width:2"/>'


def legend_svg(series, x0, y):
    out, x = [], x0
    for s in series:
        out.append(mark(s, x + 7, y - 5))
        out.append(f'<text x="{x + 20}" y="{y}" class="t-s ink2">{E(NAME[s])}</text>')
        x += 40 + 7.4 * len(NAME[s])
    return "".join(out)


def dot_plot(S, series, title_id, title):
    """Rows = all 65 questions + each category; x = mean correct 0..1; one mark per system, offset per system."""
    rows = [("all", "all 65 questions", S["overall"])] + \
           [(c, f"{CATNAME.get(c, c)} ({S['per_category'][c]['ours']['answers']})", S["per_category"][c]) for c in CATS]
    L, R, top, rh = 210, 1010, 62, 50
    W = 1040
    H = top + rh * len(rows) + 46
    X = lambda v: L + (R - L) * v
    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="{title_id}"><title id="{title_id}">{E(title)}</title>']
    p.append(legend_svg(series, L - 4, 24))
    for v in (0, .25, .5, .75, 1):
        p.append(f'<line x1="{X(v):.1f}" y1="{top - 10}" x2="{X(v):.1f}" y2="{top + rh * len(rows) - 6}" style="stroke:var(--line);stroke-width:1"/>')
        p.append(f'<text x="{X(v):.1f}" y="{top + rh * len(rows) + 14}" class="t-s mut" text-anchor="middle">{f2(float(v))}</text>')
    p.append(f'<text x="{(L + R) / 2:.0f}" y="{top + rh * len(rows) + 38}" class="t-s mut" text-anchor="middle">mean correct (1 / 0.5 / 0, Sonnet judge, run 1)</text>')
    n = len(series)
    for i, (key, label, d) in enumerate(rows):
        cy = top + rh * i + rh / 2 - 6
        if i == 0:
            p.append(f'<rect x="8" y="{cy - rh / 2 + 2:.1f}" width="{W - 16}" height="{rh - 4}" rx="8" style="fill:var(--surface-2)"/>')
        p.append(f'<text x="{L - 16}" y="{cy + 5:.1f}" class="t-s{"" if i else " ink2"}" text-anchor="end"'
                 f'{BOLD if i == 0 else ""}>{E(label)}</text>')
        vals = [d[s]["correct"] for s in series]
        p.append(f'<line x1="{X(min(vals)):.1f}" y1="{cy:.1f}" x2="{X(max(vals)):.1f}" y2="{cy:.1f}" style="stroke:var(--line-2);stroke-width:2"/>')
        for j, s in enumerate(series):
            off = (j - (n - 1) / 2) * 7
            v = d[s]["correct"]
            p.append(f'<g>{mark(s, X(v), cy + off)}<title>{E(NAME[s])} · {E(label)}: {f3(v)}</title></g>')
    p.append("</svg>")
    return "".join(p)


def latency_bars(S):
    order = sorted(SYS, key=lambda s: S["overall"][s]["latency_median_s"])
    L, R, top, rh = 210, 860, 20, 38
    W, H = 1040, top + rh * len(order) + 52
    mx = 60
    X = lambda v: L + (R - L) * v / mx
    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="blt"><title id="blt">Median and 90th-percentile '
         f'answer time per system, with mean correct</title>']
    for v in range(0, mx + 1, 10):
        p.append(f'<line x1="{X(v):.1f}" y1="{top - 4}" x2="{X(v):.1f}" y2="{top + rh * len(order)}" style="stroke:var(--line);stroke-width:1"/>')
        p.append(f'<text x="{X(v):.1f}" y="{top + rh * len(order) + 18}" class="t-s mut" text-anchor="middle">{v} s</text>')
    p.append(f'<text x="{(L + R) / 2:.0f}" y="{top + rh * len(order) + 42}" class="t-s mut" text-anchor="middle">'
             f'seconds per answer, RTX 5070 12 GB, one question at a time: bar = median, thin line to the 90th percentile</text>')
    for i, s in enumerate(order):
        o = S["overall"][s]
        y = top + rh * i + 6
        c = COLOR[s]
        p.append(f'<text x="{L - 14}" y="{y + 18}" class="t-s{"" if s == "ours" else " ink2"}" text-anchor="end"'
                 f'{BOLD if s == "ours" else ""}>{E(NAME[s])}</text>')
        p.append(f'<line x1="{X(o["latency_median_s"]):.1f}" y1="{y + 13}" x2="{X(o["latency_p90_s"]):.1f}" y2="{y + 13}" style="stroke:{c};stroke-width:2"/>')
        p.append(f'<line x1="{X(o["latency_p90_s"]):.1f}" y1="{y + 7}" x2="{X(o["latency_p90_s"]):.1f}" y2="{y + 19}" style="stroke:{c};stroke-width:2"/>')
        p.append(f'<g><rect x="{L}" y="{y + 3}" width="{X(o["latency_median_s"]) - L:.1f}" height="20" rx="4" '
                 f'style="fill:color-mix(in srgb, {c} 30%, var(--surface));stroke:{c};stroke-width:1.4"/>'
                 f'<title>{E(NAME[s])}: median {o["latency_median_s"]} s, p90 {o["latency_p90_s"]} s, first token '
                 f'{o["first_token_median_s"]} s, {o["model_calls_mean"]} model calls</title></g>')
        p.append(f'<text x="{X(o["latency_p90_s"]) + 10:.1f}" y="{y + 18}" class="t-s ink2">{o["latency_median_s"]} s · correct {f3(o["correct"])}</text>')
    p.append("</svg>")
    return "".join(p)


def build(HERE):
    D = HERE / "baselines"
    S = json.loads((D / "summary.json").read_text())
    Q = [json.loads(l) for l in (D / "questions.jsonl").read_text().splitlines() if l.strip()]
    JL = [json.loads(l) for l in (D / "judgments.jsonl").read_text().splitlines() if l.strip()]
    J = {(j["qid"], j["system"], j["run"]): j for j in JL}
    A = {(a["id"], a["system"]): a for a in map(json.loads, (D / "answers.jsonl").read_text().splitlines())}
    X = {}
    ov = S["overall"]
    pc = S["per_category"]
    X["n_judged"] = f"{len(JL)}"
    X["n_questions"] = f"{len(Q)}"

    # ---- overall
    rows = []
    for s in SYS:
        o = ov[s]
        cit = f'{o["citations_valid"]}/{o["citations"]}' if o["citations"] else "none written"
        rows.append(([f"<b>{NAME[s]}</b>" if s == "ours" else NAME[s], f3(o["correct"]),
                      f'{o["hallucinations"]} ({o["answers_with_hallucination"]})', cit,
                      f'{o["not_covered_handled"]}/{o["not_covered_judged"]}', f'{o["context_tokens_median"]:,}',
                      f3(o["model_calls_mean"]), f2(o["latency_median_s"]), f2(o["latency_p90_s"]),
                      f2(o["first_token_median_s"])], "total" if s == "ours" else ""))
    X["overall"] = table(["System", "Correct", "False claims (answers)", "Citations valid", "“Not covered” handled",
                          "Context tokens, median", "Model calls, mean", "Seconds, median", "Seconds, p90",
                          "First token, s"], rows, num=range(1, 10))

    # ---- per category, one table per measure
    def cat_table(fn, best=None, numfmt=f3):
        rows = []
        for c in CATS:
            vals = {s: fn(pc[c][s]) for s in SYS}
            cells = []
            for s in SYS:
                v = vals[s]
                txt = numfmt(v) if not isinstance(v, str) else v
                if best is not None and not isinstance(v, str):
                    top = best([vals[x] for x in SYS if not isinstance(vals[x], str)])
                    if v == top:
                        txt = f"<b>{txt}</b>"
                cells.append(txt)
            rows.append([f'{CATNAME.get(c, c)} ({pc[c]["ours"]["answers"]})'] + cells)
        return table(["Category (n)"] + [SHORT[s] for s in SYS], rows, num=range(1, 9))
    X["cat_correct"] = cat_table(lambda d: d["correct"], best=max)
    X["cat_halluc"] = cat_table(lambda d: d["hallucinations"], numfmt=str)
    X["cat_cit"] = cat_table(lambda d: f'{d["citations_valid"]}/{d["citations"]}' if d["citations"] else "—")
    X["cat_lat"] = cat_table(lambda d: f'{f2(d["latency_median_s"])} / {f2(d["first_token_median_s"])}')
    X["cat_ctx"] = cat_table(lambda d: f'{int(d["context_tokens_median"]):,} · {f2(d["model_calls_mean"])}')

    # ---- headline table for Part I: where ours wins, with the part of the layer
    part = {"definition": "concept cards (<code>check_concept</code>): one definition per concept, from its defining facts",
            "prerequisite": "the lecture dependency graph (<code>lecture_dependencies</code>, stage 4c)",
            "formula": "concept cards and facts: the formula's fact is found as a whole, with its terms",
            "where": "facts with sentence times; every retrieval system ties",
            "not_covered": "the calibrated “no close match” cut-off of the fact search; RAG's prompt does slightly better"}
    rows = []
    for c in ["definition", "prerequisite", "formula", "where", "not_covered"]:
        d = pc[c]
        rows.append([f'{CATNAME.get(c, c)} ({d["ours"]["answers"]})<br><span class="small muted">{part[c]}</span>',
                     f'<b>{f3(d["ours"]["correct"])}</b>', f3(d["rag"]["correct"]), f3(d["rag_think"]["correct"]),
                     f3(d["graphrag_text"]["correct"]), f3(d["plain"]["correct"]), f3(d["abl_facts"]["correct"]),
                     f3(d["abl_graph"]["correct"])])
    X["wins"] = table(["Category (n) and the part of the layer behind it", "Ours", "RAG", "RAG + thinking",
                       "GraphRAG + text", "Plain", "Fact search only", "Graph tools only"], rows, num=range(1, 8))
    rows = []
    for c in ["explanation", "comparison", "list", "structure", "multihop"]:
        d = pc[c]
        rows.append([f'{CATNAME.get(c, c)} ({d["ours"]["answers"]})', f3(d["ours"]["correct"]),
                     f'<b>{f3(d["rag"]["correct"])}</b>', f3(d["rag_think"]["correct"]),
                     f3(d["graphrag_text"]["correct"]), f3(d["abl_facts"]["correct"]), f3(d["abl_graph"]["correct"])])
    rows.append((["all 65", f3(ov["ours"]["correct"]), f'<b>{f3(ov["rag"]["correct"])}</b>', f3(ov["rag_think"]["correct"]),
                  f3(ov["graphrag_text"]["correct"]), f3(ov["abl_facts"]["correct"]), f3(ov["abl_graph"]["correct"])], "total"))
    X["ties"] = table(["Category (n)", "Ours", "RAG", "RAG + thinking", "GraphRAG + text", "Fact search only",
                       "Graph tools only"], rows, num=range(1, 7))

    # ---- cost
    o, r, t = ov["ours"], ov["rag"], ov["rag_think"]
    X["cost"] = table(["Per question (65 questions, run 1)", "Ours", "RAG", "RAG + thinking"], [
        ["Context tokens, median (all model calls summed)", f'{o["context_tokens_median"]:,}', f'{r["context_tokens_median"]:,}', f'{t["context_tokens_median"]:,}'],
        ["Model calls, mean", f3(o["model_calls_mean"]), f3(r["model_calls_mean"]), f3(t["model_calls_mean"])],
        ["Seconds, median", f2(o["latency_median_s"]), f2(r["latency_median_s"]), f2(t["latency_median_s"])],
        ["Seconds, 90th percentile", f2(o["latency_p90_s"]), f2(r["latency_p90_s"]), f2(t["latency_p90_s"])],
        ["First answer token, median s", f2(o["first_token_median_s"]), f2(r["first_token_median_s"]), f2(t["first_token_median_s"])],
        ["Correct (all 65)", f3(o["correct"]), f3(r["correct"]), f3(t["correct"])],
    ], num=(1, 2, 3))

    # ---- repeats: summary.json's five categories, multihop from the judgments
    rows = []
    for c in list(S["repeats"]) + ["multihop"]:
        cells = []
        for s in ("ours", "rag", "rag_think"):
            if c in S["repeats"]:
                d = S["repeats"][c][s]
                runs = [d["runs"][k] for k in ("1", "2", "3")]
            else:
                runs = [statistics.mean(J[(q["id"], s, k)]["correct"] for q in Q if q["category"] == c) for k in (1, 2, 3)]
            cells.append(" · ".join(f3(float(x)) for x in runs))
        rows.append([f'{CATNAME.get(c, c)}'] + cells)
    X["repeats"] = table(["Category", "Ours, runs 1 · 2 · 3", "RAG, runs 1 · 2 · 3", "RAG + thinking, runs 1 · 2 · 3"], rows)

    # ---- charts
    X["fig_cat"] = dot_plot(S, ["ours", "rag", "rag_think", "graphrag_text", "plain"], "bcat",
                            "Mean correct per category: ours, RAG, RAG with thinking, GraphRAG with text, plain LLM")
    X["fig_abl"] = dot_plot(S, ["ours", "abl_facts", "abl_graph", "rag"], "babl",
                            "Mean correct per category: ours, its two ablations, and RAG")
    X["fig_lat"] = latency_bars(S)

    # ---- every question, per category, with run-1 scores of every system
    blocks = []
    for c in CATS:
        qs = [q for q in Q if q["category"] == c]
        rows = []
        for q in qs:
            cells = []
            for s in SYS:
                j = J.get((q["id"], s, 1))
                v = j["correct"] if j else None
                cells.append("—" if v is None else f2(float(v)) + ("*" if j["hallucinations"] else ""))
            notes = "".join(f'<br><span class="small muted">{SHORT[s]}: {E(J[(q["id"], s, 1)]["note"])}</span>'
                            for s in ("ours", "rag"))
            src = "; ".join(E(x) for x in q["gold_sources"])
            exp = "" if q["expect"] == "yes" else f' <span class="pill pa">expect: {E(q["expect"])}</span>'
            rows.append([f'<b class="mono">{q["id"]}</b>', f'<div style="min-width:min(420px,60vw)"><b>{E(q["question"])}</b>{exp}'
                         f'<br><span class="small"><span class="muted">Gold ({E(q["origin"])}):</span> {E(q["gold_answer"])}</span>'
                         f'<br><span class="small muted">Sources: {src}</span>{notes}</div>'] + cells)
        blocks.append(f'<details><summary>{E(CATNAME.get(c, c).capitalize())} <span class="meta">{len(qs)} questions · '
                      f'mean correct: ours {f3(pc[c]["ours"]["correct"])}, RAG {f3(pc[c]["rag"]["correct"])}</span></summary>'
                      + table(["ID", "Question, gold answer and sources; judge notes on ours and RAG"] + [SHORT[s] for s in SYS],
                              rows, num=range(2, 10)) + "</details>")
    X["questions"] = "".join(blocks)

    # ---- real answers side by side
    def ans(qid, systems, meta=""):
        q = [x for x in Q if x["id"] == qid][0]
        parts = []
        for s in systems:
            a, j = A[(qid, s)], J[(qid, s, 1)]
            tools = ", ".join(t[0] for t in a["tools"]) or "no tools"
            parts.append(f'<div><span class="lbl">{E(NAME[s])} · correct {f2(float(j["correct"]))} · {a["seconds"]} s'
                         f'{" · " + E(tools) if s.startswith(("ours", "abl")) else ""}</span>'
                         f'<pre data-lang="text" class="wrap">{E(a["answer"].strip())}</pre>'
                         f'<p class="small muted">Judge: {E(j["note"])}</p></div>')
        return (f'<details><summary>{qid} · “{E(q["question"])}” <span class="meta">{E(meta)}run 1, real answers</span>'
                f'</summary><div class="split ans">{"".join(parts)}</div></details>')
    X["ans_D06"] = ans("D06", ["ours", "rag"], "definition · ")
    X["ans_P02"] = ans("P02", ["ours", "rag"], "prerequisite · ")
    X["ans_S02"] = ans("S02", ["ours", "rag"], "structure · ")
    X["ans_M08"] = ans("M08", ["ours", "rag"], "multihop · ")
    return X
