# MVP test report: pipeline v3 on the VR course (63 lectures)

2026-11-13, tested read-only against `pipeline/output/nptel_vr/` at commit 6977ae5. Nothing under `pipeline/` was
written: the QA logs and query-embedding cache went to `analysis/mvp/qa_run/out/` (through `QA_OUTPUT`), and the llama.cpp
server log went to `analysis/mvp/qa_run/llm_server_8092.log` (a copy of the Gemma config with only `server_log`
changed). `git status` was clean before and after.

Files in `analysis/mvp/`: `integrity.py` (an independent integrity check), `show.py` (prints an activity with its
cited facts and the transcript sentences behind them), `qa_run/run_qa.py` (the question set, run in one process),
`qa_run/view.py`, `qa_run/results.jsonl` (first run, 36 questions), `qa_run/results_run2.jsonl` (rerun of 20, for
stability), `qa_run/run.log`, `qa_run/viewer.log`.

## Summary

| Area | Result |
|---|---|
| Contract and references | **Clean.** 1,208 activities and 1,107 cards; every fact, concept, relationship, segment and lecture they cite exists; item facts are a subset of their activity's facts; crossword grids are consistent; complete-map answers are correct |
| Knowledge layer check | **Clean.** 72 files, 208,243 references, no schema, reference, duplicate-ID or coverage problems |
| Unresolved items | 5, all crosswords (lectures 13, 21, 29, 51, 58). In each, one clue kept a word of its answer, so code replaced that word with `___`. The grids work, but the same five crosswords also hold some of the weakest clues in the course |
| Model-written kinds (quiz, open question, recap, odd one out, put in order) | **Good.** None of the 60 sampled quiz questions has a wrong key. All 32 sampled open-question reference answers are supported by their facts. Recaps are faithful. Main weakness: in **52%** of the 1,443 quiz questions the correct option is the single longest |
| Code-made kinds built on definitions (recall, match pairs, crossword clues, spaced review) | **Weak.** Stage 4a was skipped, so each "definition" is a concept's first defining fact, and only about 26% of those read like definitions. Match pairs is the weakest kind |
| Question answering (Gemma 4 12B, GPU free) | **Strong and fast.** 36 questions, 56 answers. Median **6.1 s**, p90 11.5 s, max 20.9 s (a not-covered question). All answers are grounded, with no wrong citation. The two not-covered probes and the off-topic one were declined correctly |
| Viewer | Every route works, including video Range requests and `/api/ask` (3.6 s). Dev mode is off by default. **Answers show markdown raw** (`**bold**`, `* ` bullets, `$\omega$`). Concept maps above about 30 nodes are unreadable at "Fit" |

## 1. Integrity

### Commands

- `python3 scripts/s5_activities.py nptel_vr --check` printed `contract: all good`, exit 0. `--check` only reads.
- `python3 scripts/s4d_assemble.py nptel_vr --check` was **not run**: its `--check` path writes
  `output/nptel_vr/stage_4d_assemble/checks.json` (s4d_assemble.py line 364). I ran the same check read-only
  instead (`check_layer(knowledge_dir('nptel_vr'))` plus `summarize`). It found `72 files, 208243 references: all good`,
  with 0 schema errors, 0 broken references, 0 duplicate IDs, 0 coverage problems and 0 unchecked files. The report
  is identical to the stored `stage_4d_assemble/checks.json`.
- My own check, `python3 analysis/mvp/integrity.py`, rechecked everything from scratch:
  - 1,208 activities: quiz 347, recap 347, put_in_order 75, concept_map 63, complete_map 63, match_pairs 63,
    odd_one_out 63, open_question 63, crossword 62, recall 62.
  - Every fact, concept and relationship cited exists, on activities, items, edges, entries and pairs alike.
  - Every map edge matches its relationship's subject and object.
  - Every item-level `facts` / `key_facts` list is a subset of its activity's `facts`.
  - Every segment activity cites only facts from its own segment.
  - Every open question has at least 2 key facts.
  - Crossword grids have no letter clashes, and no clue contains a 4-letter-or-longer word of its concept's name.
  - Every complete-map blank's answer equals the hidden label or name and is among its options. No hidden concept is
    visible on another edge.
  - Quiz answer positions are balanced: 370 / 349 / 364 / 360.

### Gaps that the contract allows

