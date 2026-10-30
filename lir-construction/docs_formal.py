"""Formal sections of docs/pipeline.html: the division of work, the lecture representation, the graph representation.

Used by build_docs.py; every figure is drawn from the built LIR and timing files.
"""
from __future__ import annotations

import html
import math

E = html.escape

ICAP_SLOT = {"passive": 1, "active": 2, "constructive": 3}


def _clock(t: float) -> str:
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


# ------------------------------------------------------------------ 1. who does what
WORKERS = [
    ("Code", "deterministic rules in Python: parsing, merging, counts, IDs, timestamps, choice of activity types, "
             "answer positions, graph building, checks, assembly"),
    ("Generator · Gemma 4 E4B (Q8)", "proposes text: boundaries, sub-goals, key points, terms, objectives, edges, "
                                     "quiz items, recaps, questions, recall items, repairs"),
    ("Judge · Gemma 4 12B (QAT Q4)", "verifies text: answers yes/no with a reason for every generated item"),
    ("Embedder · all-mpnet-base-v2 (CPU)", "vectors for concept matching, edge retrieval, key-point scoring"),
    ("Video worker · yt-dlp thread", "downloads the lecture videos in parallel with everything else"),
]
STAGE_WORK = [
    # stage, code, generator, judge, embedder
    ("transcripts", "parse SRT, clean, merge cues into sentences, align no-SRT lectures to captions", "", "", ""),
    ("stage1_segment", "number sentences; sort boundaries; merge &lt; 2 min; flag &gt; 12 min; windows for long lectures",
     "boundary sentence numbers (1 call / lecture)", "", ""),
    ("stage2_annotate", "check IDs inside segment, verb-first sub-goal, term occurs in cited sentences; retry with errors",
     "sub-goal, content type, key points; key terms + used concepts (2 calls / segment)", "", ""),
    ("stage3_goals", "check every segment in exactly one contiguous objective; prefix “You'll be able to”",
     "objectives + lecture goal (1 / lecture); course goals (1 / course)", "", ""),
    ("stage4_course_state", "normalize names, aliases, acronyms; union-find over term groups; registry; salience; "
                            "snapshots state[k]", "same-concept yes/no (middle band only); typed edges (1 / lecture)",
     "", "term vectors for the similarity bands; retrieval of earlier concepts"),
    ("stage5_generate", "pick quiz targets, item types, T/F and Y/N answers, option order; pick question types from "
                        "the rule table; build concept maps; attach jump links",
     "recall items; quiz (1 / segment); recap (1 / segment); open questions (4 / lecture)", "", ""),
    ("stage6_calibrate", "grid-search m and τ against the intended labels", "good / partial / wrong sample answers",
     "", "answer sentences vs key points"),
    ("stage6_judge", "route failures; apply repairs; drop or replace what still fails; rebuild derived parts",
     "repairs with the judge's reason (≤ 2 rounds)", "verdicts on every item (1 call / segment, / question, / lecture)",
     ""),
    ("stage7_assemble", "leakage check, schema validation, write files", "", "", "key-point and concept vectors"),
]


def swimlane(timing: dict) -> str:
    """Which worker is busy in which stage, on the run's real time axis."""
    stages = [s for s in timing["stages"]]
    total = sum(s["wall_s"] for s in stages) or 1
    lanes = ["Code", "Generator (E4B)", "Judge (12B)", "Embedder (CPU)", "Videos"]
    W, left, laneh = 900, 120, 26
    H = laneh * len(lanes) + 34
    out = []
    for i, name in enumerate(lanes):
        y = i * laneh
        out.append(f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" class="ax">{name}</text>'
                   f'<line x1="{left}" x2="{W}" y1="{y + laneh}" y2="{y + laneh}" class="grid"/>')
    x = left
    for s in stages:
        w = s["wall_s"] / total * (W - left)
        models = " ".join(s.get("models", []))
        active = [0]
        if "E4B" in models:
            active.append(1)
        if "12B" in models:
            active.append(2)
        if s["stage"] in ("stage4_course_state", "stage6_calibrate", "stage7_assemble"):
            active.append(3)
        for lane in active:
            out.append(f'<rect x="{x + 1:.1f}" y="{lane * laneh + 5}" width="{max(1.5, w - 2):.1f}" height="{laneh - 10}" '
                       f'rx="3" fill="var(--s{lane + 1})" data-tip="{E(s["stage"])} · {s["wall_s"]:.0f} s · '
                       f'{s["calls"]} LLM calls"/>')
        if w > 34:
            out.append(f'<text x="{x + w / 2:.1f}" y="{H - 6}" text-anchor="middle" class="ax">{E(s["stage"].split("_")[0].replace("stage", "S"))}</text>')
        x += w
    out.append(f'<rect x="{left + 1}" y="{4 * laneh + 5}" width="{W - left - 2}" height="{laneh - 10}" rx="3" fill="var(--s5)" '
               f'fill-opacity=".55" data-tip="video downloads run on a background thread for the whole run"/>')
    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Who works when">{"".join(out)}</svg>'
            f'<p class="note">Time runs left to right, scaled to this run\'s real stage durations ({total / 60:.1f} min). '
            f'Only one model is on the GPU at a time, so the generator and judge lanes never overlap.</p>')


