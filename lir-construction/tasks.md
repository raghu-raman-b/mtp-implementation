# Tasks

Status: ✅ done · 🔄 in progress · ⬜ to do · ⏸ on hold · ⚠️ blocked or needs a decision

## LIR v2: knowledge layer overhaul (started 2026-11-02)

Why: the v1 concept registry is unreliable. "Extended reality" picked up the aliases "ER", "Error rates", "Empirical
research", "Entity-Relationship" and "Enhanced realism": the model invented "Extended reality (ER)", a first-letters rule
matched "Error rates" to "ER", and merges chained through any member of a group. A dropped first occurrence also left
52 duplicate-name concepts ("Loss" ×3, "Gradient" ×3). 48% (VR) and 71% (DL) of concepts have no link, and there are 12
`prerequisite_of` links across both courses. Key-term extraction misses terms in long parts (VR L02 part 3 defines
immersion and three kinds of VR system; one term was kept) and keeps non-concepts ("Cognitive side", "Experimental phase").

v2 rebuilds the knowledge layer; the activities are rebuilt on top of it afterwards. Code: `pipeline2/`,
`generate_lir2.py`, `lir2_schema.py`, config `lir2_config.toml`, output `lir-v2/<course>/`, on branch `lir-v2`. v1 stays
untouched until v2 is better.

Design rules (agreed):
- Goal: make the passive lecture interactive and engaging. The LIR is a format any renderer can use (web, VR), so
  knowledge is kept apart from how activities are shown.
- Everything has an address and cites sentences: `L05/S0412` sentence, `L05/P03` part (a sentence range), `L05/P03/K2`
  key point, `L05/P03/T1` term occurrence, `L05/O2` objective, `G3` course goal, `C014` concept, `C014@L05/P03` facet,
  `E031` edge, `D0420` decision.
- One task per prompt.
- Code checks structure and sources only (IDs exist, the text is in the cited sentences, no cycles). Meaning is decided
  by the model, as a yes/no with a reason. No verb lists, first-letter rules or wording heuristics.
- Course order: nothing built for lecture k reads a later lecture. Definitions are dated: "as of lecture k", refined
  from all of the concept's definitions up to k.
- Every decision (merge, edge, dropped term) is logged with its call, reason and evidence in `decisions.jsonl`.
- Lean: no salience, content type, Bloom level, ICAP/principle intents, `used_concepts`.
- Relations: `kind_of`, `part_of`, `depends_on`. Each edge has the relation (for the system) and a label written from
  the evidence (for learners).
- Named systems, products and people are concepts when the lecture explains them. Terms the course never explains stay out.
- Prompts that share a start (a window, a part) run one after another on one server slot, so the prefix cache is reused.

### Phase 0: setup

| Status | Task | Notes |
|---|---|---|
| ✅ | Branch `lir-v2` | |
| ✅ | This task list | |
| ✅ | Config: `verifier` role (Gemma 4 12B), model per step, llama-server path, "one model on the GPU at a time" switch (off on a big EC2 GPU) | `lir2_config.toml`, `pipeline/config.py` |
| ✅ | Separate `judge` role (checks and rewrites); roles that name the same model share one server (e.g. one Qwen 27B for all three) | `[judge]` in `lir2_config.toml`; without it the verifier judges |
| ✅ | LLM client: calls in a group run in order on one server slot (`id_slot`); the llama-server path from the config | `pipeline/llm.py`; v1 unchanged in behaviour |
| ✅ | LIR v2 schema | `lir2_schema.py` |
| ✅ | Addresses, decision log, run context | `pipeline2/addr.py`, `pipeline2/context.py` |
| ✅ | Term matching in text (word stems, phrases, case-sensitive abbreviations) | `pipeline2/match.py` |

### Phase 1: knowledge layer

Built and checked with a fake model on VR L01–L02 (`tests/smoke_pipeline2.py`, which also runs the judge's rewrite
paths); not yet run on a real model.