- Lecture 1 has no `recall`: no earlier concept exists.
- Lecture 63, "Concluding remarks" (5 facts), has no `crossword`.
- 9 lectures have no `put_in_order`: 2, 4, 5, 8, 10, 22, 40, 49, 63. The model found no ordered steps in them.

### The 5 unresolved items

All five are Gemma's crossword clue calls. Three attempts each. In the kept attempt, one clue still used a word of the
answer (or of one of its other names), so code masked that word with `___` (`clue_masked`).

| Activity | Masked clue (final) | Other weak clues in the same grid |
|---|---|---|
| 13/A19 | PINCHGLOVE: "Data ___ with detectors only at fingertip positions for discrete selection" | ORGANISM "A part of the total perspective along with hardware and the physical world" and COMPUTER "One of three major hardware components, listed last in the sequence" (both obscure) |
| 21/A11 | SCENEGRAPH: "Tree-based structure of links representing a computer ___ environment" (the masked word is "graphics": over-masking) | OPENSCENEGRAPH "Publicly available library that has a successor" (obscure) |
| 29/A11 | PRESENCE: "Psychological side capturing whether a ___ perceives immersive qualities" (the masked word is "user": over-masking) | INNEREAR, OUTEREAR and MIDDLEEAR all have the same clue ("One of the three parts of the human hearing system"). AUDIORECORDING "A virtual reality experience even if other senses are missing" is odd |
| 51/A21 | TRAVELTIME: "A ___ computed between two directly connected nodes using a walking-speed model" | **SHORTESTPATH "Visiting every node once and returning to the starting point" is wrong: it describes the travelling salesman tour.** VNAUGHT is obscure. ALGORITHM is generic |
| 58/A20 | VIEWPIPELINE: "...window-to-___ transformation" (the masked word is "viewport") | DELTAY "Difference between their y coordinates" (a dangling "their"). POINTRENDERING is clued with the rounding method |

The root cause is shared with the clue problems in section 2: the clue writer gets the concept's "definition", which
is the first fact that mentions the concept (4a skipped). SHORTESTPATH's definition is the TSP fact, and UNITYPREFAB's
is the Unity-asset fact.

### Housekeeping

`activities/checks.json` describes only the last run: the local Gemma kinds for lectures 9-63. The Qwen kinds' checks
are in `activities_ec2/checks.json` (flags: quiz.correct_longest 66, odd_one_out.not_a_concept 34,
quiz.correct_not_in_facts 1, 1 retry), and lectures 1-8 and 16 are in `checks_demo.json`. Anyone who reads
`checks.json` alone sees only part of the run.

## 2. Quality by reading (stratified sample)

**The sample.** I drew a seeded sample stratified over lectures 1-63: 66 activities of all ten kinds. For each item I
read the activity, the full text of every cited fact, and the transcript sentences behind each fact (`show.py`). I
also read everything in lectures 9, 23, 30 and 36 and the five unresolved crosswords.

Sample IDs:

- quiz: 3/A3 9/A6 17/A3 22/A3 28/A4 34/A10 39/A13 40/A5 46/A10 50/A4 57/A1 58/A15
- recap: 5/A2 18/A8 20/A4 27/A15 35/A12 46/A8 51/A6 58/A14
- open_question: 1/A16 14/A15 18/A27 24/A17 36/A16 42/A22 49/A14 60/A15
- odd_one_out: 7/A19 15/A16 22/A13 26/A18 36/A15 45/A22 51/A22 63/A6
- put_in_order: 11/A18 20/A11 28/A3 36/A5 43/A10 56/A5 59/A5
- crossword: 2/A8 16/A13 30/A15 36/A14 49/A12 60/A13
- match_pairs: 10/A11 24/A14 28/A12 45/A20 61/A17
- complete_map: 12/A13 30/A13 37/A12 57/A15
- concept_map: 4/A7 21/A8 43/A11 56/A25
- recall: 7/A0 31/A0 37/A0 56/A0

### Counts