def section_workers(timing: dict | None) -> str:
    rows = "".join(f"<tr><td><b>{E(n)}</b></td><td>{d}</td></tr>" for n, d in WORKERS)
    calls = {s["stage"]: s for s in (timing or {}).get("stages", [])}
    srows = ""
    for st, code, gen, judge, emb in STAGE_WORK:
        c = calls.get(st)
        n = f'{c["calls"]:,}' if c else "–"
        srows += (f"<tr><td><code>{E(st)}</code></td><td>{code}</td><td>{gen or '–'}</td><td>{judge or '–'}</td>"
                  f"<td>{emb or '–'}</td><td class='n'>{n}</td></tr>")
    return f"""
<p>The word “agent” here means a <b>stage worker</b>, not an autonomous agent: a fixed role with a narrow contract,
called by the stage runner in a fixed order. No worker decides what to do next. Five workers share the run:</p>
<table><thead><tr><th>Worker</th><th>Role</th></tr></thead><tbody>{rows}</tbody></table>
<p>The contract between them is <b>propose / decide / verify</b>. The generator proposes text inside a JSON schema;
code decides everything structural (what to ask, how many, where the correct answer goes, which IDs and times
apply); the judge verifies the text, and code routes its verdicts. A model never writes a timestamp, an ID, a
pointer or a count.</p>
<h3>Division of work per stage</h3>
<table><thead><tr><th>Stage</th><th>Code decides</th><th>Generator proposes</th><th>Judge verifies</th><th>Embedder</th><th>LLM calls (this run)</th></tr></thead>
<tbody>{srows}</tbody></table>
{swimlane(timing) if timing else ''}
<h3>Scheduling</h3>
<p>Every stage is a <b>barrier</b>: it sends all of its calls for all lectures, waits for all of them, and only then
does the next stage start. Inside a stage the calls are independent, so the client keeps up to <i>n</i> requests in
flight (32 for the generator, 8 for the judge), subject to a token budget of 85% of the server's KV pool. Retries for
failed layer-2 checks go back into the same batch. Stage 4 is the one place where order matters: its LLM calls are
batched for the whole course, but code then walks the lectures in order to build the registry, so nothing in
<code>state[k]</code> depends on a later lecture. Stage 6 alternates the two models on the GPU: judge all items →
repair the failures → judge the repairs → …, at most two repair rounds.</p>"""


