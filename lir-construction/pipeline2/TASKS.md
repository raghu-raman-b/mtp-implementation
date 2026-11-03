# LIR v2.1: merged pipeline

Status: ✅ done · 🔄 in progress · ⬜ to do · ⏸ on hold · ⚠️ blocked or needs a decision

Planned on 2026-11-03. Replaces the step layout of LIR v2 (`../tasks.md`, "LIR v2"); the knowledge layer and activities
keep their purpose, but calls are merged per part, window, group or lecture, and the run is scheduled per item.

## Why

LIR v2 makes one call per decision. Estimated on v1's real VR data, that is 30k–75k calls for VR (v1: 5,149) and
40k–103k for Deep Learning (v1: 4,306), with thinking uncapped at temperature 1.0: one parts call on VR L01 thought
for 17,129 tokens to return 28 characters. Estimated VR run time: 10–18 h (v1: 2 h 51 min).

The merged pipeline below: about 6.0k calls for VR and 5.5k for DL; on the 27B, about 5 h for VR (see Estimates).

## Design rules

Kept from v2:
- Goal: make the passive lecture interactive and engaging. The LIR is a format any renderer can use (web, VR), so
  knowledge is kept apart from how activities are shown.
- Everything has an address and cites sentences: `L05/S0412` sentence, `L05/P03` part, `L05/P03/K2` key point,
  `L05/P03/T1` term occurrence, `L05/O2` objective, `G3` course goal, `C014` concept, `C014@L05/P03` facet, `E031`
  link, `D0420` decision.
- Code checks structure and sources only (IDs exist, cited sentences are in range, a term occurs in its sentences, an
  abbreviation is in its sentence). Meaning is decided by the model. No verb lists, first-letter rules or wording
  heuristics.
- Every decision (kept, dropped, merged, rewritten, flagged) is logged with its call, reason and evidence in
  `decisions.jsonl`.
- Lean: no salience, content type, Bloom level, ICAP/principle intents.
- Relations: `kind_of`, `part_of`, `depends_on`, each with a label written for learners.
- Named systems, products and people are concepts when the lecture explains them.

Changed:
- **One unit per prompt** instead of one task per prompt: a call handles every item of one part, window, registry
  group or lecture. Thinking does the planning, so plan and write are one call.
- **Two kinds of definition.** A term definition belongs to its lecture, comes from that lecture's sentences and is
  what the learner sees there. The registry's canonical definition is course-wide and is used to build the graph
  (facets, links, lookup). Definitions are no longer dated "as of lecture k".
- **Course order applies to what the learner sees**: lecture k shows its own term definitions, recall uses only
  earlier lectures, a lecture's concept map shows only links found up to that lecture. The graph itself is built with
  the whole course known.
- **Links**: any graph shape is allowed, cycles included; the judge decides which links stay. A two-way `kind_of` or
  `part_of` is flagged in the decision log, not dropped.
- **Judges** check every item of a unit in one call; only the items that fail are rewritten (once) and judged again.
  A code check that fails drops or retries only that item, never the whole unit.

## Model and engine

Two setups run the same pipeline, so their output can be compared:

| Setup | Writes (generator) | Verifies and judges | Engine |
|---|---|---|---|
| Large | Qwen 3.8 27B FP8 | Qwen 3.8 27B FP8 (the same server) | vLLM, no MTP (throughput first) |
| Small | Gemma 4 E4B | Gemma 4 12B | vLLM, two servers sharing the GPU |

Generator steps: 1, 2, 3, 5, 7, 7c, 9a–9d. Verifier steps: 4 registry, 6 links. Judge: every J step.

| Setting | Value | Notes |
|---|---|---|
| GPU | RTX PRO 6000 96 GB (EC2) | vLLM 0.32.0; engine checks done on EC2 |
| Thinking cap | 8k: parts, objective + key points, key terms, facets, links, activities, open questions; 4k: judges, registry, goals, recall, calibration | per request `thinking_token_budget`; vLLM ends the thinking with a closing phrase (`--reasoning-config` `reasoning_end_str`), the answer is never cut |
| Sampling | temperature 0.6, top_p 0.95, top_k 20, seed 0 | check against the Qwen 3.8 model card; never 0 (repetition loops in thinking) |
| Scheduling | `--scheduling-policy priority`; the critical path first (see Run order) | |
| Reasons | one sentence, after thinking | schema length limit |