| Kind (units judged) | Clean | Problems (count: type) | Examples |
|---|---|---|---|
| quiz (60 questions) | 56 | 0: wrong key or unsupported answer. 1: ambiguous distractor. 3: give-away distractors (mirror or "only left/right" options). Course-wide: correct option uniquely longest in 52% (751/1,443) | Ambiguous: **3/A3 Q2**. "Try cosmetic looks on a digital face" is also a pre-purchase AR app (fact 3/S1/F3). Give-away: **57/A1 Q1** (VR more / fewer / same / AR more), **28/A4 Q4-Q5** ("Only the right image"). Length: **58/A15 Q2**, **34/A10 Q2** |
| recap (8) | 5 | 2: small drift. 1: vague | Drift: **27/A15** "Central vision requires the eyes to be focused on the fovea" (the fact says pointed straight at the object). **35/A12** reworded priority. Vague: **58/A14** "several layers" drops the layer list |
| open_question (32 questions) | 28 | 0: unsupported reference answer. 3: forced cross-lecture link. 1: answer doesn't address "how" | Forced: **18/A27 Q4** (3D structure tracking vs the AR continuum), **60/A15 Q4** (Unity preference tab vs the continuum), **1/A16 Q2**. "How": **18/A27 Q2** (never says how hybrid tracking fixes inertial drift) |
| odd_one_out (20 puzzles) | 16 | 3: contestable. 1: forced | **15/A16 #2** (Battery/Speaker/Projector/Camera: the Blade also has a camera, and the HoloLens battery is not mentioned). **7/A19 #3** (the cyber code system is itself a marker system). **51/A22 #2** (bare "Model" against Speed/Teleport/Terrain). **63/A6** |
| put_in_order (7) | 4 | 1: trivial. 1: weak first step. 1: not a real sequence | Trivial: **11/A18** (3 obvious steps). **43/A10** ("prepare team" is only implied). **59/A5** mixes cause, design, effect and requirement into a "sequence" |
| crossword (63 clues in 6 grids) | 49 | 8: vague or not unique. 5: obscure, no context. 1: wrong | Vague: **60/A13** SCENEVIEW / GAMEVIEW ("One window in the software...") and UNITYSCENE; **2/A8** HEALTHCARE, EDUCATION. Obscure: **16/A13** "The second of the four steps" (x4, never says which four); **2/A8** DEFENSE "about 4% of the total areas". Wrong: **60/A13** UNITYPREFAB clued as "Visual or audio elements such as 3D models or textures" (that describes an asset) |
| match_pairs (40 pairs) | ~12 | ~20: list sentence as cloze, cut with "…", or near-identical right sides. ~8: the right side is not that term's definition | Not its definition: **10/A11** motion sickness → internal-factors sentence; **45/A20** controlled experiment → usability-assessment sentence; **28/A12** retina → light-path sentence. Twins: **61/A17** material/texture, **24/A14** input/output device |
| complete_map (16 blanks) | 13 | 1: near-duplicate option. 2: long-fragment options | **37/A12** "is for" alongside "is for covering a". **12/A13** the answer is the only long fragment. **5/A10** (outside the sample) blanks the same pair twice |
| concept_map (32 edges read) | 28 | 4: fragment labels. Size: median 73 nodes, 42 of 63 maps exceed 60 nodes | "has as an example in this categorization", "display --is used to build--> augmented reality" (21/A8). 21/A8 shows both **AR Toolkit** and **augmented reality toolkit** |
| recall (22 items) | 12 | 10: the answer is not a definition. Repetition: "virtual reality" is recalled in 30 lectures, "augmented reality" in 19 | **7/A0** "What is head-mounted display (HMDs)?" → the history of the formative years. **31/A0** neuron → "Perception depends on the interconnection of neurons". **56/A0** lighting / object representation / modeling transformation → the same 5-stage list sentence |

Course-wide measure for the definition-based kinds: of the 1,107 spaced-review cards, only **283 (26%)** have a back
that starts like a definition ("<name> is / are / refers..."). The rest begin with a list or a context sentence. For
example, teleportation → "The type of transition, meaning how the scene changes..." and human eye → "Light incident on
the human eye passes...". The same text feeds recall answers, match pairs, crossword clues and the concept card's
"definition" in the viewer.

### What is good

Quizzes and open questions (Qwen) are the strongest material. Facts are restated faithfully. Distractors are usually
real neighbouring concepts from the same lecture: the other fidelity types, the other tracking techniques, the other
statistical tests. Examples: 17/A3 (IMU calibration with C1/C2), 9/A6 (the three fidelities), 46/A10 (choosing a
significance test), 36/A6 (affinity diagram). Recaps (Gemma) read well and stay on their facts.

### Duplicate concepts (3b skipped; reported, not fixed)

- Acronym / expansion twins (6 pairs):
  - VR headset C0077 / virtual reality headset C0222
  - AR Toolkit C0296 / augmented reality toolkit C1229
  - extended reality engine C0724 / xr engine C1373
  - three-dimensional model C0981 / 3D model C3082
  - iPhone operating system C1147 / ios C3361
  - Majuli virtual reality tour C1967 / Majuli VR Tour C2370