# ------------------------------------------------------------------ 2. lecture representation
def goal_tree(lec: dict) -> str:
    """Lecture goal → objectives → segments (sub-goals) → key points, drawn as a left-to-right tree."""
    segs = {s["id"]: s for s in lec["segments"]}
    rows = []
    for o in lec["roadmap"]["objectives"]:
        for sid in o["segment_ids"]:
            rows.append((o, segs[sid]))
    W, rowh = 900, 30
    H = max(80, rowh * len(rows) + 10)
    x0, x1, x2, x3 = 10, 220, 470, 820
    out = [f'<g class="box"><rect x="{x0}" y="{H / 2 - 30:.0f}" width="190" height="60" rx="10"/>'
           f'<text x="{x0 + 95}" y="{H / 2 - 4:.0f}" text-anchor="middle" class="bt">Lecture goal</text>'
           f'<text x="{x0 + 95}" y="{H / 2 + 14:.0f}" text-anchor="middle" class="bs">{E(lec["lecture_id"])}</text></g>']
    y = 5
    oy = {}
    for i, (o, s) in enumerate(rows):
        cy = y + rowh / 2
        oy.setdefault(o["id"], []).append(cy)
        out.append(f'<line x1="{x2 - 4}" x2="{x2 + 6}" y1="{cy:.0f}" y2="{cy:.0f}" class="grid"/>'
                   f'<rect x="{x2 + 6}" y="{y + 3}" width="{x3 - x2 - 16}" height="{rowh - 6}" rx="6" fill="var(--s{1 + (int(o["id"][1:]) - 1) % 6})" fill-opacity=".16" '
                   f'data-tip="{E(s["id"])} · {_clock(s["start"])}–{_clock(s["end"])} · {E(s["content_type"])}<br>{E(s["subgoal"])}"/>'
                   f'<text x="{x2 + 14}" y="{cy + 4:.0f}" class="ax val">{E(s["id"])} · {E(s["subgoal"][:62])}</text>'
                   f'<text x="{x3 + 4}" y="{cy + 4:.0f}" class="ax">{len(s["key_points"])} kp</text>')
        y += rowh
    for o in lec["roadmap"]["objectives"]:
        ys = oy[o["id"]]
        cy = sum(ys) / len(ys)
        out.append(f'<path d="M{x0 + 190} {H / 2:.0f} C {x1 - 20} {H / 2:.0f}, {x1 - 30} {cy:.0f}, {x1} {cy:.0f}" class="flow"/>')
        out.append(f'<rect x="{x1}" y="{cy - 12:.0f}" width="{x2 - x1 - 16}" height="24" rx="6" class="treeobj" '
                   f'data-tip="{E(o["text"])}"/><text x="{x1 + 8}" y="{cy + 4:.0f}" class="ax val">{E(o["id"])} · {E(o["text"][18:52])}…</text>')
        for yy in ys:
            out.append(f'<path d="M{x2 - 16} {cy:.0f} C {x2 - 8} {cy:.0f}, {x2 - 10} {yy:.0f}, {x2 - 4} {yy:.0f}" class="flow"/>')
    return f'<svg viewBox="0 0 {W + 40} {H}" class="chart" role="img" aria-label="Goal hierarchy">{"".join(out)}</svg>'


def phase_strip(lec: dict) -> str:
    ph = lec["phases"]
    W, left = 900, 0
    w = W / len(ph)
    out = []
    for i, p in enumerate(ph):
        k = ICAP_SLOT[p["intent"]["icap_mode"]]
        label = {"primer": "P", "segment": p.get("segment_id", ""), "active": "A", "constructive": "C"}[p["type"]]
        out.append(f'<rect x="{left + i * w + 1:.1f}" y="0" width="{w - 2:.1f}" height="34" rx="5" fill="var(--s{k})" '
                   f'data-tip="φ{i} · {p["type"]} · {p["intent"]["icap_mode"]} · {E(", ".join(p["intent"]["principle"]))}<br>'
                   f'rule {E(p["intent"]["rule_id"])}"/>')
        if w > 18:
            out.append(f'<text x="{left + i * w + w / 2:.1f}" y="22" text-anchor="middle" class="stripl">{E(label)}</text>')
    lg = '<div class="legend">' + "".join(f'<span><i style="background:var(--s{v})"></i>{k}</span>' for k, v in ICAP_SLOT.items()) + "</div>"
    return f'<svg viewBox="0 0 {W} 36" class="chart" role="img" aria-label="Phase sequence">{"".join(out)}</svg>{lg}'


