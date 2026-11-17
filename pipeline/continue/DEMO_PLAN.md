# Demo plan: the VR course as a learning companion (rebuilt layer, 2026-11-17)

**The story in one line.** From nothing but 63 lecture videos and their transcripts, the pipeline builds a learning
companion: every lecture cut into the steps it teaches, every concept traced to the moment it is taught and given a
definition, a question box that answers only from the course and cites lecture and time, and a full set of activities
and games, each checked by a judge. Nothing on screen was written by hand.

**Numbers to quote** (`knowledge/index.json`, `knowledge/goals.json`, `activities/`, `activities/checks.json`):
63 lectures, 386 segments, 2,006 facts, 3,122 concepts after the synonym merge (1,316 with a model-written
definition: the glossary; the other 1,806 are connecting concepts on the maps), 7,427 relationships, 8 course goals,
63 lecture goals, 125 objectives. 1,168 activities of ten kinds: 347 quizzes, 347 recaps, 63 concept maps, 63
complete-the-map, 63 match-the-pairs, 63 open questions, 62 crosswords, 62 recalls, 57 odd-one-out, 41 put-in-order.
A judge checked 3,911 items and failed 1,086; learners see 1,136 activities (32 whole activities and 35 of 1,163 quiz
questions are hidden). 1,316 review cards. Answers take about 5 s (first words after 2-4 s), each claim cited to a
lecture and a time.