- Synonyms: headset C0005, head-mounted display C0040, virtual reality headset C0222 and VR headset C0077.
- **11 lecture concept maps show two or three of the headset family together:** 2/A5, 6/A14, 10/A9, 11/A19, 13/A16,
  15/A12, 16/A10, 17/A10, 20/A16, 28/A10, 44/A15. 6/A14 and 15/A12 show all three of headset, head-mounted display
  and virtual reality headset.
- "head-mounted display" has no "HMD" alias. QA still resolves "HMD" through the acronyms index.

## 3. Question answering (Gemma 4 12B, local llama.cpp on an RTX 5070, GPU otherwise idle)

Setup: one process, thinking on (the config's budget, 8k). The server started in 4 s. The first warm-up took 16 s
(embedder plus server), later ones 12.5 s. The table shows run 1's time, then run 2's for the 20 questions asked again.

| ID | Kind | Question | Time s (run1 / run2) | Tools | Citations (lectures) | Covered | Verdict |
|---|---|---|---|---|---|---|---|
| Q01 | definition | What is extended reality? | 3.7 / 3.1 | check_concept | 3 (1, 2) | yes | Correct, grounded |
| Q02 | definition | What is presence in virtual reality? | 6.8 | check_concept | 8 (8, 9, 11) | yes | Correct, rich, grounded |
| Q03 | how | How does inside looking out infrared tracking work? | 6.1 | check_concept, fact_lookup | 4 (16, 18) | yes | Correct. The unknown name was recovered by fact_lookup |
| Q04 | how | How is a cheap gyroscope calibrated using C1 and C2? (lecture 17) | 7.5 | check_concept, fact_lookup | 2 (17) | yes | Correct. **LaTeX in the answer** (`$\omega_{cal}$`) shows raw in the viewer |
| Q05 | compare | How is AR different from VR? | 11.5 / 12.7 | check_concept x2 | 6 (1, 3, 5, 7) | yes | Correct, cross-lecture. One small embellishment ("mostly distinct" phases) |
| Q06 | compare | Optical vs video see-through HMDs? | 7.3 | check_concept x2 | 1 (14) | yes | Correct but thin. The layer only has their uses (AR vs augmented virtuality) |
| Q07 | compare | Full gait vs partial gait vs gait negation? | 8.8 / **19.0** | check_concept x3, fact_lookup | 5 (40) | yes | Correct, with examples. Time varies |
| Q08 | list | What are the causes of cybersickness? | 6.1 | check_concept | 7 (10, 11, 49) | yes | Correct, complete taxonomy |
| Q09 | list | Five stages of contextual inquiry? | 4.3 | check_concept | 1 (36) | yes | Correct. The same citation repeats after each of 5 lines (clutter) |
| Q10 | list | Parts of the human hearing system? | 3.0 | check_concept | 1 (29) | yes | Correct |
| Q11 | where | In which lecture is stereoscopy taught? | 1.8 | check_concept | 1 (28) | yes | Correct. The text says 14:25 but cites the segment at 11:44 (two times shown) |
| Q12 | where | Where does the course explain the uncanny valley? | 4.0 / 3.1 | check_concept | 6 (9) | yes | Correct. Same two-times pattern |
| Q13 | prereq | What do I need before lecture 40? | 7.3 / 6.7 | lecture_dependencies | 14 (3, 4, 11, 19, 37-40) | yes | Grounded. Some prerequisites are odd (location awareness, markers): a lecture-graph issue |
| Q14 | purpose | What is lecture 51 for? | 4.4 / 5.0 | lecture_overview | 6 (51) | yes | Correct, clear |
| Q15 | acronym | What is an IMU? | 4.2 / 4.2 | check_concept | 4 (17) | yes | Correct |
| Q16 | acronym | what is HRTF | 6.7 / 6.7 | check_concept | 4 (30) | yes | Correct |
| Q17 | misspelling | what is cybersicknes | 7.3 / 7.4 | check_concept | 10 (10, 26, 49) | yes | Correct. Name matched despite the typo |
| Q18 | misspelling | explain steroscopy | 2.5 | check_concept | 1 (28) | yes | Correct (matched as 'close') |
| Q19 | not covered | How does a Kalman filter fuse IMU and camera data? | **20.9 / 18.4** | check_concept, fact_lookup | 3 (17, 18) | no | Correct refusal, then related grounded facts. **Slowest type** |
| Q20 | not covered | Vergence-accommodation conflict? | 9.2 | check_concept, fact_lookup | 3 (25, 27, 28) | no | Declines, but pads with loosely related facts. Less crisp |
| Q21 | tracking | What is drift correction and why is it needed? | 5.0 | check_concept | 5 (16, 17) | yes | Correct |
| Q22 | displays | FOV and why it matters for cybersickness? | 7.4 / 6.6 | check_concept | 8 (11, 12, 28) | yes | Correct, nuanced (narrow FOV helps, too narrow hurts) |
| Q23 | perception | Why is peripheral vision better at detecting movement? | 4.4 | fact_lookup | 3 (27) | yes | Grounded parts. The "because rods" causal link is the model's inference |
| Q24 | interaction | What is world in miniature? | 3.9 | check_concept | 3 (39) | yes | Correct |
| Q25 | cybersickness | How does teleportation help reduce cybersickness? | 12.1 | check_concept | 2 (11, 51) | yes | Correct |
| Q26 | rendering | Why are GPUs used for rendering in VR? | 4.6 / 5.4 | check_concept | 3 (14, 58) | yes | Correct, cross-lecture (14 and 58) |
| Q27 | haptics | What kinds of haptic feedback devices does the course mention? | 7.0 | check_concept, fact_lookup | 4 (14) | yes | Correct, incomplete (misses lecture 31's pin array) |
| Q28 | methods | Test for within-subject, one factor, two levels? | 4.7 | fact_lookup | 2 (46) | yes | Correct (paired t, Wilcoxon, McNemar for nominal data) |
| Q29 | not covered | Who won the 2022 FIFA World Cup? | 5.2 / 2.4 | course_goals / none | 0 | no | Correct refusal |
| Q30 | list | Three characteristics of a VR system? (lecture 4) | 11.4 / 3.5 | check_concept (+fact_lookup) | 3-4 (4) | yes | Correct |
| Q31 | compare | Difference between immersion and presence? | 6.9 / 6.7 | check_concept x2 | 9 (2, 8, 9) | yes | Correct, excellent |
| Q32 | compare | Electromagnetic vs acoustic tracking? | 4.0 / 4.8 | check_concept x2 | 2 (18) | yes | Correct, crisp |
| Q33 | purpose | What is lecture 36 for? | 3.7 / 3.3 | lecture_overview | 4 (36) | yes | Correct |
| Q34 | how | How does the Wizard of Oz approach work? | 7.0 / 7.0 | check_concept, fact_lookup | 4 (42) | yes | Correct, with the IBM 1984 example |
| Q35 | prereq | What do I need before lecture 16? | 7.3 / 7.3 | lecture_dependencies | 10 (1, 3, 5, 6, 8, 9, 13) | yes | Grounded. Odd items (augmented virtuality; HMD = "displays from the 1950s") |
| Q36 | prereq | What do I need before lecture 30? | 5.2 / 6.0 | lecture_dependencies | 6-7 (1, 4, 8, 10, 29) | yes | Correct. Run 1 listed "presence" under lecture 29; run 2 was clean |

**Timing** over all 56 answers: median 6.1 s, mean 6.7 s, p90 11.5 s, min 1.8 s, max 20.9 s. This morning, with the GPU
shared, answers took 23-94 s. The not-covered path is the slowest (18-21 s for the Kalman question: it searches with 5
rephrasings). Multi-concept comparisons can spike: Q07 took 8.8 s, then 19 s. The `/api/ask` call through the viewer
took 3.6 s.

**Grounding:**

- No wrong citation found: every cited fact supports its sentence.
- No substantive claim lacks a citation. The only uncited sentences are lead-ins ("The five stages ... are:") and
  Q29's one-line description of the course.
- Small issues: two inferred causal links (Q23, Q25: "because"), one embellishment (Q05), and the double-time display
  for "where" questions. That display comes from a fact time in the text next to a segment citation.

**Presentation risk:** 31 of the 56 answers contain markdown (`**`, `* `, `- ` bullets) and one contains LaTeX. The
viewer prints answers as plain text (`.qa-a { white-space: pre-wrap }`, a text node), so the asterisks and `$...$`
appear literally on screen.

Another limit on precision: citation times are the start of the fact's first evidence sentence, which is often the
topic's introduction. 462 of the 2,006 facts share their start time with 2 or more others in the same segment. For
example, all six contextual-inquiry stage facts point to 3:55.

## 4. Viewer on the real layer

I ran `python3 pipeline/viewer/serve.py nptel_vr --port 8771` (with `QA_OUTPUT` / `QA_CONFIG` pointing at
`analysis/mvp/qa_run`) and stopped it by PID each time (`kill <pid>`; the port is free afterwards).

- Start banner: `segments 63, knowledge 63, activities 63, videos 63 ...; question answering importable`.
- `/` 200; `/static/app.js` 200 (65 KB); `/static/style.css` 200.
- `/api/course` 200 (448 KB: 63 lectures, goals, layers knowledge / activities / spaced_review all true).
- `/api/lecture/4`, `/9`, `/30`, `/36`, `/63` all 200 (37-91 KB), each with segments, sentences, knowledge and
  activities (lecture 30 has all ten kinds), `video: true` and a YouTube ID.
- `/api/lecture/99` returns 200 with an empty placeholder (`source: none`), not 404. This is by design ("a missing
  layer is never an error"), but a mistyped lecture key shows an empty page.
- `/data/knowledge/concepts.json` 200 (5.6 MB), `lectures/lec_30.json` 200, `lecture_graph.json` 200;
  `fact_embeddings.json` 404 (as designed); `/data/activities/lec_30.json`, `course.json` and `checks.json` all 200.
- `/media/30` with `Range: bytes=0-1023` returns 206; HEAD returns `Accept-Ranges: bytes`, `video/mp4`.
- Path traversal attempts (`..%2F`, `/static/../serve.py`) return 404.
- `POST /api/ask {"question": "What is psychoacoustics?", "lecture": "30"}` took 3.6 s and returned 3 citations
  (lecture 30), covered true. An empty question gets "Please type a question."
- Headless Chrome screenshots (fresh profile): dev mode is off by default, and no IDs or counts are visible. **The
  lecture concept map at "Fit" is readable only for small or tall maps:** lecture 4 (19 nodes) and lecture 23 (32
  nodes) look good. Lectures 8, 9, 17, 30 and 36 render as a wide strip with unreadable labels until you zoom (+ or
  Ctrl+scroll).

## 5. Issues, ranked

1. **Markdown and LaTeX shown raw in the answer box.** 31/56 answers are affected. This is the most visible problem on
   stage. Fix in the viewer (render bold, bullets and inline code) or in `qa_system.txt` (plain text only).
2. **Definitions taken from first facts (4a skipped).** Only 26% read as definitions. This degrades recall, match
   pairs, crossword clues, spaced-review cards and concept-card definitions, and causes the wrong clues (SHORTESTPATH,
   UNITYPREFAB). Real 4a fixes it at the source.
3. **Match pairs are the weakest kind.** About 70% of pairs are list clozes, truncated, near-identical or mismatched.
   Keep them out of the demo.
4. **The correct quiz option is uniquely longest in 52% of questions** (chance is about 25%). A test-wise learner can
   game it. A stronger check than the report-only 1.5x `correct_longest` flag, plus a retry, would help.
5. **Synonym concepts (3b skipped).** The headset family appears together in 11 lecture maps, and there are 6
   acronym/expansion twins. It looks bad on maps and concept lists.
6. **Large concept maps** (median 73 nodes; 42/63 over 60). Unreadable at Fit; inverse duplicate edges ("occurs at" /
   "is a level of") add clutter.
7. **Crossword clue context.** Ordinal clues ("The second of the four steps"), identical clues for sibling answers
   (three ear parts), statistics clues ("about 4%"), and over-masking in the unresolved five.
8. **Recall repeats lecture-1 concepts.** "Virtual reality" appears in 30 lectures' recall and "augmented reality" in
   19. The prompts are ungrammatical ("What is head-mounted display (HMDs)?").
9. **Not-covered answers are slow** (about 20 s), and the "vergence" one pads with loosely related facts.
10. **Prerequisite answers include odd concepts** (lecture graph: location awareness or markers before lecture 40,
    augmented virtuality before 16).
11. **Coarse citation times:** 462 facts share their time with 2 or more others, because the first evidence sentence
    is often the topic's introduction.
12. **Small things:**
    - `activities/checks.json` covers only the last run.
    - `/api/lecture/<bad key>` returns 200 with an empty page.
    - "Where is X taught" answers show two different times.