def section_representation(lec: dict) -> str:
    n = len(lec["sentences"])
    m = len(lec["segments"])
    return f"""
<p>A lecture is represented in four layers, each defined on the one below. Everything that is generated points back
to the bottom layer, the sentences, so every item can be checked against the transcript and linked into the video.</p>
<div class="formal">
<p><b>Sentences.</b> Σ = (σ<sub>0</sub>, …, σ<sub>N−1</sub>), σ<sub>i</sub> = (i, t<sup>start</sup><sub>i</sub>, t<sup>end</sup><sub>i</sub>, text<sub>i</sub>), with t<sup>start</sup> non-decreasing. Here N = {n}.</p>
<p><b>Segmentation.</b> A partition of Σ into contiguous intervals S = (s<sub>1</sub>, …, s<sub>M</sub>), s<sub>j</sub> = [a<sub>j</sub>, b<sub>j</sub>],
a<sub>1</sub> = 0, a<sub>j+1</sub> = b<sub>j</sub> + 1, b<sub>M</sub> = N − 1, with 120 s ≤ dur(s<sub>j</sub>) (merged by code) and dur(s<sub>j</sub>) ≤ 720 s or flagged. Here M = {m}.</p>
<p><b>Annotation.</b> α(s) = (subgoal, c, K<sub>s</sub>, T<sub>s</sub>, U<sub>s</sub>): a verb-first sub-goal; a content type c ∈ C (10 types);
key points K<sub>s</sub> = {{(k, text, I<sub>k</sub>)}}, 2 ≤ |K<sub>s</sub>| ≤ 5, I<sub>k</sub> ⊆ s; key terms T<sub>s</sub> = {{(term, definition, I)}}, I ⊆ s;
used concepts U<sub>s</sub>. Every term t is mapped to a concept κ(t) ∈ V of the course graph (next section).</p>
<p><b>Goal hierarchy.</b> Objectives O = (o<sub>1</sub>, …, o<sub>R</sub>), 2 ≤ R ≤ 6 (or M when M &lt; 2), a partition of S into contiguous runs;
one lecture goal g. Course goals G<sup>c</sup> are built bottom-up from the lecture goals, each over a set of lectures.</p>
<p><b>Phases.</b> Φ = (φ<sub>0</sub>, φ<sub>1</sub>, …, φ<sub>2M+1</sub>) = (primer, seg(s<sub>1</sub>), act(s<sub>1</sub>), …, seg(s<sub>M</sub>), act(s<sub>M</sub>), constructive).
A renderer walks Φ in order and draws each φ by its type; nothing else is needed to play the lecture.</p>
<p><b>Intent.</b> Every phase and every item x carries ι(x) = (P, mode, bloom, rule, rationale, src): principles P ⊆ Π (11 named
principles), ICAP mode ∈ {{passive, active, constructive}}, a Bloom level, the code rule that chose x, a templated rationale,
and its sources src(x) ⊆ Σ.</p>
</div>
<h3>Invariants (checked by code)</h3>
<ul>
<li><b>Grounding:</b> src(x) ⊆ s(x) for items generated from a segment, and src(x) ⊆ Σ for lecture-level items.</li>
<li><b>Coverage:</b> S partitions Σ; O partitions S into contiguous runs; every segment has exactly one objective.</li>
<li><b>Order:</b> lecture k refers only to concepts with intro(v) ≤ k; recall items point only to lectures &lt; k.</li>
<li><b>Counts:</b> 4 quiz items per segment before judging (exactly one correct option each), 4 open questions per lecture, 3–5 key points per question with ≥ 2 keywords each.</li>
<li><b>Origin:</b> every LLM-produced item has an origin record (model, prompt ID and version, input hash, validator result, retries, tokens, latency).</li>
</ul>
<h3>Example: {E(lec['lecture_id'])} · {E(lec['title'])}</h3>
<p>The goal hierarchy (lecture goal → objectives → segments, with their key-point counts; hover a box for its text):</p>
{goal_tree(lec)}
<p>The phase sequence Φ, colored by ICAP mode (P = primer, S<i>j</i> = segment video, A = quiz and summary, C = concept map and questions):</p>
{phase_strip(lec)}"""


