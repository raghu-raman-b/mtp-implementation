# Tasks

Status: ✅ done · 🔄 in progress · ⬜ to do · ⏸ on hold · ⚠️ blocked or needs a decision

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
| ⏸ | Content quality (open-question types, key-point wording, review quiz items, recall coverage, prompts) | on hold: the user evaluates both courses first and sends the issues |

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

## Notes

- vLLM 0.32.0 installed in the toolbox venv (`lir-construction/.venv`, torch 2.13 + CUDA 13, sees the RTX 5070), but the FP8 model does
  not fit the 12 GB card (embedding tables stay bf16, about 11 GB for the model alone). llama.cpp Q8 is the engine.
