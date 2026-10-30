#!/usr/bin/env python3
"""Build docs/pipeline.html: how the pipeline works, with real examples and charts from the built courses.

    python3 build_docs.py          (also run automatically at the end of generate_lir.py)

Everything is read from the outputs (lir/, output/*/timing.json, the prompts), so the page stays current.
The page is self-contained: inline CSS, inline SVG charts, a few lines of JS for tooltips. No network needed.
"""
from __future__ import annotations

import html
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

E = html.escape
# reference categorical palette (light, dark), used in fixed slot order
SLOTS = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500"),
         ("#e87ba4", "#d55181"), ("#008300", "#008300"), ("#6250d6", "#9085e9"), ("#e34948", "#e66767")]
FAMILIES = [  # content types folded into six families, so the timeline needs at most six colors
    ("Motivation", {"motivation"}),
    ("Definition", {"definition"}),
    ("Explanation / derivation", {"mechanism_explanation", "derivation_or_proof"}),
    ("Procedure / example", {"procedure_or_algorithm", "worked_example", "application_or_demo"}),
    ("Comparison", {"comparison"}),
    ("Recap / discussion", {"recap", "discussion"}),
]
STAGE_GROUPS = [
    ("1 · Segment", ["stage1_segment"]), ("2 · Annotate", ["stage2_annotate"]),
    ("3–4 · Goals + course state", ["stage3_goals", "stage4_course_state"]),
    ("5 · Generate", ["stage5_generate"]), ("6 · Judge + repair", ["stage6_judge"]),
    ("Other (transcripts, calibration, assembly)", ["transcripts", "stage6_calibrate", "stage7_assemble", "docs"]),
]
BENCH = [(16, 498), (32, 630), (48, 629), (64, 612)]  # measured on the RTX 5070, 64-128 annotation-style calls


def fam_of(ct: str) -> int:
    return next(i for i, (_, s) in enumerate(FAMILIES) if ct in s)


def clock(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


# ------------------------------------------------------------------ data
def load(root: Path) -> list[dict]:
    courses = []
    idx = root / "lir" / "index.json"
    if not idx.exists():
        return courses
    for c in json.loads(idx.read_text())["courses"]:
        d = root / c["path"]
        course = json.loads((d / "course.json").read_text())
        lecs = [json.loads((d / f"{lid}.json").read_text()) for lid in course["lecture_ids"] if (d / f"{lid}.json").exists()]
        tj = root / "output" / c["course_id"] / "timing.json"
        courses.append({"course": course, "lectures": lecs, "timing": json.loads(tj.read_text()) if tj.exists() else None})
    courses.sort(key=lambda x: -len(x["lectures"]))
    return courses


# ------------------------------------------------------------------ charts (inline SVG)
def legend(items: list[tuple[str, int]]) -> str:
    return '<div class="legend">' + "".join(
        f'<span><i style="background:var(--s{k + 1})"></i>{E(label)}</span>' for label, k in items) + "</div>"


def timeline_chart(lectures: list[dict], human: dict | None = None) -> str:
    """One row per lecture: segments as bars colored by content family; optional human-boundary row."""
    W, rowh, gap, left = 900, 18, 8, 64
    maxd = max(l["duration_s"] for l in lectures)
    rows = []
    y = 0
    for l in lectures:
        x0 = left
        rows.append(f'<text x="{left - 8}" y="{y + 13}" text-anchor="end" class="ax">{E(l["lecture_id"])}</text>')
        for s in l["segments"]:
            x = left + (s["start"] / maxd) * (W - left - 10)
            w = max(2.0, (s["end"] - s["start"]) / maxd * (W - left - 10) - 2)
            k = fam_of(s["content_type"])
            tip = f'{l["lecture_id"]} {s["id"]} · {clock(s["start"])}–{clock(s["end"])} · {s["content_type"].replace("_", " ")}<br>{E(s["subgoal"])}'
            rows.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{rowh}" rx="4" fill="var(--s{k + 1})" '
                        f'data-tip="{E(tip, quote=True)}"/>')
        y += rowh + gap
        if human and l["lecture_id"] == human["lecture_id"]:
            rows.append(f'<text x="{left - 8}" y="{y + 11}" text-anchor="end" class="ax">human</text>')
            rows.append(f'<line x1="{left}" x2="{W - 10}" y1="{y + 7}" y2="{y + 7}" class="grid"/>')
            for t in human["coarse"]:
                x = left + t / maxd * (W - left - 10)
                rows.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y}" y2="{y + 14}" class="hmark" '
                            f'data-tip="human boundary at {clock(t)}"/>')
            for s in l["segments"][1:]:
                x = left + s["start"] / maxd * (W - left - 10)
                rows.append(f'<circle cx="{x:.1f}" cy="{y - gap / 2 - 1:.1f}" r="2.5" class="pmark" '
                            f'data-tip="pipeline cut at {clock(s["start"])}"/>')
            y += 22
    ticks = ""
    step = 600 if maxd > 2400 else 300
    for t in range(0, int(maxd) + 1, step):
        x = left + t / maxd * (W - left - 10)
        ticks += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{y}" class="grid"/><text x="{x:.1f}" y="{y + 14}" text-anchor="middle" class="ax">{t // 60}m</text>'
    used = sorted({fam_of(s["content_type"]) for l in lectures for s in l["segments"]})
    return (f'<svg viewBox="0 0 {W} {y + 22}" class="chart" role="img" aria-label="Segment timeline">{ticks}{"".join(rows)}</svg>'
            + legend([(FAMILIES[k][0], k) for k in used]))


def stacked_time_chart(timing: dict) -> str:
    """Processing minutes per lecture, stacked by stage group."""
    rows = timing["lectures"]
    W, barh, gap, left = 900, 16, 6, 64
    vals = []
    for r in rows:
        bs = r.get("by_stage_s", {})
        vals.append([sum(bs.get(st, 0) for st in sts) / 60 for _, sts in STAGE_GROUPS])
    mx = max(sum(v) for v in vals) or 1
    out, y = [], 0
    for r, v in zip(rows, vals):
        x = left
        out.append(f'<text x="{left - 8}" y="{y + 12}" text-anchor="end" class="ax">{E(r["lecture_id"])}</text>')
        for k, val in enumerate(v):
            w = val / mx * (W - left - 70)
            if w < 0.5:
                continue
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(1, w - 2):.1f}" height="{barh}" rx="3" fill="var(--s{k + 1})" '
                       f'data-tip="{E(r["lecture_id"])} · {E(STAGE_GROUPS[k][0])}: {val:.1f} min"/>')
            x += w
        out.append(f'<text x="{x + 6:.1f}" y="{y + 12}" class="ax val">{sum(v):.1f} min · {r["video_min"]} min video</text>')
        y += barh + gap
    return (f'<svg viewBox="0 0 {W + 120} {y + 4}" class="chart" role="img" aria-label="Processing time per lecture">{"".join(out)}</svg>'
            + legend([(g, k) for k, (g, _) in enumerate(STAGE_GROUPS)]))