## The pipeline

Calls are estimates for VR / DL. "J" steps are judges: one call per unit, then one rewrite of the failed items and
one more judge call (counted, assuming about half the units need it).

### Knowledge layer

| # | Step | One call per | Input | Task | Output | Think | Calls VR / DL |
|---|---|---|---|---|---|--:|--:|
| 0 | Sentences (code) | — | Subtitles, or the transcript aligned to YouTube captions | Split into sentences | Numbered sentences with times | — | — |
| 1 | Parts | lecture | Whole transcript (300-sentence windows if too long) | Topic boundaries; code merges parts under 2 min | Parts (sentence ranges) | 8k | 63 / 23 |
| 2 | Objective + key points | part | Part transcript | What the learner can do after the part; 2–5 key points, each tagged subject or course | Objective; key points with sentence IDs (course ones dropped) | 8k | 388 / 378 |
| J2 | Judge | part | Part transcript, objective, key points | Each: accurate, supported, about the subject, self-contained? | Verdicts; failed key points rewritten once, then dropped; a failed objective is kept and flagged | 4k | 776 / 756 |
| 3 | Key terms | ~40-sentence window inside a part (10 overlap) | Window transcript, the part's judged objective | Every term the lecturer explains: keep or drop (reason), glossary name, abbreviation if the lecturer says one (with its sentence), definition from the cited sentences | Term occurrences, and dropped candidates with reasons | 8k | 444 / 587 |
| J3 | Judge | part | Whole part transcript, its terms (deduplicated across windows) | Each: worth a glossary entry given the part, name right, definition supported by the sentences? | Verdicts; failed terms rewritten once, then dropped | 4k | 776 / 756 |
| 4 | Registry | group of similar terms | Code groups: same name or attested abbreviation; terms all similar to each other (embedding ≥ 0.6), size-capped. Per term: name, aliases, lecture definition, cited sentences | Which terms are the same concept (the model splits the group); per concept: canonical name, definition, reason | Concepts: ID, canonical name, aliases, canonical definition, reason, sources, term occurrences. A single term needs no call | 4k | ~600 / ~480 |
| 4w | Write back (code) | — | Concepts | Each term occurrence gets its concept ID and canonical name | Updated lecture files | — | — |
| 7 | Objectives + lecture goal | lecture | Judged part objectives | Group parts into 2–6 contiguous objectives ("You'll be able to …"); one lecture goal | Objectives, lecture goal | 4k | 63 / 23 |
| 7c | Course goals | course | Every lecture's goal and objectives | 2–6 course goals, each with the lectures that serve it; every lecture serves one | Course goals | 4k | 1 / 1 |
| J7 | Judge | lecture; one for the course goals | Parts' objectives and key points; the objectives and goal (or the course goals) | Accurate, covers the content, claims nothing extra? | Verdicts; rewritten once; kept and flagged if still failing | 4k | ~89 / ~33 |
| 5a | Mentions (code) | — | Concepts (all names and aliases), sentences | Where each concept is named, from its introducing lecture on | Concept → parts → sentences | — | — |
| 5 | Facets (lecture by lecture, in course order; a lecture's parts at once) | part | Part transcript; every concept named in it: canonical name, aliases, canonical definition, the sentences that name it, all its facets from earlier lectures | Per concept: taught here or only mentioned; what the part teaches about it, as a fact of the subject, saying what is new | Facets: concept, part, only_mentioned, says, sentences | 8k | 388 / 378 |
| J5 | Judge (off the chain) | part | Part transcript, its facets | Each: supported by its sentences, something this part teaches? | Verdicts; rewritten once, otherwise "only mentioned" | 4k | 776 / 756 |
| 6 | Links | lecture (after its facets) | Every concept named in the lecture: canonical name, canonical definition, its sentences in this lecture (≤ 6), this lecture's facet and its earlier facets | Every relation the lecture states or clearly implies | Proposed links: src, relation, dst, label, evidence (sentences shown) | 8k | 63 / 23 |
| J6 | Judge | lecture | Proposed links, their evidence, both definitions | Each: supported, right direction, label true and natural? | Kept / dropped / reversed (code flips it); links merged across lectures (earliest kept, evidence joined, a conflicting relation logged) | 4k | 63 / 23 |
| 8 | Lecture map (code) | — | Facets, `depends_on` links | Lecture i → j when j teaches about a concept introduced in i, or a concept in j depends on one from i; top 3 incoming per lecture | Lecture map | — | — |

### Activity layer

| # | Step | One call per | Input | Task | Output | Think | Calls VR / DL |
|---|---|---|---|---|---|--:|--:|
| 9a | Part activities | part | Part transcript, judged key points | Quiz: 0–4 items on the key points worth testing (multiple choice / true-false / yes-no, with reason); recap (2–3 sentences); a review question on each key point the quiz does not test. Code checks each item's format | Quiz items, recap, review questions | 8k | 388 / 378 |
| J9a | Judge | part | Part transcript, all its items | Each: answerable from the part, answer right and the only right one, worth asking, explanations right? | Verdicts; failed items rewritten once, then dropped (a recap falls back to the key points) | 4k | 776 / 756 |
| 9b | Open questions | lecture | Everything known about the lecture: goal, objectives, part objectives, key points with their sentences, key terms and definitions, facets, links within the lecture | 2–6 questions (about one per 15 min of video), each of a type the content supports | Question, type, reference answer, 3–5 key points with keywords and sentences | 8k | 63 / 23 |
| J9b | Judge | lecture | The same lecture knowledge, all its questions | Answerable, of its type, reference answer right, key points match? | Verdicts; rewritten once, then dropped | 4k | 126 / 46 |
| 9c | Recall | lecture | Concepts carried in by the lecture map (≤ 4): term definitions and facets from earlier lectures only | One question and answer per concept, with a jump back to where it was taught | Recall items | 4k | 62 / 22 |
| J9c | Judge | lecture | The recall material, the items | Recalls the concept without giving it away, answer right? | Verdicts; rewritten once, then dropped | 4k | 124 / 44 |
| 9d | Calibration | sampled open question (16) | Question, reference answer, key points | A good, a partial and a wrong student answer | Answers for fitting the scorer | 4k | 16 / 16 |

### Built by code at the end

| Step | Input | Output |
|---|---|---|
| Concept map per lecture | Concepts introduced in the lecture plus up to 4 earlier ones it teaches about (facets); links found up to this lecture | ≤ 14 nodes ranked by links in the lecture, seeds, labelled links |
| Spaced review after each part | Facets (earlier concepts the part teaches about), quiz tags, `depends_on` links | Due concepts (gaps 1, 2, 4, 8 lectures; concepts a new one depends on first) re-asked with an earlier judged quiz item, least used first; ≤ 4 candidates, 2 by default |
| Scorer calibration | Calibration answers | m and τ for open-answer scoring; key-point embeddings |
| Assemble | Everything | The files below, validated against `lir2_schema.py` |

## Run order (one course at a time)

Each part and each lecture moves on as soon as its inputs are ready; nothing waits for a whole stage to finish.

```
critical path   1 parts → 2 → J2 → 3 key terms → J3            (per part)
                ══ registry (needs every term; one wave) ══
                5 facets L01 → L02 → … → Lnn                     (top priority)
                last lecture: J5 → 6 → J6 → 9b, 9c → judges → code at the end
filling the GPU (lower priority, as soon as their inputs exist)
                J2 → 9a part activities → J9a                    (from the start)
                7 goals → 7c → J7                                (after J2)
                per lecture behind the facet chain: J5, 6 links → J6, 9b → J9b, 8 lecture map
                links into lecture k, 9c recall → J9c; 9d calibration on the first 16 open questions
```

The facet chain is kept on purpose: facets build on earlier facets. Measured on v1's concepts, it cannot be shortened
by waiting only for lectures that share a concept: a few concepts appear in nearly every lecture (VR: Augmented reality
in 63, DL: Gradient in 22), so it stays 63 (VR) and 23 (DL) lectures long. Without MTP, a request runs at about 14
tok/s while the GPU is full (1,750 tok/s over 128 requests), so on the large setup the chain sets VR's run time
(about 6 min per lecture until the other work runs out). Accepted.

Alternatives considered and set aside: earlier key points instead of earlier facets (no chain; an earlier key point
names the concept in 98% of cases), a lagged chain (k−4), a second per-concept "what's new" pass.

## Outputs

Per course, in `lir-v2/<course>/` (or `runs/<name>/<course>/lir/`):

| File | What it holds | Used by |
|---|---|---|
| `Lxx.json`, the lecture LIR | Sentences with times; parts (objective, key points with sources, term occurrences with the lecture's definition, concept ID and canonical name); objectives; lecture goal; flags; origin of every call | Watching, captions, the glossary at that point, lookups by address |
| `activities/Lxx.json` | Default sequence (recall → watch, quiz with spaced review, summary per part → concept map → open questions); recall items; per part: quiz, recap, review questions, spaced review candidates; the lecture's concept map; open questions; scoring settings | The learner's lecture |
| `course.json`, the concept graph | Concepts (canonical name, aliases, canonical definition, reason, sources, term occurrences, facets); links (relation, label, evidence, lecture found in, flags); lecture map; course goals; alias index | Lookup (term → concept → definition, facets, links, limited to the learner's position), the course map, the per-lecture maps |
| Concept map per lecture | Inside `activities/Lxx.json`: nodes, seeds, links with labels | The concept map activity: the learner builds a map from the seeds and compares it with this one |
| Course concept map | The concept graph in `course.json` (the union of every lecture's links; nodes are the same canonical concepts) | The course map at the end of the course, grouped by course goal |
| Lecture map | In `course.json`: lecture → lecture links with weights and the concepts they carry | Recall before a lecture, ordering of spaced review |
| `embeddings.json` | Concept embeddings | Matching a learner's concept names and answers |
| `decisions.jsonl` | Every decision with call, reason and evidence | Review, debugging |

Build files (`output/<course>/v2/` or `runs/<name>/<course>/build/`): answer cache, step outputs, `calls.jsonl` (every
request), `report.md` (time and calls per step, tokens, counts, pass and drop rates).

## Estimates

Calls (v1 in brackets): VR ~6.0k (5,149), DL ~5.5k (4,306).

Time, one course at a time, middle case (the per-step token numbers are guesses; range about ×0.7 to ×1.4).
Small-model speeds are not measured: E4B ~4,000–8,000 tok/s, 12B ~2,500–4,500 tok/s, scaled from the 27B.

| Run | GPU work | Run time | v1 |
|---|--:|--:|--:|
| VR, small (E4B + 12B) | 1.4 h | ~2.1 h | 2 h 51 min |
| VR, large (27B) | 3.5 h | ~5.2 h (facet chain) | |
| DL, small | 1.3 h | ~1.4 h | 3 h 34 min |
| DL, large | 3.3 h | ~3.5 h | |
| All four, with server starts | | ~12.5–13 h | |

## Tasks

### Plan

| Status | Task | Notes |
|---|---|---|
| ✅ | Call counts: v1 vs v2, per step | v1 from each lecture's origin list; v2 from the v2 code paths over v1's real data |
| ✅ | Measure: same-concept pairs above the threshold | ~1.2 per concept at 0.6 (VR 1,022, DL 816) |
| ✅ | Measure: concept spread, pairs by co-occurrence, concepts per lecture, facet chain depth | |
| ✅ | Merged pipeline, outputs, run order, estimates | this file |

### Code

Built on 2026-11-03. Checked with the fake-model smoke test on VR L01–L02 (every step, judge, rewrite, flip and
spaced-review path; identical output under different hash seeds, so a resumed run hits its cache) and the HTTP client
against a stand-in vLLM server (command lines of both setups, request body, priority order). Not yet run on a real
model.

| Status | Task | Notes |
|---|---|---|
| ✅ | vLLM settings: thinking budget per step, closing phrase, priority scheduling, temperature 0.6, text only | `pipeline/llm.py` (`thinking_token_budget`, `--reasoning-config`, `--scheduling-policy priority`, `--language-model-only`), per-server settings from the role's table; budget part of the cache key |
| ✅ | Requests in priority order | `PriorityGate`: at most max-num-seqs in flight per server, waiting ones by priority, then first come |
| ✅ | Per-item flow: tasks with dependencies, priorities on the critical path | `pipeline2/flow.py`, `pipeline2/orchestrate.py`; replaces the stage-by-stage `generate_lir2.py` |
| ✅ | Item-level failures: a failed code check drops the item (logged); rewrites only for failed items; a rejected request (4xx) is a failed item, not a crashed run; output capped to fit the context | `pipeline2/judge.py`, `pipeline/llm.py` |
| ✅ | 2 + J2 merged | `s2_parts.py` |
| ✅ | 3 + J3: one call per window, one judge per part | `s3_terms.py` |
| ✅ | 4 registry: global groups (complete linkage, at most 8 entries), one call per group, write back | `s4_registry.py`; schema: canonical definition + reason + sources instead of dated versions |
| ✅ | 7 + 7c + J7 merged | `s7_goals.py` |
| ✅ | 5 facets per part, in course order, with every earlier facet (as written); J5 off the chain | `s5_facets.py`; at most 25 concepts per call |
| ✅ | 6 links per lecture + J6 (keep / drop / flip); merge across lectures; cycles allowed, two-way and forward flags | `s6_edges.py` |
| ✅ | 8 lecture map per lecture (recall need not wait for the course) | `s8_lecture_map.py` |
| ✅ | 9a part activities + J9a | `act_part.py` (replaces `act_quiz.py`, `act_summary.py`) |
| ✅ | 9b open questions per lecture from the lecture's knowledge + J9b | `act_open.py`; J9b is one call per lecture (all its questions), not one per question |
| ✅ | 9c recall per lecture from earlier term definitions and facets + J9c | `act_recall.py` |
| ✅ | 9d calibration | `act_calibrate.py`; at the end (16 calls) |
| ✅ | Schema and assembly for the changed fields | `lir2_schema.py` (2.1), `assemble.py` |
| ✅ | Smoke test with the fake model on VR L01–L02 | `tests/smoke_pipeline2.py` |
| ✅ | Run report: calls, tokens and time per step | `report.py` (each step's span from the flow), `run_report.py` |
| ✅ | Small setup config: E4B generator + 12B verifier/judge on vLLM, two servers sharing the GPU | `lir2_config_small.toml`; `setup_ec2.sh` downloads the Gemma models |
| ✅ | Large setup config: MTP off | `lir2_config.toml` |
| ✅ | Run script: setups one after another, courses one at a time, a run folder per setup | `run_v2.sh --setups small,large --courses vr`; `run_monitor.py` reads both servers |

### Run (EC2)

| Status | Task | Notes |
|---|---|---|
| ✅ | Engine checks | done on EC2 before this plan |
| ⬜ | VR, small setup | today, first: also the shakedown of the new pipeline (~2 h) |
| ⬜ | VR, large setup | today, second (~5 h) |
| ⬜ | DL, small and large | |
| ⬜ | Compare the two setups and v1 by hand: registry, facets, links (missed links in big lectures?), key terms, activities | |

### Later

| Status | Task | Notes |
|---|---|---|
| ⬜ | Viewer on LIR v2.1 | a concept map in lecture k shows that lecture's term definitions on hover, not the canonical one |
| ⬜ | Live Q&A lookup limited to the learner's position | |
| ⏸ | A faster model (mixture of experts) | only after the L01–L03 quality check |

## Open decisions

- Thinking caps per step: set above; to revisit with the measured tokens.
- Big DL lectures (92–156 concepts) in one link call: if L01–L03 shows missed links, split them into concept groups.
- Facet chain: kept whole (facets build on earlier facets), accepting ~1.7 h more on the large VR run.