# ------------------------------------------------------------------ 3. graph representation
def growth_chart(course: dict, lectures: list[dict]) -> str:
    order = {lid: i for i, lid in enumerate(course["lecture_ids"])}
    K = len(course["lecture_ids"])
    v_k = [0] * K
    e_k = [0] * K
    for c in course["concepts"]:
        i = order.get(c["introduced"]["lecture_id"])
        if i is not None:
            for k in range(i, K):
                v_k[k] += 1
    for e in course["edges"]:
        i = order.get(e["evidence"]["lecture_id"])
        if i is not None:
            for k in range(i, K):
                e_k[k] += 1
    W, H, left, bot = 900, 240, 46, 28
    mx = max(max(v_k), max(e_k), 1)
    step = max(1, 10 ** int(math.log10(mx)) // (1 if mx / 10 ** int(math.log10(mx)) > 3 else 2))
    out = []
    for v in range(0, mx + 1, step):
        y = H - bot - v / mx * (H - bot - 10)
        out.append(f'<line x1="{left}" x2="{W}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" class="ax">{v}</text>')
    xs = [left + (k / max(1, K - 1)) * (W - left - 20) for k in range(K)]
    for series, slot, name in ((v_k, 1, "|V_k| concepts"), (e_k, 2, "|E_k| edges")):
        pts = " ".join(f"{x:.1f},{H - bot - v / mx * (H - bot - 10):.1f}" for x, v in zip(xs, series))
        out.append(f'<polyline points="{pts}" fill="none" stroke="var(--s{slot})" stroke-width="2"/>')
        for k, (x, v) in enumerate(zip(xs, series)):
            out.append(f'<circle cx="{x:.1f}" cy="{H - bot - v / mx * (H - bot - 10):.1f}" r="4" fill="var(--s{slot})" '
                       f'class="gnode" data-tip="after {course["lecture_ids"][k]}: {name.split()[1]} = {v}"/>')
        out.append(f'<text x="{xs[-1] + 6:.1f}" y="{H - bot - series[-1] / mx * (H - bot - 10) + 4:.1f}" class="ax val">{series[-1]}</text>')
    lab_every = max(1, K // 12)
    for k in range(0, K, lab_every):
        out.append(f'<text x="{xs[k]:.1f}" y="{H - 8}" text-anchor="middle" class="ax">{course["lecture_ids"][k]}</text>')
    return (f'<svg viewBox="0 0 {W + 40} {H}" class="chart" role="img" aria-label="Graph growth">{"".join(out)}</svg>'
            f'<div class="legend"><span><i style="background:var(--s1)"></i>|V<sub>k</sub>| concepts known after lecture k</span>'
            f'<span><i style="background:var(--s2)"></i>|E<sub>k</sub>| edges known after lecture k</span></div>')


def section_graph(course: dict, lectures: list[dict], ex: dict) -> str:
    rel = {}
    for e in course["edges"]:
        rel[e["rel"]] = rel.get(e["rel"], 0) + 1
    deg = {}
    for e in course["edges"]:
        for x in (e["src"], e["dst"]):
            deg[x] = deg.get(x, 0) + 1
    isolated = sum(1 for c in course["concepts"] if c["id"] not in deg)
    cm = ex["phases"][-1]["concept_map"]
    rec = ex["phases"][0]["recall"]
    return f"""
<p>The course is represented as one typed, evidence-carrying graph that grows lecture by lecture. Everything that
crosses a lecture boundary (recall items, links to earlier material in summaries, interleaved quiz items, the concept
maps) is a query on a snapshot of this graph.</p>
<div class="formal">
<p><b>Graph.</b> G = (V, E, λ). Concepts v ∈ V carry a name, aliases A(v), a definition d(v) (or none), an introduction
point intro(v) = (lecture, segment, sentence, t), mentions M(v) (segment and sentence IDs), and a salience. Edges are typed
triples e = (u, r, w) ∈ V × R × V with R = {{prerequisite_of, part_of, example_of, contrasts_with, leads_to, used_in}};
each carries a link phrase λ(e) for the concept map and evidence ev(e) = (lecture, I), I ⊆ Σ<sub>lecture</sub>.
Edges are deduplicated on (u, r, w); contrasts_with is symmetric.</p>
<p><b>Canonicalization.</b> A term t from stage 2 is mapped to a concept by κ, applying the first rule that fires:
(1) normalized name or alias equal (case, plural, hyphens; “Augmented Reality (AR)” gives the alias AR);
(2) acronym rule: an acronym equals the initials of another name of ≥ 2 words;
(3) cos(emb(t), emb(v)) ≥ 0.93 → same concept;
(4) 0.78 ≤ cos &lt; 0.93 → the generator answers a yes/no question;
(5) otherwise a new concept, but only if t is defined somewhere; a term that is only used, never defined, joins an
existing concept or is dropped. Rules 1–2 and the order of evaluation make κ deterministic given the LLM's yes/no answers.</p>
<p><b>Snapshots.</b> For lecture position k, G<sub>k</sub> = (V<sub>k</sub>, E<sub>k</sub>) with V<sub>k</sub> = {{v : lec(intro(v)) ≤ k}} and
E<sub>k</sub> = {{e : lec(ev(e)) ≤ k}}, mentions and definitions filtered the same way. Snapshots are monotone:
G<sub>k−1</sub> ⊆ G<sub>k</sub>. Each is saved as <code>output/&lt;course&gt;/state/state_Lxx.json</code>.</p>
<p><b>No leakage.</b> Everything generated for lecture k is a function of (α(lecture k), G<sub>k</sub>); the primer is a function of
(α(lecture k), G<sub>k−1</sub>, and the edges from lecture k's new concepts). Code checks this when assembling.</p>
<p><b>Salience.</b> sal<sub>k</sub>(v) = [ln(1 + |segments mentioning v up to k|) + 𝟙[d(v) defined] + ½ ln(1 + deg<sub>k</sub>(v))] / max<sub>u</sub>(·).
It ranks the primer's key terms (≤ 8), the summary's key concepts (≤ 8) and the concept-map seeds.</p>
<p><b>Queries.</b> With new(k) = {{v : lec(intro(v)) = k}} and N<sub>k</sub>(x) the neighbours of x in G<sub>k</sub>:</p>
<ul>
<li>recall(k) = top-4 by sal<sub>k−1</sub> of {{u ∈ V<sub>k−1</sub> : ∃ (u, r, w) ∈ E<sub>k</sub>, w ∈ new(k), r ∈ {{prerequisite_of, used_in}}}};</li>
<li>earlier_links(s) = {{u : (u, ·, w) or (w, ·, u) ∈ E<sub>k</sub>, w ∈ κ(s), u introduced before s}};</li>
<li>interleave(s) = argmax<sub>u</sub> sal<sub>k</sub>(u) over u ∈ V<sub>k−1</sub> adjacent to κ(s) with d(u) defined;</li>
<li>map_ref(k) = the subgraph of G<sub>k</sub> induced by V(k) ∪ (N<sub>k</sub>(V(k)) ∩ V<sub>k−1</sub>), where V(k) are the concepts mentioned in
lecture k; seeds = top-4 of new(k) by salience plus the top-2 earlier anchors.</li>
</ul>
</div>
<h3>This course's graph</h3>
<div class="tiles"><div class="tile"><b>{len(course['concepts'])}</b><span>concepts |V|</span></div>
<div class="tile"><b>{len(course['edges'])}</b><span>edges |E|</span></div>
<div class="tile"><b>{(2 * len(course['edges']) / max(1, len(course['concepts']))):.2f}</b><span>mean degree</span></div>
<div class="tile"><b>{isolated}</b><span>concepts with no edge</span></div>
{''.join(f'<div class="tile"><b>{v}</b><span>{E(k.replace("_", " "))}</span></div>' for k, v in sorted(rel.items(), key=lambda x: -x[1]))}</div>
<p>How the graph grows, lecture by lecture (the snapshot sizes |V<sub>k</sub>| and |E<sub>k</sub>|):</p>
{growth_chart(course, lectures)}
<p>For {E(ex['lecture_id'])}, the queries above give {len(rec)} recall item(s) and a reference map of
{len(cm['reference_nodes'])} concepts and {len(cm['reference_edges'])} links, seeded with
{', '.join(E(s['name']) for s in cm['seeds'])}.</p>"""


# ------------------------------------------------------------------ 4. configuration
CONFIG_FIELDS = [
    ("[generator] model", "The model for stages 1–5, the calibration answers and the judge's repairs. A Hugging Face GGUF "
     "reference <code>org/repo:file.gguf</code> runs locally on llama.cpp (downloaded on first use); a plain OpenAI model "
     "name such as <code>gpt-6-luna</code> runs on the API."),
    ("[generator] slots", "Local: parallel requests on the server (continuous batching). API: concurrent requests. "
     "32 is the throughput peak for E4B on the RTX 5070."),
    ("[generator] kv_tokens", "Local only: the KV-cache pool in tokens, shared by all slots (f16, never quantized). The "
     "client keeps the tokens in flight under 85% of it."),
    ("[generator] think_budget", "Local only: the most thinking tokens one call may use (llama.cpp <code>--reasoning-budget</code>). "
     "Stops runaway reasoning."),
    ("[generator] reasoning_effort", "API only: <code>low</code>, <code>medium</code> or <code>high</code>."),
    ("[judge] model", "The layer-3 judge (stage 6). Same two formats as the generator. A local judge must be larger than the "
     "generator to be useful; an API model is the default here."),
    ("[judge] slots, kv_tokens, think_budget, reasoning_effort", "As for the generator. A local 12B judge fits the 12 GB card "
     "only with 8 slots and a 32k pool; if it does not fit, the run retries with 6/24k and 4/16k, then stops with a clear message."),
    ("[api] env_file, key_var", "Where the API key is read: the variable <code>key_var</code> in the file <code>env_file</code> "
     "(or the environment). Never committed: <code>.env</code> is in <code>.gitignore</code>."),
    ("[api] base_url", "Any OpenAI-compatible endpoint."),
    ("[api] budget_usd", "The total API budget across all runs. Every call is priced before it is sent at its worst case "
     "(prompt + maximum output); a call that could cross the budget is not sent. Spending is recorded per run and per "
     "stage in <code>api_spend.json</code>, shown live in the terminal, and summarized in the report. Judge items left "
     "unsent are counted as “not judged (budget)” and keep their layer-2-checked content."),
    ('[api.prices."model"] input, cached_input, output', "US$ per million tokens, used for the budget. Required for every "
     "API model in use; the run refuses to start without them."),
    ("[videos] height", "Video resolution for the downloads (default 720)."),
]

EXAMPLES = """# judge locally with Gemma 4 12B (no API, no spending; slower: the models take turns on the GPU)
[judge]
model = "unsloth/gemma-4-12B-it-qat-GGUF:gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
slots = 8
kv_tokens = 32768
think_budget = 4096

# generate on the API too (then add its prices under [api.prices."gpt-6-luna"])
[generator]
model = "gpt-6-luna"
slots = 32
reasoning_effort = "medium"

# a different local generator: any GGUF on Hugging Face, "repo:file"
[generator]
model = "unsloth/gemma-4-E2B-it-GGUF:gemma-4-E2B-it-UD-Q8_K_XL.gguf"
"""


def section_config(cfg_text: str, ledger: dict | None) -> str:
    rows = "".join(f"<tr><td><code>{E(k)}</code></td><td>{v}</td></tr>" for k, v in CONFIG_FIELDS)
    spend = ""
    if ledger:
        runs = "".join(f"<tr><td>{E(r['date'])}</td><td>{E(r['course_id'])}</td><td class='n'>{r['calls']}</td>"
                       f"<td class='n'>${r['usd']:.4f}</td></tr>" for r in ledger.get("runs", []) if r.get("calls"))
        spend = (f"<h3>API spending so far</h3><p>${ledger.get('total_usd', 0):.4f} of the "
                 f"${ledger.get('budget_usd', 0):.2f} budget.</p>"
                 f"<table><thead><tr><th>Run</th><th>Course</th><th>Calls</th><th>Cost</th></tr></thead><tbody>{runs}</tbody></table>")
    return f"""
<p>Which model plays which role is set in <code>lir-construction/lir_config.toml</code>; edit it and rerun
<code>generate_lir.py</code> (or pass <code>--config other.toml</code>). Nothing else changes: the stages, prompts and checks are
the same whichever model runs them. Cached answers are keyed by model, so switching a model recomputes only what that
model produces.</p>
<h3>Every field</h3><table><thead><tr><th>Field</th><th>What it does</th></tr></thead><tbody>{rows}</tbody></table>
<h3>Examples</h3><pre>{E(EXAMPLES)}</pre>
<h3>The current file</h3><pre>{E(cfg_text)}</pre>{spend}"""