def bench_chart() -> str:
    W, H, left, bot = 520, 200, 44, 28
    mx = 700
    out = []
    for v in (0, 200, 400, 600):
        y = H - bot - v / mx * (H - bot - 10)
        out.append(f'<line x1="{left}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" class="ax">{v}</text>')
    bw = (W - left) / len(BENCH)
    for i, (slots, tps) in enumerate(BENCH):
        x = left + i * bw + bw * 0.25
        h = tps / mx * (H - bot - 10)
        out.append(f'<rect x="{x:.1f}" y="{H - bot - h:.1f}" width="{bw * 0.5:.1f}" height="{h:.1f}" rx="4" fill="var(--s1)" '
                   f'data-tip="{slots} slots: {tps} output tokens/s"/>')
        out.append(f'<text x="{x + bw * 0.25:.1f}" y="{H - bot - h - 6:.1f}" text-anchor="middle" class="ax val">{tps}</text>')
        out.append(f'<text x="{x + bw * 0.25:.1f}" y="{H - 10}" text-anchor="middle" class="ax">{slots} slots</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart small-chart" role="img" aria-label="Throughput by slot count">{"".join(out)}</svg>'


def judge_chart(judge: dict) -> str:
    keys = [("passed_first", "Passed first time"), ("repaired", "Repaired, then passed"), ("dropped", "Dropped"),
            ("replaced_by_code", "Replaced by code")]
    label = {"subgoal": "Sub-goals", "term": "Definitions", "quiz": "Quiz items", "summary": "Summaries",
             "oq": "Open questions", "recall": "Recall items", "edge": "Edges"}
    W, barh, gap, left = 900, 16, 6, 120
    out, y = [], 0
    for kind, c in judge.items():
        tot = c.get("judged", 0) or 1
        x = left
        out.append(f'<text x="{left - 8}" y="{y + 12}" text-anchor="end" class="ax">{E(label.get(kind, kind))}</text>')
        for k, (key, name) in enumerate(keys):
            v = c.get(key, 0)
            w = v / tot * (W - left - 80)
            if v:
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(1, w - 2):.1f}" height="{barh}" rx="3" fill="var(--s{k + 1})" '
                           f'data-tip="{E(label.get(kind, kind))} · {name}: {v} of {c.get("judged", 0)}"/>')
            x += w
        out.append(f'<text x="{x + 6:.1f}" y="{y + 12}" class="ax val">{c.get("judged", 0)} judged</text>')
        y += barh + gap
    return (f'<svg viewBox="0 0 {W} {y + 4}" class="chart" role="img" aria-label="Judge outcomes">{"".join(out)}</svg>'
            + legend([(n, k) for k, (_, n) in enumerate(keys)]))


def concept_graph(course: dict, n: int = 36) -> str:
    """Top concepts by salience and the edges among them, laid out with a small force simulation."""
    import numpy as np
    cs = sorted(course["concepts"], key=lambda c: -c["salience"])[:n]
    ids = [c["id"] for c in cs]
    pos = {cid: i for i, cid in enumerate(ids)}
    edges = [e for e in course["edges"] if e["src"] in pos and e["dst"] in pos]
    lec_order = {lid: i for i, lid in enumerate(course["lecture_ids"])}
    W, H = 900, 520
    rng = np.random.default_rng(0)
    P = rng.uniform([100, 60], [W - 100, H - 60], size=(len(ids), 2))
    for _ in range(400):
        F = np.zeros_like(P)
        d = P[:, None, :] - P[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1)) + 1e-3
        F += (d / dist[..., None] * (7000 / dist ** 2)[..., None]).sum(1)
        for e in edges:
            a, b = pos[e["src"]], pos[e["dst"]]
            v = P[b] - P[a]
            L = np.linalg.norm(v) + 1e-3
            f = (L - 130) * 0.03 * v / L
            F[a] += f
            F[b] -= f
        F += (np.array([W / 2, H / 2]) - P) * 0.01
        P += np.clip(F, -15, 15)
        P[:, 0] = P[:, 0].clip(70, W - 70)
        P[:, 1] = P[:, 1].clip(24, H - 24)
    nl = max(1, len(course["lecture_ids"]) - 1)
    out = []
    for e in edges:
        a, b = P[pos[e["src"]]], P[pos[e["dst"]]]
        out.append(f'<line x1="{a[0]:.0f}" y1="{a[1]:.0f}" x2="{b[0]:.0f}" y2="{b[1]:.0f}" class="gedge" '
                   f'data-tip="{E(cs[pos[e["src"]]]["name"])} — {E(e["label"])} — {E(cs[pos[e["dst"]]]["name"])} ({e["rel"]}, {e["evidence"]["lecture_id"]})"/>')
    for c, p in zip(cs, P):
        r = 5 + 9 * c["salience"]
        lpos = lec_order.get(c["introduced"]["lecture_id"], 0) / nl
        out.append(f'<circle cx="{p[0]:.0f}" cy="{p[1]:.0f}" r="{r:.1f}" fill="var(--s1)" fill-opacity="{0.35 + 0.65 * (1 - lpos):.2f}" '
                   f'class="gnode" data-tip="{E(c["name"])}<br>introduced in {c["introduced"]["lecture_id"]} · salience {c["salience"]}"/>')
        out.append(f'<text x="{p[0]:.0f}" y="{p[1] - r - 4:.0f}" text-anchor="middle" class="glabel">{E(c["name"][:26])}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Concept graph">{"".join(out)}</svg>'
            f'<p class="note">The {len(cs)} most salient concepts of {E(course["title"])} and the {len(edges)} edges among them. '
            f'Circle size is salience; darker circles were introduced earlier in the course. Hover for details.</p>')