| Status | Task | Notes |
|---|---|---|
| ✅ | 0 Sentences with addresses | v1 `transcript.py` and caption alignment |
| ✅ | 1 Parts: the standalone-segments prompt (WD 0.09), parts under 2 min merged | generator |
| ✅ | 2a Part objective, 1 call per part | generator |
| ✅ | 2b Key points: every subject point the part teaches, each cited, no cap | generator |
| ✅ | 3a Term candidates over windows of about 40 sentences inside each part (10 overlap), no cap; code: the term is in its cited sentences | generator |
| ✅ | 3b Keep or drop each candidate, with a reason | verifier |
| ✅ | 3c Glossary name (noun phrase, singular); abbreviation only if the lecturer says it, with the sentence; code checks it is there | verifier |
| ✅ | 3d Definition from the cited sentences | verifier |
| ✅ | 3e Grounding check; one rewrite with the reason, then drop | verifier |
| ✅ | 3b–3e for one window run in order on one slot (shared prefix) | |
| ✅ | 4a Registry candidates: same name, attested alias, or top 5 by embedding at 0.6 or more | code |
| ✅ | 4b Same-concept yes/no per pair, against the concept's entry; terms in one lecture merge only if every pair says same | verifier |
| ✅ | 4c Definition as of lecture k from all definitions so far, grounding-checked | verifier |
| ✅ | 5a Mentions: name and attested aliases in every part from the introducing lecture on | code |
| ✅ | 5b Facets: what each part says about each concept it mentions, or "only mentioned"; grouped per part | generator |
| ✅ | 6a Pair candidates: similar but different (4b), a facet in the part where the other is introduced, named in the other's definition or defining sentences | code |
| ✅ | 6b Relation: `kind_of` / `part_of` / `depends_on` (either direction) / none, with evidence | verifier |
| ✅ | 6c Code checks: evidence mentions both, no cycles, `depends_on` earlier → later (flagged otherwise) | |
| ✅ | 6d Link label written from the evidence, then checked; one rewrite | verifier |
| ✅ | 7a Lecture objectives from the part objectives (contiguous runs) | generator |
| ✅ | 7b Lecture goal from the objectives | generator |
| ✅ | 7c Course goals, bottom-up from the lecture goals | generator |
| ✅ | 8 Lecture map: Li → Lj weighted by concepts carried, top 3 incoming per lecture, carrier concepts listed | code |
| ✅ | Judge: part objectives (accurate for the part?) and key points (supported by their sentences, about the subject?); one rewrite by the verifier, then a key point is dropped and an objective kept and flagged | verifier, before the goals are built |
| ✅ | Judge: lecture objectives, lecture goals, course goals (accurate for what they group?); facets (supported by their sentences?); one rewrite, then a facet becomes a mention and a goal is kept and flagged | verifier |
| ✅ | Step order: generator (parts, objective, key points, candidates) → verifier (judge, key terms, registry) → generator (goals, facets) → verifier (judge, edges) | |
| ✅ | Assemble: `course.json`, `Lxx.json`, `decisions.jsonl`, alias index, concept embeddings; schema validation | `lir-v2/<course>/` |
| ✅ | Run report: time and calls per step, counts (candidates, kept, merges, edges by type), drop reasons | `output/<course>/v2/report.md` |
| ✅ | Entry point `generate_lir2.py` | |
| ✅ | Smoke test with a fake model (plumbing only, no GPU) | `tests/smoke_pipeline2.py` |
| ✅ | README: v2 and running on EC2 | |

### Phase 2: activity layer