Every item and question below was checked on the rebuilt layer today (local viewer, `/api/view/<lecture>`, and the
real QA with Gemma 4 12B on this PC's RTX 5070).

**Activity IDs.** Learners do not see IDs: an activity is found by its place on the Activities tab ("Before you
watch", "Part N: <segment>", "After the lecture") and its kind. IDs such as 30/A9 show only in developer mode
(`?dev=1`) and are given here so the item can be found again. Hidden items are left out and the rest renumbered; none
of the items chosen below has a hidden question, so their numbers are as listed.

## Setup (before the audience)

- **On this PC:** `cd pipeline && python viewer/serve.py nptel_vr --warm` (`--warm` loads the layer, the query
  embedder and the model at start). **On a cloud instance:** see "Demo day on a cloud instance" below.
- Open http://localhost:8765, full screen, light theme. **Developer mode off** (it shows the hidden items).
- **Warm-up, off stage:** ask "How does a Kalman filter fuse IMU and camera data for tracking?". It is the first
  question to use the fact search, which loads the embedder if it is not loaded yet: 20-23 s cold (measured twice),
  then 3-9 s for every answer. Do not show its answer (see "Avoid on stage").
- Open tabs in advance: lecture 4, lecture 30, lecture 36, lecture 9, lecture 62 (concept map), the course map.

## The walk (about 12 minutes)

| # | Where | Do | Say |
|---|---|---|---|
| 1 | **Course home**, then **Concept map** in the top bar | Scroll the 8 course goals; on the course map (lectures grouped by week and topic, arrows = prerequisites) click lecture 30: lecture 29 (direct) and the earlier lectures it builds on light up and its card opens; click a goal chip | "Eight course goals, and which lectures build on which, worked out from the transcripts." |
| 2 | **Lecture 4 "Definitions"** | Click a segment in the list (4 segments); let it play; the current segment and the transcript follow | "Each lecture is cut into the steps it teaches, each with its goal. You navigate by meaning." |
| 3 | Lecture 4 -> **Concepts** -> "virtual reality system" | Read the definition; click "where it is defined": the video jumps to 6:01 (it is also explained at 13:24 and in lecture 13); show its facts and relationships | "Every concept is traced to the sentence where it is taught, and the definition is written from those sentences." |
| 4 | Lecture 4 -> **Concept map** (18 concepts) | Click "computer-aided design system" or "three-dimensional movie experience": its neighbours light up ("does not support immersive experience", "does not support interaction"); double-click to zoom. Then **quiz 4/A5** (Part 3): "Why is a mouse-driven CAD system not a virtual reality system?" | "How the ideas connect: CAD, video conferencing and 3D movies against the three VR characteristics, and the quiz asks exactly that." |
| 4b | **Lecture 62 -> Concept map** (165 concepts) | The key view (about 20 concepts) reads at once; toggle "All 165 concepts, by part": grouped by the part of the lecture that teaches them, a part's title plays the video there | "Even the densest lecture stays readable; every concept sits where it is taught." |
| 5 | **Lecture 23 -> Concept map** (23/A11) | Point at "disappearing technology" -> "is the same thing as" -> "presence" | "Across the course: the lecturer's idea that the best technology disappears is the same as presence." |
| 6 | **Lecture 30 "Auditory Sense & Immersive Experience"** -> Activities | **Crossword 30/A14** (After the lecture): fill 3 across AZIMUTH and 2 across ELEVATION live. **Quiz 30/A9** (Part 5, 4 questions: ILD, acoustic shadow, average HRTF, binaural rendering): answer Q1 wrong on purpose (pick "Interaural time difference"), the explanation says why and links to the moment in the video. Optional: **odd one out 30/A15** (Social / Primitive / Monaural / Warning) | "Every question has a right answer stated in the lecture; the wrong options are real neighbouring concepts." |
| 7 | **Lecture 36 "Usability requirement gathering and specification"** -> Activities | **Put in order 36/A5** (Part 2: the five contextual-inquiry stages, plan to reflect), **complete the map 36/A11**, **odd one out 36/A14** ("Obtain permissions" among the affinity-diagram steps) | "Different games from the same knowledge, consistent with each other." |
| 8 | **Lecture 9 "Issues & Challenges"** (optional) | **Quiz 9/A6** (Part 3, the three fidelities, 4 questions), **put in order 9/A5** (Part 2: how familiarity changes along the uncanny valley curve), **match the terms 9/A14** (presence, uncanny valley effect, the three fidelities, pose) | "The uncanny valley lecture as a quiz, an ordering game and a matching game; the matching uses the written definitions." |
| 9 | **Lecture 5** -> "Before you watch" | **Recall 5/A0**: AR, MR and the reality-virtuality continuum from lecture 1, VR and virtual environment from lecture 4; flip a card | "The course graph knows what each lecture builds on, and asks you to recall it first." |
| 9b | **Glossary** in the top bar | Type "HRTF" (finds head-related transfer function by its acronym), then "uncanny" | "1,316 concepts with a definition, each linked to where it is taught." |
| 10 | **The question box** | The questions below; click one citation after each | "It answers only from the course, and you can check every claim." |

Clean alternatives if one of the above misbehaves: crossword **4/A10** or **9/A15** or **23/A14** (no judge
failure), odd one out **9/A16** (User presence among the AR issues), quiz **4/A3** (Part 2, the VR characteristics).

## The questions, in order (verified; times with the GPU free)

Times: the viewer's streamed route on this PC (first words / whole answer), with the CLI run in brackets; lectures
cited. All answers read: grounded, every claim cited, no wrong citation seen.

| # | Question | Time | Citations | What it shows |
|---|---|---|---|---|
| 1 | **"What is the difference between immersion and presence?"** | 4.7 / 8.4 s (6.8, 8.2) | 5-8, lectures 8, 9 | Immersion technological and objective, presence psychological and subjective; immersion aids presence but does not ensure it. A strong opener. |
| 2 | **"What are the causes of cybersickness?"** | 4.3 / 9.0 s (8.4) | 5-10, lectures 10, 11, 25, 26, 41, 49 | A full taxonomy: internal factors, then hardware and content factors, then height, speed and angular velocity, sensory mismatch. |
| 3 | **"What is the field of view and why does it matter for cybersickness?"** | 3.8 / 8.0 s (7.8) | 8, lectures 11, 12, 28 | The nuance impresses: a narrower field of view helps, too narrow hurts, and it costs presence. |
| 4 | **"Why are GPUs used for rendering in VR?"** | 3.4 / 5.1 s (6.8) | 3-6, lectures 14, 58 | Joins hardware and rendering lectures: parallel vertex transforms, lighting, projection. |
| 5 | **"What is an IMU?"** | 2.0 / 5.5 s (5.5) | 6, lectures 17, 18 | The acronym is resolved; gyroscope, accelerometer, magnetometer; drift correction. |
| 6 | **"what is HRTF"** | 1.8 / 3.9 s (3.8) | 4, lecture 30 | Lower case, no question mark: still found. Average-listener HRTF, binaural synthesis. |
| 7 | **"what is cybersicknes"** | 3.5 / 9.1 s (8.4) | 8-11, lectures 10, 25, 26, 49 | Misspelt on purpose: still matched. Symptoms, causes, the presence trade-off. |
| 8 | **"How does the Wizard of Oz approach work?"** | 2.1 / 4.1 s (6.1; once 21 s, a cold first run) | 3, lecture 42 | The hidden "wizard" and the 1984 IBM speech-recognition test. |
| 9 | **"What is lecture 36 for?"** | 2.0 / 4.7 s (4.2) | 4, lecture 36 | The goals tree: the lecture's aim and objectives. |
| 10 | **"What do I need to know before lecture 9?"** | 1.9 / 5.2 s (5.7) | 4-6, lectures 2, 4, 7 | Virtual reality system, reality, immersion, 3D registration, each with its definition and time; revise lectures 4, 2, 7. **Ends with a raw "[lecture_dependencies]"** (every run): say "the tool it used" and move on, or skip this one. |
| 11 | **"What is vergence-accommodation conflict?"** | 1.6 / 2.8 s (3.3, 3.4) | 2-4, lectures 14, 26, 28 | A real VR topic this course does not teach: it says so, then offers what the course does say (vection, binocular vision). |
| 12 | **"Who won the 2022 FIFA World Cup?"** | 2.9 / 3.2 s (3.9, 4.7) | none | "The course does not cover the 2022 FIFA World Cup", and what the course is about. End here: it does not make things up. |

Optional: **"What are the three fidelities in VR design?"** (3.1 / 6.0 s, lecture 9): representational, interaction
and experiential fidelity, each with its range; pairs well with quiz 9/A6. **"What is the uncanny valley?"** (5.3 s,
lecture 9). **"What is the difference between AR and VR?"** (9.5 s, lectures 3, 5, 15: good but the slowest).

Click the "Lecture N · m:ss" links inside an answer: they open the lecture at that moment.

## Avoid on stage

- **Developer mode**: it shows the hidden items and the judge marks.
- **Recaps** in general: 222 of 347 recap summaries have a text the judge failed (not supported by or not faithful to
  the facts) and learners still see them (the hiding rule hides recaps only for source talk). Among them 4/A2, 9/A7,
  30/A2, 30/A4, 30/A8, 36/A2, 36/A4. Clean ones if asked: 23/A2, 62/A13, 62/A20.
- **Crosswords with judge-failed clues** (shown to learners): 51/A21 (6 of 12 clues), 40/A18 (5), 57/A16 (5 of 8),
  29/A11 (4), 5/A12 (3 of 5), 6/A16, 13/A19, 27/A19, 38/A20, 43/A13, 45/A20, 60/A12, 61/A17, 62/A24 (3 each). 30/A14
  and 36/A13 have one flagged clue each (6 across PSYCHOPHYSICS, 5 down REQUIREMENT: "not unique"); fine to show,
  but fill AZIMUTH and ELEVATION.
- **Duplicate concepts left after the merge**: head-mounted display / virtual reality headset (both defined, both in
  the glossary, together on the maps of lectures 2, 6, 10, 11, 15, 16, 28); interaction / user interaction (both on
  lecture 4's map: point at the three characteristics, do not open "interaction"); iPhone operating system / ios;
  field of view / horizontal field of view (both have the alias FOV; lecture 28's map). Do not search "VR",
  "headset" or "FOV" in the glossary ("VR" also matches "virtual reality headset", whose aliases include "VR").
- **Odd "also known as" lists**: presence ("present", "presence results", "presence ratings"), virtual reality system
  ("system"). Do not dwell on the alias line of those cards.
- **Connecting-concept cards with odd role sentences**: "control" ("a part of a video player in a virtual tablet
  interface"), "live-action 180-degree video" ("a kind of video"), "gigabyte", "real-world view" (a wrong gloss),
  "ios". Open defined concepts (the glossary ones) on stage.
- **Selecting a hub concept** in a full ("All N concepts") view (e.g. "game engine" in lecture 20): a crowded fan of
  labels. Select hubs in the key view.
- **Questions**: "before lecture 30" (now thin: only lecture 29's frequency, plus XR and VR); every "before lecture
  N" answer may end with the raw "[lecture_dependencies]"; formula questions (raw LaTeX: the Kalman answer printed
  `$\theta_{dk} = \alpha \theta_{gk} + ...$` in 2 of 3 runs); several concepts compared at once (9-19 s). The first
  question that uses the fact search after a start without `--warm` takes 20-23 s.

## Demo day on a cloud instance (through SSH)

**Setup** (`pipeline/demo/README.md`; proven today on an RTX PRO 6000: `setup_demo.sh`, then `check_demo.sh` ALL
PASS, `analysis/mvp/demo_ec2_2026-11-17/check_demo.txt`): start the instance; rsync the code and `output/nptel_vr`
(about 170 MB; videos optional, 5.5 GB); `bash pipeline/demo/setup_demo.sh` in tmux (about 20 min the first time,
2 min on a rerun; it builds llama.cpp, starts Gemma 4 12B and the viewer with `--warm`, and asks two warm-up
questions); `ssh -N -L 8765:127.0.0.1:8765 demo`; open http://localhost:8765; `check_demo.sh` must say ALL PASS.
Then ask the off-stage warm-up question above once more through the page.

**Choose the region by the venue, and test the tunnel first.** Today, through SSH from the user's network to a
us-east-1 instance, raw throughput was about 40 kB/s each way while the PC's internet did 5.7 MB/s, so pages took
2-20 s. Pick an instance in the region nearest the venue (ap-south-1 Mumbai for India), and before anything else time
the tunnel:

```
time (ssh demo "head -c 2000000 /dev/urandom" | wc -c)     # 2 MB: should finish in under about 2 s
```

If it is slow, try another region or network before the demo, not during it. Videos play from YouTube (the browser
fetches them directly, no tunnel load) unless the files were copied; with copied files, `--prefer-youtube` (or the
page's `?yt=1`) still plays from YouTube.

**Question answering on the instance.**
- **llama.cpp** (the `setup_demo.sh` default, `configs/gemma4_12b_demo.json`): works; `check_demo.sh` answered
  "What is an HMD?" in 2.9 s with 4 citations.
- **vLLM Gemma 4 12B** (`configs/gemma4_12b_vllm_demo.json`; start steps in `analysis/qa/STATE.md`, "How demo setup
  would start vLLM Gemma on the instance"): benchmarked median 4.5 s, max 6.6 s, 0 answers over 8 s, all grounded
  (`analysis/qa/bench_vllm_shipped.jsonl`, 17 answers).
- Either way answers stream: the first words show after about 3 s.
- Stop at the end on the instance: `python -m qa --stop` (with `--config` for the vLLM config), then stop the
  instance (README step 8).

## Talking points if asked

- **Grounding**: every fact cites transcript sentences; every answer cites facts; citations become lecture and time.
  Identifiers a tool did not return are dropped before the answer is shown. Out-of-course questions are recognised
  by a calibrated score and answered "not covered".
- **Knowledge layer**: the synonym merge joined the concepts each segment named into 3,122 course concepts; definitions
  were written by the model from each concept's defining facts (1,316 concepts); course goals, lecture goals and
  objectives form a goals tree; the lecture graph links lectures by the concepts they reuse.
- **Activities**: generated from the facts and concepts, checked in code (answers in the facts, options real concepts,
  crossword fit), then by a judge per item; what the judge fails is hidden from learners for quizzes, open questions,
  odd one out and put in order.
- **Models**: Qwen 3.8 27B on one cloud GPU built the knowledge; Gemma 4 12B answers questions on a desktop GPU (the
  demo runs on one modest GPU, or on vLLM in the cloud).
- **Next**: recaps rewritten or hidden by the judge, the remaining duplicates (HMD / VR headset), the scored question
  set, other courses (the preprocessing already runs on five MIT and NPTEL courses).