ARCH = """<svg viewBox="0 0 900 330" class="chart" role="img" aria-label="Pipeline architecture">
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arrowhead"/></marker></defs>
<g class="box"><rect x="10" y="20" width="150" height="56" rx="10"/><text x="85" y="44" text-anchor="middle" class="bt">0 · Transcripts</text><text x="85" y="62" text-anchor="middle" class="bs">SRT → sentences; align</text></g>
<g class="box"><rect x="190" y="20" width="150" height="56" rx="10"/><text x="265" y="44" text-anchor="middle" class="bt">1 · Segment</text><text x="265" y="62" text-anchor="middle" class="bs">1 call / lecture</text></g>
<g class="box"><rect x="370" y="20" width="150" height="56" rx="10"/><text x="445" y="44" text-anchor="middle" class="bt">2 · Annotate</text><text x="445" y="62" text-anchor="middle" class="bs">2 calls / segment</text></g>
<g class="box"><rect x="550" y="20" width="150" height="56" rx="10"/><text x="625" y="44" text-anchor="middle" class="bt">3 · Goal hierarchy</text><text x="625" y="62" text-anchor="middle" class="bs">1 call / lecture</text></g>
<g class="box seq"><rect x="730" y="20" width="160" height="56" rx="10"/><text x="810" y="44" text-anchor="middle" class="bt">4 · Course state</text><text x="810" y="62" text-anchor="middle" class="bs">lecture order · state[k]</text></g>
<g class="box"><rect x="730" y="130" width="160" height="56" rx="10"/><text x="810" y="154" text-anchor="middle" class="bt">5 · Generate</text><text x="810" y="172" text-anchor="middle" class="bs">primer, quiz, summary, OQ</text></g>
<g class="box judge"><rect x="500" y="130" width="200" height="56" rx="10"/><text x="600" y="154" text-anchor="middle" class="bt">6 · Judge + repair</text><text x="600" y="172" text-anchor="middle" class="bs">12B judges · E4B repairs · ×2</text></g>
<g class="box"><rect x="300" y="130" width="170" height="56" rx="10"/><text x="385" y="154" text-anchor="middle" class="bt">6 · Calibrate scorer</text><text x="385" y="172" text-anchor="middle" class="bs">m, τ from generated answers</text></g>
<g class="box"><rect x="100" y="130" width="170" height="56" rx="10"/><text x="185" y="154" text-anchor="middle" class="bt">7 · Assemble LIR</text><text x="185" y="172" text-anchor="middle" class="bs">no LLM · schema check</text></g>
<g class="box out"><rect x="10" y="240" width="260" height="56" rx="10"/><text x="140" y="264" text-anchor="middle" class="bt">lir/&lt;course&gt;/</text><text x="140" y="282" text-anchor="middle" class="bs">course.json + Lxx.json → viewer</text></g>
<g class="box vid"><rect x="330" y="240" width="300" height="56" rx="10"/><text x="480" y="264" text-anchor="middle" class="bt">Videos (background thread)</text><text x="480" y="282" text-anchor="middle" class="bs">yt-dlp · 720p · media/&lt;course&gt;/</text></g>
<g class="box"><rect x="690" y="240" width="200" height="56" rx="10"/><text x="790" y="264" text-anchor="middle" class="bt">Layer 1 + 2 validation</text><text x="790" y="282" text-anchor="middle" class="bs">inside every stage</text></g>
<path d="M160 48 H186" class="flow" marker-end="url(#ar)"/><path d="M340 48 H366" class="flow" marker-end="url(#ar)"/>
<path d="M520 48 H546" class="flow" marker-end="url(#ar)"/><path d="M700 48 H726" class="flow" marker-end="url(#ar)"/>
<path d="M810 76 V126" class="flow" marker-end="url(#ar)"/><path d="M730 158 H704" class="flow" marker-end="url(#ar)"/>
<path d="M500 158 H474" class="flow" marker-end="url(#ar)"/><path d="M300 158 H274" class="flow" marker-end="url(#ar)"/>
<path d="M185 186 V236" class="flow" marker-end="url(#ar)"/><path d="M480 240 V200 H280" class="flow dashed"/>
</svg>"""


# ------------------------------------------------------------------ page
CSS = """
:root{--bg:#fcfcfb;--panel:#ffffff;--text:#0b0b0b;--muted:#52514e;--faint:#8a8984;--line:#e6e5e0;--code:#f4f3ef;--accent:#2a78d6;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#6250d6;--s8:#e34948;color-scheme:light}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--bg:#141413;--panel:#1a1a19;--text:#f0efec;--muted:#c3c2b7;--faint:#8f8e86;--line:#2e2e2b;--code:#222220;--accent:#3987e5;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#141413;--panel:#1a1a19;--text:#f0efec;--muted:#c3c2b7;--faint:#8f8e86;--line:#2e2e2b;--code:#222220;--accent:#3987e5;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text)}
body{font:15.5px/1.62 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.layout{display:grid;grid-template-columns:250px 1fr;max-width:1240px;margin:0 auto}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:28px 16px;border-right:1px solid var(--line);font-size:14px}
nav a{display:block;color:var(--muted);text-decoration:none;padding:4px 8px;border-radius:6px}nav a:hover{background:var(--code);color:var(--text)}
nav .sub{padding-left:18px;font-size:13px}
main{padding:36px 40px 120px;min-width:0}
h1{font-size:34px;letter-spacing:-.015em;margin:0 0 6px}h2{font-size:24px;margin:56px 0 12px;padding-top:12px;border-top:1px solid var(--line)}
h3{font-size:18px;margin:30px 0 8px}p{max-width:78ch}.lead{font-size:18px;color:var(--muted);max-width:70ch}
code{font:13px/1.5 "JetBrains Mono",ui-monospace,Menlo,monospace;background:var(--code);padding:1px 5px;border-radius:5px}
pre{font:12.5px/1.55 "JetBrains Mono",ui-monospace,Menlo,monospace;background:var(--code);padding:14px 16px;border-radius:10px;overflow:auto;max-height:440px;white-space:pre-wrap}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0 18px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}.tile b{display:block;font-size:26px}.tile span{color:var(--muted);font-size:13px}
details{margin:8px 0}summary{cursor:pointer;color:var(--accent);font-weight:550}
.tag{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:99px;background:var(--code);color:var(--muted);margin-right:4px}
.chart{width:100%;height:auto;display:block;margin:10px 0}.small-chart{max-width:560px}
.chart .ax{font-size:11.5px;fill:var(--muted)}.chart .val{fill:var(--text)}.chart .grid{stroke:var(--line);stroke-width:1}
.chart rect[data-tip],.chart circle[data-tip],.chart line[data-tip]{cursor:default}
.chart .hmark{stroke:var(--text);stroke-width:2}.chart .pmark{fill:var(--text)}
.chart .gedge{stroke:var(--faint);stroke-width:1.4}.chart .gnode{stroke:var(--panel);stroke-width:2}.chart .glabel{font-size:11px;fill:var(--text);paint-order:stroke;stroke:var(--bg);stroke-width:3px}
.chart .box rect{fill:var(--panel);stroke:var(--line);stroke-width:1.5}.chart .box.seq rect{stroke:var(--s1);stroke-width:2}
.chart .box.judge rect{stroke:var(--s7);stroke-width:2}.chart .box.out rect{stroke:var(--s3);stroke-width:2}.chart .box.vid rect{stroke-dasharray:5 4}
.chart .bt{font-size:14px;font-weight:650;fill:var(--text)}.chart .bs{font-size:12px;fill:var(--muted)}
.chart .flow{stroke:var(--faint);stroke-width:1.6;fill:none}.chart .dashed{stroke-dasharray:5 4}.chart .arrowhead{fill:var(--faint)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted);margin:2px 0 10px}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.note{font-size:13px;color:var(--muted)}
#tip{position:fixed;pointer-events:none;background:var(--text);color:var(--bg);font-size:12.5px;padding:6px 9px;border-radius:7px;max-width:340px;z-index:10;display:none}
.formal{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;padding:6px 18px;margin:14px 0}
.formal p,.formal li{max-width:none}.formal sub,.formal sup{font-size:.72em}
.chart .treeobj{fill:var(--panel);stroke:var(--accent);stroke-width:1.5}.chart .stripl{font-size:11px;font-weight:700;fill:#fff;pointer-events:none}
.opt{padding:4px 0}.opt.ok{font-weight:650}
.theme{position:fixed;right:16px;top:12px;z-index:5;font:inherit;font-size:13px;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--text);cursor:pointer}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{display:none}main{padding:24px 16px 80px}.grid2{grid-template-columns:1fr}}
"""