Every item is tagged with the key points and concepts it tests and cites its sentences. Items are written by the
generator and judged by the verifier (a different, larger model); one rewrite by the verifier with the judge's reason,
then the item is dropped (a recap falls back to the part's key points). Built and checked with the same fake-model
smoke test; not yet run on a real model. Output: `lir-v2/<course>/activities/Lxx.json`,
kept apart from the knowledge files, with the default order (recall → watch, quiz, summary per part → concept map →
open questions) as a list renderers can follow or ignore.

| Status | Task | Notes |
|---|---|---|
| ✅ | Recall before lecture k: concepts carried by the lecture map's incoming links; one item per concept (question, answer) from the definition as of k−1 and earlier facets, with a jump-back sentence | up to 4 |
| ✅ | Quiz per part, plan: which key points are worth testing and the type of each (multiple choice / true-false / yes-no), 0 to 4 items | generator; earlier lectures come back through spaced review |
| ✅ | Quiz per part, write: one call per item; code puts the correct option at a fixed random position, checks options are distinct and the correct one does not stand out by length | v1: correct option longest in 56–64% |
| ✅ | Summary per part: recap (2–3 sentences); check-yourself questions only on key points the quiz does not test | v1: 88–91% overlap |
| ✅ | Concept map per lecture, by code: concepts introduced in the lecture plus earlier concepts it teaches about, ranked by links in the lecture's subgraph then facets, at most 14; seeds; edge labels from step 6d; choices logged | |
| ✅ | Open questions, plan: the model picks 2–4 questions (type, parts, concepts) from the lecture's content | generator |
| ✅ | Open questions, write: question, reference answer, 3–5 key points with keywords (in the reference answer) and cited sentences | generator |
| ✅ | Judge every item (recall, quiz, recap, review question, open question); rewrite once; drop | judge |
| ✅ | Spaced review after each part (shown after its quiz): earlier concepts the part teaches about that are due, re-asked with an earlier quiz item (least used first). "Tested" = in a quiz item or an open question; the gap doubles after each test when due (1, 2, 4, 8 lectures); once per lecture; concepts a new concept depends on first. Up to 4 candidates per part, the first 2 are the default | code, `pipeline2/act_spaced.py`; a renderer with learner history can pick other candidates |
| ✅ | Scorer calibration (m, τ) from good / partial / wrong answers written for a sample of open questions; key-point embeddings | v1 `calibrate.py` and `scorer.py` |
| ✅ | Activities schema and assembly; smoke test extended | |

### Phase 3: quality check and running it

| Status | Task | Notes |
|---|---|---|
| ⬜ | Full run on EC2: VR course | the user runs it; ask first |
| ⬜ | Hand check against v1 on the same lectures: registry (duplicates, aliases, definitions), links, key points, quiz, summary, open questions, concept maps | |
| ⬜ | Fix what the check finds; rerun from the cache | |
| ⬜ | Full run: Deep Learning course | |

### Phase 4: docs, other tests, viewer

| Status | Task | Notes |
|---|---|---|
| ⬜ | Viewer on LIR v2 (knowledge + activities) | |
| ⬜ | Live Q&A lookup: alias → concept → definition as of k, facets, edges, sentences; limited to the learner's position | serve.py API |
| ⬜ | Answer scoring in the viewer: open answers vs key points; concept maps through the alias index, direction, label meaning or relation | |
| ⬜ | Tests: lookups, scorer, schema round trip, leakage (nothing in lecture k cites a later lecture) | |
| ⬜ | `docs/pipeline.html` and README for v2 | |

## Pipeline (`generate_lir.py`)

| Status | Task | Notes |
|---|---|---|
| ✅ | Stages 1–5 and 7 from the design doc | segment, annotate, goal hierarchy, course state, generate, assemble |
| ✅ | Best segmentation prompt (standalone segments, WD 0.09) | unchanged from `event-segmentation/compare/REPORT.md` |
| ✅ | Gemma 4 E4B Q8 on llama.cpp, KV cache f16 (not quantized) | in the `llm-engine` toolbox |
| ✅ | Throughput tuning | 32 slots peak at ~630 tok/s (16: 498, 48: 629, 64: 612) |
| ✅ | Layer 1 (JSON schema) and layer 2 (code checks + retries with feedback) | |
| ✅ | Timing report written automatically | `output/<course>/timing_report.md` |
| ✅ | Test runs: VR 1–3 and Deep Learning 1–3 | VR ~2.7 min/lecture, DL ~6 min/lecture (before the judge) |
| ✅ | Server stop bug (server left running inside the toolbox) | now stopped by port |
| ✅ | Rename `provenance` → `origin` | |
| ✅ | Lectures without subtitles (VR 4, 5) | official transcript aligned to YouTube's automatic captions |
| ✅ | Layer-3 judge code: judge every item, repair (2 rounds), resolve leftovers by code | `pipeline/s6_judge.py` |
| ✅ | Interleaved quiz item (at most 1 per quiz, from an earlier lecture) | |
| ✅ | Scorer calibration (m, τ) from LLM-written good / partial / wrong answers | `pipeline/calibrate.py` |
| ✅ | Pass rates per stage and per judge check in the report | |
| ✅ | LIR written to `lir/<course>/` (build files stay in `output/`) | plus `lir/index.json` for the viewer |
| ✅ | One command: videos in the background, color-coded progress bars, ETA | `pipeline/ui.py`, `pipeline/media.py` |
| ✅ | `--lir-only` and `--videos-only` flags | |
| ✅ | Download the 12B judge model | 6.7 GB, `UD-Q4_K_XL` |
| ✅ | Test the judged run on VR 1–3 | 10.4 min, $0.019; judge passed 78% first time, repaired most of the rest, dropped 24/48 edges |
| ✅ | `lir_config.toml`: model per role (HF GGUF = local, OpenAI name = API); judge on `gpt-6-luna` | key from `.env` (git-ignored) |
| ✅ | API budget: $2.40 total, checked before every call, ledger `api_spend.json`, live in terminal and report | |
| ✅ | Local server restarted automatically if another run stops it | lets two runs share the GPU |
| ✅ | Judge speed: thinking cap per server (`--reasoning-budget`: judge 4096, generator 8192) | one judge call looped to 16k tokens without it |
| ✅ | Judge speed: open questions judged inside their segment's call; edges in groups of 6 | |
| ✅ | Full VR course run (all 63 lectures, judged, videos at 720p) | 2 h 51 min for 31 h of video (2.7 min/lecture); judge $0.52; 81% of 5,242 items passed first time |
| ✅ | Check the viewer on the full course | home, lecture 40, scoring API |
| ✅ | Portable: answer cache in git, requirements files, “run on another PC” in README | videos re-downloaded with `--videos-only` |

## Viewer (`viewer/`, `serve.py`)

| Status | Task | Notes |
|---|---|---|
| ✅ | Runtime scorer module (keywords + CPU embeddings) | `scorer.py`, same code as calibration; word-level keyword sets + WordNet synonyms, as in the doc |
| ✅ | Concept canonicalization: aliases "(AR)" and acronyms | fixed AR / augmented reality duplicates |
| ✅ | `serve.py`: static files with video seeking (HTTP Range), `/api/score`, `/api/cmap` | CPU only; tested |
| ✅ | Home page: course goals, full roadmap, Start / Continue | loads the whole course LIR |
| ✅ | Primer: goal, objectives, key terms, recall items with jump links | |
| ✅ | Segment: local video, optional captions with live highlighting, learner highlights | YouTube fallback if no local file |
| ✅ | Quiz: item cards, explanations after all items are answered | |
| ✅ | Summary: recap, key concepts on click, key terms, earlier links, learner highlights | |
| ✅ | Open questions: Excellent / Good / Acceptable / Try again, missed key points, revise, reference | keyword fallback offline |
| ✅ | Concept-map task: build, score, show reference | |
| ✅ | Learner-facing design: no build stats, "Lecture N" not IDs, no segment numbers | intents and rule IDs only in review mode (`?review`) |
| ✅ | Fix: lists of elements rendered as `[object HTMLDivElement]` | found by headless-Chrome screenshots |

## Round 2: review feedback (2026-10-30)

| Status | Task | Notes |
|---|---|---|
| ✅ | Lecture as pages: Before you start → (Watch, Quiz, Summary) per segment → Concept map → Questions | Next always goes to the next activity |
| ✅ | Watch page: only the segment's clip, full width, own controls (no native controls), end card | clip enforced in the player, no re-encode |
| ✅ | Captions off by default; click a caption to highlight it (no transcript panel) | |
| ✅ | Quiz: second try on a wrong multiple-choice answer, explanations after | |
| ✅ | Summary page: recap, check-yourself cards (click to reveal, ▶ jump back), earlier links, highlights | no key terms |
| ✅ | Concept map page full width; reference map with dagre (layered, arrows, label pills), pan/zoom, ≤ 14 nodes | `viewer/vendor/dagre.min.js`, works offline |
| ✅ | Reference map locked until the learner checks their map | |
| ✅ | Questions page; hint from a keyword, key points after 2nd try, reference answer after 2 tries | |
| ✅ | Prerequisites on Before you start (“try to recall”, reveal on click) | |
| ✅ | Capitalized concept and term names | |
| ✅ | Dev mode toggle (`?dev=1`): answers, intents + source sentences, origin, judge verdicts | replaces `?review` |
| ✅ | serve.py: only serve viewer/, lir/, media/, docs/ (it used to list the folder, `.env` included) | |
| ✅ | Prompts: key points tagged subject / course; terms v3 (glossary terms, self-contained definitions); quiz v3 (model picks 1–4 items and types); summary v2 (review questions); recall v2; edges v3 (complete labels) | |
| ✅ | Code checks: definitions (no It/This, not circular, no bare abbreviation), subject-not-lecture questions, label endings | `pipeline/validate.py` |
| ✅ | Judge: key term worth learning + faithful + useful; quiz item worth asking; summary review questions; not-worth items dropped at once; concepts with no surviving definition leave the registry | |
| ✅ | Prerequisites for every lecture after the first: edges, then concepts mentioned again | |
| ✅ | Docs and README updated | |
| ✅ | Test 1 on VR 1–3 (12 min, $0.03): no acronym cards, quizzes 0–4 by content | found 4 issues, fixed below |
| ✅ | Fix: "Term (ABBR)" key terms were not linked to their concept, so a rejected definition stayed in the registry | `s4_state.py` |
| ✅ | Definitions in clear own words, not copied speech; one concept per term; no repetition (prompt + code + stricter judge) | |
| ✅ | Questions that talk about the lecture ("mentioned in the lecture") rejected; true/false repairs must be statements | |
| ✅ | Edges the judge finds reversed are flipped by code instead of dropped | |
| ✅ | Review questions only for subject key points | the open-question fallback limit was reverted: it cut L01 to one question |
| ✅ | Test 2 and 3 on VR 1–3, then regenerated the whole VR course | 63 lectures, 388 parts, 883 concepts, 417 edges, 1,272 quiz items, 1,356 review questions, 101 recall items, 236 open questions; judge: 4,903 items, $0.73; about 3.7 h on the RTX 5070 |
| ✅ | API client waits out network drops (up to ~15 min) instead of stopping the run | the first full run stopped in judge round 2 on a certificate error; resumed from the cache |
| ⏸ | Content quality (open-question types, key-point wording, review quiz items, recall coverage, prompts) | superseded by LIR v2 (top of this file) |

## Deep Learning course (MIT 6.7960) full run (2026-10-31)

| Status | Task | Notes |
|---|---|---|
| ✅ | Full run with videos: 23 lectures, 29 h of video, 280k words (lecture 22 is not in the dataset; the PyTorch tutorial is not a lecture, so it is not built) | 3 h 34 min; 378 parts, 779 concepts, 192 edges, 1,346 quiz items, 1,418 review questions, 44 recall items, 184 key terms, 84 open questions |
| ✅ | API budget capped at the remaining credit: `budget_usd = 2.28` | this run $0.74 (959 calls); $2.08 of $2.28 used, about $0.20 of credit left |
| ✅ | Local fallback judge: when the API budget is spent, the blocked judge calls go to Gemma 4 12B (`[judge_fallback]` in `lir_config.toml`); items it judged are counted in `quality` | in README and docs; not needed by either course |
| ✅ | Resume with `--lir-only` if items were left unjudged | not needed: all 4,130 items were judged by the API (74% passed first time, 145 concepts left the registry) |
| ✅ | Final QC on both courses: schema, cross-references, videos, every shipped quiz item, viewer pages | all 86 lectures validate; 86/86 videos; 2,618 quiz items with valid answer keys and 4 options for multiple choice; 320 open questions with reference answers; items that failed layer 2 were dropped, not shipped |
| ✅ | Docs: NPTEL vs MIT comparison (per-hour measures, content mix, pass and drop rates, build time by stage, cost, full table) | `docs/pipeline.html#compare` |

QC notes for the content review (not changed):
- Definitions sometimes keep sentence numbers from the prompt, e.g. "… minimizes a cost function (242-244)." (DL L01).
- Wrap-up activities and key terms have a limit per lecture, so MIT (75-minute lectures) gets half as many per hour of video: 2.9 open questions per hour vs 7.6, 6.3 key terms vs 15.0, 6.6 links vs 13.4. Possible change: scale the limits with lecture length.
- Some quiz items test trivia rather than the subject, e.g. DL L08: "Transformers are the current architecture that is highly relevant for securing jobs in the field."
- Model wording slips through in objectives, e.g. "Graph Neural Nn." (DL L08).
- The layer-2 errors most often seen are true/false and yes/no answers swapped between item types (both courses).

## UI refinement (2026-10-31)

| Status | Task | Notes |
|---|---|---|
| ✅ | True-black default theme with a light mode (toggle in the top bar, `?theme=light`) | dark is the default whatever the OS setting |
| ✅ | New type: Sora (headings), Geist (text), Geist Mono (times, numbers, labels) | Google Fonts, system fallbacks offline |
| ✅ | Home: hero with progress ring; goals list; roadmap drawn as a path with a node per lecture | course stats only in dev mode |
| ✅ | Lecture shell: glowing progress line under the top bar; contents list drawn as a track | |
| ✅ | Watch: controls float over the clip and hide while it plays; ambient glow from the video behind the player; top bar dims while playing | |
| ✅ | Motion: pages rise in; answer cards open smoothly; right answers pop, wrong ones shake; rings sweep in; `prefers-reduced-motion` respected | |
| ✅ | Concept map: pill nodes, seed concepts glow, the reference map draws itself in, hover isolates a concept and its neighbours, definitions on hover | |
| ✅ | Recall items use the same reveal cards as the summary | |
| ✅ | Learner map editor: same polish as the reference | curved links with arrows that stop at the node edge, dot grid drawn in the map with snapping, dashed preview line while linking, "Tidy up" lays the map out with dagre and glides there |
| ✅ | Course home: a compact view for long courses | List / Grid toggle (remembered; grid is the default above 30 lectures); tiles in course order with progress and "up next"; course-goal chips dim the other lectures (goals are not contiguous in MIT, so no sections) |
| ✅ | Mobile pass on the watch page and top bar | top-bar words fold into icons below 600 px; scrubber on its own row; smaller play button; captions move to the top of the clip while the controls show; landscape phones fit the whole clip |
| ✅ | Course map at the end of the course (`#/map`): every lecture's reference concept map joined into one, no generation | after the last lecture's questions ("Next: Course map") and as the last card on the home page; concepts coloured and grouped by course goal; click a goal or a concept to zoom in; definition, ▶ jump to where it was taught, and links in a side panel; search; "Grow" replays the map lecture by lecture; labels never overlap and more appear as you zoom; pinch zoom on phones |
| ✅ | Math in the text rendered with KaTeX (vendored in `viewer/vendor/katex/`, works offline) | 763 formulas in the two courses (DL 393 strings, VR 50), all render; backslashes that JSON turned into control characters (`\theta` → tab + "heta") are repaired by stage 7 (`fix_math` in `s7_assemble.py`) and at display time; the existing files were repaired in place (32 strings in 13 files, nothing else changed) |

## Documentation

| Status | Task | Notes |
|---|---|---|
| ✅ | README | |
| ✅ | `docs/pipeline.html` rewritten by hand (no generator): use case first, then the learner's lecture, how it is built, quality, cost, running it, reference | VR course stats and charts; `build_docs.py` / `docs_formal.py` removed |
| ✅ | Docs, formal detail: division of work, lecture representation, graph representation | now in the Reference part |
| ✅ | Docs: configuration, every field, local vs API examples | `[judge_fallback]` added |
| ✅ | Docs: NPTEL vs MIT comparison | section "NPTEL vs MIT" in part 3 |
| ✅ | Docs: "The lecture as data" (what the LIR allows: O(1) coverage lookups, segment-wise fetch, RAG chunks, advantages) | part 3, `#lirdata`; lookups tested on the VR LIR |
| ✅ | Docs: Part 4 "A run, call by call": L01 through every stage with real prompts and answers, batches, parallelism, call counts | prompts and answers from an offline replay of the answer cache (5,149 calls, 0 misses; rebuilt LIR identical to `lir/` apart from map node order); slot timeline from the generator's server log |

## Notes

- vLLM 0.32.0 installed in the toolbox venv (`lir-construction/.venv`, torch 2.13 + CUDA 13, sees the RTX 5070), but the FP8 model does
  not fit the 12 GB card (embedding tables stay bf16, about 11 GB for the model alone). llama.cpp Q8 is the engine.