JS = """
const tip=document.getElementById('tip');
document.addEventListener('mousemove',e=>{const t=e.target.closest('[data-tip]');if(!t){tip.style.display='none';return}
tip.innerHTML=t.getAttribute('data-tip');tip.style.display='block';tip.style.left=Math.min(e.clientX+14,innerWidth-360)+'px';tip.style.top=(e.clientY+14)+'px'});
const tb=document.querySelector('.theme');const set=t=>{t==='auto'?document.documentElement.removeAttribute('data-theme'):document.documentElement.setAttribute('data-theme',t);tb.textContent={auto:'◐ Auto',light:'☀ Light',dark:'☾ Dark'}[t]};
let th='auto';try{th=localStorage.getItem('docs-theme')||'auto'}catch(e){}set(th);
tb.onclick=()=>{th={auto:'light',light:'dark',dark:'auto'}[th];set(th);try{localStorage.setItem('docs-theme',th)}catch(e){}};
"""


def table(header, rows, num=()) -> str:
    h = "".join(f"<th>{E(str(x))}</th>" for x in header)
    b = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{x}</td>' for i, x in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def pick_example(lectures: list[dict]) -> dict:
    def score(l):
        ph = l["phases"]
        return (len(ph[0]["recall"]) > 0) * 3 + len({q["question_type"] for q in ph[-1]["open_questions"]}) + \
            sum(1 for p in ph if p["type"] == "active" for q in p["quiz"]["items"] if q.get("interleaved_from"))
    return max(lectures[1:] or lectures, key=score)


def build(root: Path = HERE) -> Path:
    from pipeline import prompts as P
    courses = load(root)
    out = root / "docs" / "pipeline.html"
    out.parent.mkdir(exist_ok=True)
    S, NAV = [], []

    ORDER = ["overview", "running", "config", "agents", "representation", "graph", "inference", "stages",
             "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "cost-", "lir", "viewer", "files"]

    def rank(id_):
        return next(i for i, p in enumerate(ORDER) if id_ == p or (p.endswith("-") and id_.startswith(p)))

    def sec(id_, title, body, sub=False):
        NAV.append((rank(id_), len(NAV), f'<a href="#{id_}" class="{"sub" if sub else ""}">{E(title)}</a>'))
        S.append((rank(id_), len(S), f'<section id="{id_}">' + (f"<h3>{E(title)}</h3>" if sub else f"<h2>{E(title)}</h2>") + body + "</section>"))

    # ---- overview
    tot_lec = sum(len(c["lectures"]) for c in courses)
    tot_h = sum(l["duration_s"] for c in courses for l in c["lectures"]) / 3600
    tiles = (f'<div class="tiles"><div class="tile"><b>{len(courses)}</b><span>courses built</span></div>'
             f'<div class="tile"><b>{tot_lec}</b><span>lectures</span></div><div class="tile"><b>{tot_h:.1f} h</b><span>of video</span></div>'
             f'<div class="tile"><b>{sum(len(c["course"]["concepts"]) for c in courses)}</b><span>concepts in the registries</span></div>'
             + "".join(f'<div class="tile"><b>{c["timing"]["pipeline_wall_s"] / 60 / max(1, len(c["lectures"])):.1f} min</b>'
                       f'<span>per lecture · {E(c["course"]["course_id"])}</span></div>' for c in courses if c["timing"]) + "</div>")
    sec("overview", "Overview", f"""
<p>The pipeline compiles one course at a time. Subtitle files and lecture titles go in; one <b>LIR</b> (Lecture
Intermediate Representation) file per lecture and one course file come out, plus the downloaded videos. A viewer
renders the LIR as a guided course: a primer before each lecture, the lecture in short segments, a quiz and summary
after each segment, and a concept map and open questions at the end. Nothing at viewing time calls an LLM; the only
model used there is a small sentence-embedding model on the CPU, for scoring open answers.</p>{tiles}
<h3>Five principles</h3><ul>
<li><b>Narrow calls for a small model.</b> Each LLM call does one job on a short input (a segment, not a lecture, where possible), and its output is constrained to a JSON schema.</li>
<li><b>The LLM proposes, code decides.</b> The model extracts and writes text. Code merges, assigns timestamps, enforces counts, picks activity types by rule and places the correct answer. The model never writes a timestamp or a pointer.</li>
<li><b>Everything cites the transcript.</b> Every generated item carries the sentence IDs it came from.</li>
<li><b>Intent is recorded, not implied.</b> Every phase and item carries the learning principle it serves, its ICAP mode, its Bloom level, and the rule that chose it.</li>
<li><b>Stages, not autonomous agents.</b> Each stage runs over all lectures as one batch before the next stage starts.</li></ul>
<h3>Architecture</h3>{ARCH}
<p class="note">Stage 4 is the only step that walks the course in lecture order; its LLM calls are still batched for the
whole course, and the registry is built by code in order. Validation layers 1 and 2 run inside every stage; layer 3
(the judge) is stage 6. Videos download on a background thread for the whole run.</p>""")

    # ---- running
    sec("running", "Running it", """
<pre>cd lir-construction
python3 generate_lir.py --lecture ../dataset/virtual_and_augmented_reality      # whole course, ready to view
python3 generate_lir.py --lecture ../dataset/mit_6_7960_deep_learning --only 1-3
python3 generate_lir.py --lecture ... --lir-only        # no videos
python3 generate_lir.py --lecture ... --videos-only     # only the videos
python3 serve.py                                         # viewer at http://localhost:8000</pre>
<p>The terminal shows color-coded progress: an overall bar with an ETA (weighted by how long each stage usually
takes, and refined from earlier runs), a bar for the current batch of calls with tokens per second and retries, and
the video downloads with speed and ETA. A rerun reuses every cached LLM answer whose prompt did not change.</p>""" +
        table(["Folder", "Contents"], [
            ["<code>lir/&lt;course&gt;/</code>", "the LIR: <code>course.json</code>, <code>L01.json</code>… (edit these for a final review)"],
            ["<code>lir/index.json</code>", "the list of built courses, for the viewer"],
            ["<code>media/&lt;course&gt;/</code>", "videos, <code>Lxx.mp4</code>"],
            ["<code>output/&lt;course&gt;/</code>", "build files: <code>timing_report.md</code>, <code>timing.json</code>, <code>cache/</code> (every LLM answer), <code>stages/</code>, <code>state/state_Lxx.json</code>, <code>logs/</code>"],
            ["<code>docs/pipeline.html</code>", "this page, rebuilt after every run"]]))

    # ---- configuration
    import docs_formal as F
    ledger = json.loads((root / "api_spend.json").read_text()) if (root / "api_spend.json").exists() else None
    cfg_path = root / "lir_config.toml"
    sec("config", "Configuration: choosing the models", F.section_config(cfg_path.read_text() if cfg_path.exists() else "", ledger))

    # ---- inference
    sec("inference", "How inference runs", f"""
<p>Both models run in <code>llama-server</code> (llama.cpp) inside the <code>llm-engine</code> toolbox, started and
stopped by the pipeline. Only one fits on the 12 GB card at a time, so the pipeline swaps them: the generator runs
stages 1–5, the judge takes over for stage 6, the generator comes back for repairs, and so on.</p>""" +
        table(["", "Generator", "Judge"], [
            ["Model", "Gemma 4 E4B-it", "Gemma 4 12B-it (QAT)"],
            ["Weights", "Q8 GGUF (<code>UD-Q8_K_XL</code>, 8.7 GB)", "4-bit QAT GGUF (<code>UD-Q4_K_XL</code>, 6.7 GB)"],
            ["KV cache", "f16, not quantized; one 131,072-token pool shared by all slots", "f16; 65,536-token pool"],
            ["Parallel slots", "32 (continuous batching)", "16"],
            ["Thinking", "on for every call", "on for every call"],
            ["Sampling", "temperature 0, seed 0", "temperature 0, seed 0"],
            ["Output", "constrained to each call's JSON schema (llama.cpp grammar)", "same"],
            ["GPU memory in use", "9.7 GB at 32 slots", "—"]]) + f"""
<h3>Batching</h3>
<p>Each stage sends every prompt for every lecture at once. The client keeps up to 32 requests in flight; the
server's continuous batching decodes them together. Because the KV pool is shared, the client also caps the tokens
in flight (prompt plus expected output) at 85% of the pool, so several long lectures segmented at once cannot
overflow it. Prompts that share a prefix reuse the server's prompt cache: segment-level prompts are ordered role
line → segment transcript → task, so the annotation, quiz, summary and question calls on one segment share their
transcript prefix.</p>
<div class="grid2"><div>{bench_chart()}<p class="note">Output tokens per second with thinking on, 64–128 annotation-style
calls on Deep Learning transcript segments. Throughput peaks at 32 slots, the default.</p></div>
<div><h3 style="margin-top:0">Why not vLLM</h3><p>vLLM is installed and wired in (<code>--engine vllm</code>), but
Gemma's E4B carries 3.5 B parameters of embedding tables (per-layer embeddings) that vLLM keeps in bf16, about 7 GB.
With FP8 transformer layers the model alone needs about 11 GB of the 12 GB card, leaving no room for the KV cache.
The Q8 GGUF stores those tables in 8 bits and fits with 2.5 GB to spare.</p></div></div>
<h3>Caching and cost logging</h3>
<p>Every answer is written to <code>output/&lt;course&gt;/cache/&lt;stage&gt;.jsonl</code>, keyed by a hash of the model, prompt,
schema and settings; a rerun after a prompt change recomputes only that stage. Every call logs its input and
output tokens and latency; the per-lecture cost in the report splits each stage's wall time over lectures by how
long their calls held a slot.</p>""")

    # ---- stages with real examples
    if courses:
        c0 = courses[0]
        ex = pick_example(c0["lectures"])
        seg = max(ex["segments"], key=lambda s: len(s["key_terms"]) + len(s["key_points"]))
        human = None
        hp = root.parent / "lec1__P01__both.json"
        if hp.exists() and c0["course"]["course_id"].startswith("nptel-virtual"):
            human = {"lecture_id": "L01", "coarse": json.loads(hp.read_text())["boundaries"]["coarse"]}
        sec("stages", "The stages, with a real example", f"""<p>Examples below come from
<b>{E(c0['course']['title'])}</b>, lecture <b>{E(ex['lecture_id'])} · {E(ex['title'])}</b>, as built. Each stage's prompt is
shown in full under “Prompt”.</p>""")

        def prompt_box(p):
            return f"<details><summary>Prompt <code>{E(p[0])}</code> v{E(p[1])}</summary><pre>{E(p[2])}</pre></details>"

        sec("s0", "0 · Transcripts", """<p>Each subtitle file is parsed into cues, cleaned of sound tags
(<code>[SQUEAKING]</code>), speaker labels (<code>SARA BEERY:</code>) and the OCW licence notice, and merged into sentences:
a cue that ends mid-sentence joins the next. Every sentence keeps its start and end time and gets an ID; every later
item cites these IDs. Lectures with no subtitle file (VR lectures 4 and 5) take the official NPTEL transcript and
align its words to YouTube's automatic captions, which time every word, so the sentences keep the clean
punctuation and get accurate times.</p>""", True)
        sec("s1", "1 · Segment", f"""<p>One call per lecture with the best prompt from the segmentation study
(<code>event-segmentation/compare/REPORT.md</code>: WindowDiff 0.09 against the human annotator, versus 0.28 for TextTiling).
The model sees the numbered transcript and returns the sentence numbers that start a segment. Code then sorts them,
merges segments under 2 minutes into the shorter neighbour, and flags segments over 12 minutes. Lectures over 28k
prompt tokens are segmented in overlapping windows of 300 sentences.</p>{prompt_box(P.SEGMENT)}
<p>Every lecture's segments, colored by content type{' (with the human annotator’s coarse boundaries for L01: black ticks; dots are the pipeline’s cuts)' if human else ''}:</p>
{timeline_chart(c0['lectures'], human)}""", True)
        kps = "".join(f"<li>{E(k['text'])} <span class='note'>[{', '.join(map(str, k['sentence_ids']))}]</span></li>" for k in seg["key_points"])
        terms = "".join(f"<li><b>{E(t['term'])}</b>: {E(t['definition'])}</li>" for t in seg["key_terms"])
        sec("s2", "2 · Annotate", f"""<p>Two narrow calls per segment. The first writes the sub-goal (verb first), the
content type (one of ten) and 2–5 key points, each one atomic statement with its sentence IDs. The second lists key
terms with definitions and the sentences that define them, plus concepts the segment uses without defining. Code
checks that every cited ID is inside the segment, that the sub-goal starts with an allowed verb, and that each term
actually occurs in its cited sentences.</p>
<div class="card"><b>{E(ex['lecture_id'])} {E(seg['id'])}</b> <span class="tag">{E(seg['content_type'].replace('_', ' '))}</span>
<span class="tag">{clock(seg['start'])}–{clock(seg['end'])}</span><p><b>Sub-goal:</b> {E(seg['subgoal'])}</p>
<b>Key points</b><ul>{kps}</ul>{('<b>Key terms</b><ul>' + terms + '</ul>') if terms else ''}</div>
{prompt_box(P.ANNOTATE)}{prompt_box(P.TERMS)}""", True)
        objs = "".join(f"<li>{E(o['text'])} <span class='note'>({', '.join(o['segment_ids'])})</span></li>" for o in ex["roadmap"]["objectives"])
        cg = "".join(f"<li>{E(g['text'])} <span class='note'>({', '.join(g['lecture_ids'])})</span></li>" for g in c0["course"]["course_goals"])
        sec("s3", "3 · Goal hierarchy", f"""<p>A tiny call per lecture: only the title and the list of sub-goals go in. Out
come 2–6 objectives, each a contiguous run of segments, phrased as “You'll be able to …”, and one lecture goal. Code
checks every segment is in exactly one objective and the runs are contiguous. Course goals are built bottom-up from
the lecture goals in one more call.</p><div class="card"><b>{E(ex['lecture_id'])} goal:</b> {E(ex['roadmap']['lecture_goal'])}<ul>{objs}</ul>
<b>Course goals</b><ul>{cg}</ul></div>{prompt_box(P.GOALS)}""", True)
        rel_counts = {}
        for e in c0["course"]["edges"]:
            rel_counts[e["rel"]] = rel_counts.get(e["rel"], 0) + 1
        sec("s4", "4 · Course knowledge state", f"""<p>The registry is what makes cross-lecture links possible. For each lecture in
order, terms are canonicalized against it: same normalized name, an alias such as “(AR)”, or an acronym that spells
another name's initials is the same concept; otherwise embedding similarity decides (≥ 0.93 same, 0.78–0.93 a yes/no
LLM call, below that a new concept). Concepts only used, never defined, join an existing concept or are dropped.
One call per lecture then extracts typed edges (prerequisite of, part of, example of, contrasts with, leads to, used
in), each with a link phrase and evidence sentence IDs. Finally <code>state[k]</code> is saved: the registry and edges as of
lecture k. Anything generated for lecture k reads only <code>state[k]</code>; the primer reads <code>state[k−1]</code>.</p>
<div class="tiles"><div class="tile"><b>{len(c0['course']['concepts'])}</b><span>concepts</span></div><div class="tile"><b>{len(c0['course']['edges'])}</b><span>edges</span></div>
{''.join(f'<div class="tile"><b>{v}</b><span>{E(k.replace("_", " "))}</span></div>' for k, v in sorted(rel_counts.items(), key=lambda x: -x[1]))}</div>
{concept_graph(c0['course'])}{prompt_box(P.SAME_CONCEPT)}{prompt_box(P.EDGES)}""", True)

        primer = ex["phases"][0]
        active = next(p for p in ex["phases"] if p["type"] == "active" and p["segment_id"] == seg["id"])
        cons = ex["phases"][-1]
        quiz_html = ""
        for q in active["quiz"]["items"][:2]:
            opts = "".join(f'<div class="opt {"ok" if i == q["correct_index"] else ""}">{"✓" if i == q["correct_index"] else "·"} {E(o)} '
                           f'<span class="note">— {E(q["explanations"][i])}</span></div>' for i, o in enumerate(q["options"]))
            quiz_html += (f'<div class="card"><span class="tag">{E(q["item_type"].replace("_", " "))}</span>'
                          + (f'<span class="tag">review from {E(q["interleaved_from"]["lecture_id"])}</span>' if q.get("interleaved_from") else "")
                          + f'<p><b>{E(q["stem"])}</b></p>{opts}<p class="note">intent: {E(q["intent"]["rule_id"])} · {E(q["intent"]["rationale"])}</p></div>')
        recall_html = "".join(f'<li><b>{E(r["question"])}</b><br>{E(r["recap"])} <span class="note">→ {E(r["jump_to"]["lecture_id"])} {clock(r["jump_to"]["t"])} · {E(r["intent"]["rationale"])}</span></li>' for r in primer["recall"])
        oq = cons["open_questions"][0] if cons["open_questions"] else None
        oq_html = ""
        if oq:
            kp = "".join(f"<li>{E(k['text'])} <span class='note'>keywords: {E(', '.join(k['keywords']))}</span></li>" for k in oq["key_points"])
            oq_html = (f'<div class="card"><span class="tag">{E(oq["question_type"].replace("_", " "))}</span><span class="tag">{E(oq["intent"]["rule_id"])}</span>'
                       f'<p><b>{E(oq["prompt"])}</b></p><p class="note">{E(oq["intent"]["rationale"])}</p><p><b>Reference answer.</b> {E(oq["reference_answer"])}</p><b>Key points</b><ul>{kp}</ul></div>')
        oq_rules = table(["If the lecture has…", "Question type", "Principle"], [
            ["a derivation or procedure segment", "fill in missing steps", "worked-example completion"],
            ["a contrasts-with edge or a comparison segment", "compare and contrast", "elaboration"],
            ["a mechanism-explanation segment", "self-explanation (why or how)", "self-explanation"],
            ["a worked-example or application segment", "apply to a new case", "transfer"],
            ["a procedure with a failure mode in the transcript", "troubleshooting", "elaboration, transfer"],
            ["always (fallback)", "explain it to someone else", "generative learning"]])
        sec("s5", "5 · Generate the components", f"""<p>Most of each component is assembled by code from stages 2–4; the LLM
writes only the wording. All calls for all lectures go out as one batch.</p>
<h3>Primer</h3><p>Objectives from stage 3; new key terms (introduced in this lecture, ranked by salience, at most 8);
recall items: for each new concept, code follows prerequisite-of and used-in edges back to earlier concepts in
<code>state[k−1]</code>, keeps up to 4, and one call writes a recall question and recap for each. Code attaches the jump
link.</p>{('<div class="card"><ul>' + recall_html + '</ul></div>') if recall_html else '<p class="note">(No recall items in this lecture.)</p>'}
{prompt_box(P.RECALL)}
<h3>Quiz (after each segment)</h3><p>Code assigns each of the 4 items a target key point and fixes the types (2
multiple choice, 1 true/false, 1 yes/no). It also fixes the true/false and yes/no answers and, after generation,
shuffles where the correct option goes. One item per quiz may review a concept from an earlier lecture that this
segment builds on (interleaving).</p>{quiz_html}{prompt_box(P.QUIZ)}
<h3>Summary</h3><p>A 2–3 sentence recap (one small call); key concepts with on-click explanations (registry
definitions, or generated for concepts without one); key terms; links to earlier concepts with edges into the
segment; the learner's highlights.</p><div class="card">{E(active['summary']['recap'])}
<p class="note">{len(active['summary']['key_concepts'])} key concepts · {len(active['summary']['earlier_links'])} earlier links</p></div>{prompt_box(P.SUMMARY)}
<h3>Concept-map task</h3><p>Built by code only. The reference map is this lecture's concepts plus earlier concepts one
edge away; the seeds are the lecture's 4 most salient concepts plus up to 2 earlier anchors.</p>
<div class="card">Seeds: {', '.join(E(s['name']) for s in cons['concept_map']['seeds'])}<br>
<span class="note">reference: {len(cons['concept_map']['reference_nodes'])} concepts, {len(cons['concept_map']['reference_edges'])} links</span></div>
<h3>Open questions</h3><p>Code picks 4 question types from the rule table (best-matching distinct types first), then one
call per question writes the prompt, a reference answer and 3–5 key points with keywords. The rule that fired is
stored in the item's intent.</p>{oq_rules}{oq_html}{prompt_box(P.OPEN_Q)}""", True)

        # validation
        judge_all, resolved = {}, []
        for c in courses:
            for k, v in (c["timing"] or {}).get("judge", {}).items():
                for kk, vv in v.items():
                    judge_all.setdefault(k, {}).setdefault(kk, 0)
                    judge_all[k][kk] += vv
            for l in c["lectures"]:
                resolved += [(l["lecture_id"], r) for r in l.get("quality", {}).get("resolved_by_code", [])]
        pass_rows = []
        for c in courses:
            for p in (c["timing"] or {}).get("pass_rates", []):
                pass_rows.append([E(c["course"]["course_id"]), E(p["stage"]), p["items"], p["passed_first"], p["passed_after_retry"], p["failed"]])
        res_html = "".join(f"<li><b>{E(lid)}</b> {E(r['item'])}: <i>{E(r['reason'])}</i> → {E(r['action'])}</li>" for lid, r in resolved[:12])
        sec("s6", "6 · Validation: three layers", f"""<p><b>Layer 1</b> is constrained decoding: every call's output must
match its JSON schema, so counts (exactly 4 quiz items), enums and length limits always hold. <b>Layer 2</b> is code
checks after each call (cited IDs inside the segment, verb-first goals, contiguous objectives, distinct options, a
correct option not much longer than the rest, keywords present in the reference answer, no concept from a later
lecture, recall pointing only backwards). A failed check is sent back with the error appended to the prompt, up to
2 retries.</p>{table(["Course", "Stage", "Items", "Passed first time", "Passed after retry", "Resolved by code"], pass_rows, (2, 3, 4, 5)) if pass_rows else ''}
<p><b>Layer 3</b> is the judge: Gemma 4 12B, larger than the generator, checks every item with the design doc's
questions. Is each quiz item answerable from the segment alone, and is the marked answer right (and the only right
one)? Is each definition faithful to its cited sentences? Does the sub-goal describe the segment? It also checks
summaries, open questions, recall items and edges. A rejected item goes back to the generator with the judge's
reason (up to 2 rounds) and is judged again. Whatever still fails is resolved by code: quiz items, questions,
recall items, edges and terms are dropped; a summary falls back to the segment's key points. Nothing is left for a
human except a final review of the LIR.</p>{judge_chart(judge_all) if judge_all else '<p class="note">(No judged run yet.)</p>'}
{('<details><summary>Examples of items resolved by code</summary><ul>' + res_html + '</ul></details>') if res_html else ''}""", True)
        sec("s7", "7 · Assemble the LIR", """<p>No LLM calls. Code builds the lecture and course files, runs the
leakage check, validates both against the Pydantic schema (<code>lir_schema.py</code>), and stores the embeddings the
runtime scorer needs: one per open-question key point, one per concept.</p>""", True)

        # per-lecture charts
        for c in courses:
            if not c["timing"]:
                continue
            t = c["timing"]
            rows = [[E(r["lecture_id"]), E(r["title"]), r["video_min"], r["segments"], r["llm_calls"], f'{r["output_tokens"]:,}',
                     r["processing_min"], r["processing_min_per_video_hour"]] for r in t["lectures"]]
            sec(f"cost-{c['course']['course_id']}", f"Time per lecture: {c['course']['title']}", f"""
<p>{len(t['lectures'])} lectures, {t['video_s'] / 60:.0f} min of video, built in {t['pipeline_wall_s'] / 60:.1f} min
(<b>{t['pipeline_wall_s'] / 60 / max(1, len(t['lectures'])):.1f} min per lecture</b>,
{t['pipeline_wall_s'] / 60 / (t['video_s'] / 3600):.1f} min per hour of video). Each lecture's time is its share of every
stage's wall time, in proportion to how long its calls held a server slot.</p>{stacked_time_chart(t)}
<details><summary>Table view</summary>{table(["Lecture", "Title", "Video (min)", "Segments", "LLM calls", "Output tokens", "Processing (min)", "min / video hour"], rows, (2, 3, 4, 5, 6, 7))}</details>""")

        # formal sections: division of work, lecture representation, graph representation
        import docs_formal as F
        sec("agents", "Who does what: the division of work", F.section_workers(c0["timing"]))
        sec("representation", "How a lecture is represented", F.section_representation(ex))
        sec("graph", "The graph representation", F.section_graph(c0["course"], c0["lectures"], ex))

        # LIR structure
        sample = json.loads(json.dumps(ex))
        sample["sentences"] = sample["sentences"][:2] + ["…"]
        sample["segments"] = sample["segments"][:1] + ["…"]
        for k in ("phases",):
            sample[k] = [sample[k][0] | {"recall": sample[k][0]["recall"][:1], "key_terms": sample[k][0]["key_terms"][:2]},
                         sample[k][1], {**sample[k][2], "quiz": {"items": sample[k][2]["quiz"]["items"][:1]}}, "…"]
        sample["origin"] = sample["origin"][:1] + ["…"]
        txt = json.dumps(sample, indent=1, ensure_ascii=False)
        sec("lir", "The LIR files", f"""<p>Two kinds of JSON file. <code>course.json</code> holds the lecture list, course goals,
the concept registry (name, aliases, definition, where introduced, every mention, salience), the edges with evidence,
and the concept embeddings. Each <code>Lxx.json</code> holds the sentences with timestamps, the roadmap, the segments and
an ordered list of <b>phases</b>: any UI, or a VR environment, renders a lecture by walking the list and drawing each
phase by its <code>type</code> (<code>primer</code>, <code>segment</code>, <code>active</code>, <code>constructive</code>).</p>
<p><b>Intent</b> on every phase and item: <code>principle</code>, <code>icap_mode</code>, <code>bloom_level</code>, <code>rule_id</code>,
<code>rationale</code>, <code>sources</code>. <b>Origin</b>, one record per generated item: model, engine, prompt ID and version, input
hash, validator result, retries, tokens, latency. <b>Quality</b>: the judge's results per check. The full definitions
are in <code>lir_schema.py</code>.</p><details><summary>Trimmed example: {E(ex['lecture_id'])}.json</summary><pre>{E(txt[:12000])}</pre></details>""")

    # viewer & scoring
    sc = courses[0]["lectures"][0]["scoring"]["open_answer"] if courses else {}
    sec("viewer", "The viewer and runtime scoring", f"""<p><code>python3 serve.py</code> serves the viewer at
<code>http://localhost:8000</code>. The home page shows the course goals and the full roadmap (lectures → objectives →
segments, with progress) and a Start button; the whole course LIR is loaded at once. A lecture walks its phases:
the primer, then each segment's video (local file, seeking supported; optional captions with the current
sentence highlighted; click to jump, double-click to highlight), then its quiz and summary, and finally the concept
map and open questions. Highlights resurface in the segment summary and at the end of the lecture. Progress and
answers are kept in the browser.</p>
<h3>Scoring open answers (CPU)</h3><p>An answer is scored against the question's key points, not one ideal answer.
A key point counts as covered if the answer contains at least <b>m</b> words of its keyword set (stemmed, with WordNet
synonyms), or if some sentence of the answer has cosine similarity ≥ <b>τ</b> with the key point (the key-point
embeddings are stored in the LIR; only the learner's sentences are embedded at runtime, on the CPU). The share
covered gives the tier: <b>Excellent</b> ≥ 0.75, <b>Good</b> ≥ 0.5, <b>Acceptable</b> ≥ 0.25, else <b>Try again</b>. The
feedback names the tier, gives a hint from one missed key point, lists the covered and missed key points, and lets
the learner revise before revealing the reference answer.</p>
<p>m and τ are calibrated without a human: the generator writes a good, a partial and a wrong answer to a sample of
questions, and code grid-searches m and τ so good answers land at ≥ 0.75, partial ones in [0.25, 0.75) and wrong
ones below 0.25. Current setting: <b>m = {sc.get('m', '?')}, τ = {sc.get('tau', '?')}</b>{(f", {sc['agreement']:.0%} agreement on {sc['answers']} answers; mean score: " + ', '.join(f'{k} {v}' for k, v in sc.get('mean_score_by_label', {}).items())) if sc.get('calibrated') else ''}.</p>
<h3>Scoring concept maps</h3><p>Each learner concept is matched to a registry concept by name or alias first, then by
embedding similarity. A learner link matches a reference edge if it joins the same two concepts; a similar label
earns a bonus. The score is the share of the reference edges among the learner's matched concepts that were found.
Links not in the reference are marked, not penalized; the reference map can be shown at any time.</p>""")

    sec("files", "Code map", table(["File", "What it does"], [
        ["<code>generate_lir.py</code>", "the one command: videos, stages 0–7, docs, report"],
        ["<code>pipeline/transcript.py</code>", "course discovery, SRT → sentences"],
        ["<code>pipeline/media.py</code>", "video downloads (yt-dlp), caption alignment"],
        ["<code>pipeline/llm.py</code>", "server launcher (generator, judge), batching client, cache, token budget, cost log"],
        ["<code>pipeline/prompts.py</code>", "every prompt, with ID and version"],
        ["<code>pipeline/s1_segment.py</code> … <code>s7_assemble.py</code>", "the stages"],
        ["<code>pipeline/s6_judge.py</code>", "layer-3 judge, repairs, resolution by code"],
        ["<code>pipeline/calibrate.py</code>", "m and τ calibration"],
        ["<code>pipeline/validate.py</code>", "layer-2 checks"],
        ["<code>pipeline/ui.py</code>, <code>pipeline/report.py</code>", "terminal progress, timing and quality report"],
        ["<code>lir_schema.py</code>", "Pydantic LIR v0"],
        ["<code>scorer.py</code>, <code>serve.py</code>, <code>viewer/</code>", "runtime scoring and the viewer"],
        ["<code>build_docs.py</code>", "this page"]]))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LIR Pipeline</title><style>{CSS}</style></head><body>
<button class="theme" type="button">◐ Auto</button><div id="tip"></div>
<div class="layout"><nav><b style="display:block;margin:0 8px 12px">LIR pipeline</b>{''.join(x[2] for x in sorted(NAV))}</nav>
<main><h1>Lecture planner: how the LIR is built</h1><p class="lead">From subtitle files to a guided, checked, ready-to-view course,
on one 12 GB GPU. Generated {time.strftime('%Y-%m-%d %H:%M')} from the current outputs.</p>{''.join(x[2] for x in sorted(S))}</main></div>
<script>{JS}</script></body></html>"""
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build(HERE))
