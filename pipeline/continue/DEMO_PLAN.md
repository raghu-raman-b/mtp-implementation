# Demo plan: the VR course as a learning companion (final, 2026-11-13)

**The story in one line.** From nothing but 63 lecture videos and their transcripts, the pipeline builds a learning
companion: every lecture cut into the steps it teaches, every concept traced to the moment it is taught, a question box
that answers only from the course and cites lecture and time, and a full set of activities and games. Nothing on screen
was written by hand.

**Numbers to quote** (`knowledge/index.json`, `activities/`): 63 lectures, 347 segments, 2,006 facts, 3,384 concepts,
7,479 relationships, 7 course goals, 127 objectives; 1,208 activities, all ten kinds in every lecture (347 quizzes,
347 recaps, 63 open questions, 63 crosswords...), 1,107 review cards. Answers in about 6 seconds, each claim cited to a
lecture and a time.

Every item below was checked on the real layer (`analysis/mvp/showcase.md`, `analysis/mvp/test_report.md`).

## Setup (before the audience)

- **On a cloud instance:** follow `pipeline/demo/README.md` (copy code, outputs and videos; `setup_demo.sh`; forward
  port 8765; `check_demo.sh` must say ALL PASS). **On this PC:** `cd pipeline && python viewer/serve.py nptel_vr`.
- Open http://localhost:8765, full screen, light theme. Developer mode off.
- **Warm-up:** ask one throw-away question ("What is extended reality?"): the first answer loads the model and the
  embedder (12-16 s). After that answers take 3-8 s.
- Open tabs in advance: lecture 4, lecture 23 (concept map), lecture 30, lecture 36.

## The walk (about 12 minutes)

| # | Where | Do | Say |
|---|---|---|---|
| 1 | **Course home**, then **Concept map** in the top bar | Scroll the course goals; on the course map (lectures grouped by week and topic, arrows = prerequisites) click lecture 30: its prerequisites light up and its card opens; click a goal chip | "Seven course goals, and which lectures build on which, worked out from the transcripts." |
| 2 | **Lecture 4 "Definitions"** | Click a segment in the list; let it play; the current segment and the transcript follow | "Each lecture is cut into the steps it teaches, each with its goal. You navigate by meaning." |
| 3 | Lecture 4 -> **Concepts** -> "virtual reality system" | Click "where it is defined": the video jumps to 6:01; show its facts and relationships | "Every concept is traced to the sentence where it is taught." |
| 4 | Lecture 4 -> **Concept map** (19 nodes) | Click a node: its neighbours light up and its card opens; double-click to zoom | "How the ideas connect: CAD, video conferencing and 3D movies against the three VR characteristics." |
| 4b | **Lecture 62 -> Concept map** (166 concepts) | The key view (about 20 concepts) reads at once; toggle "All 166 concepts, by part": grouped by the part of the lecture that teaches them, a part's title plays the video there | "Even the densest lecture stays readable; every concept sits where it is taught." |
| 5 | **Lecture 23 -> Concept map** (23/A12) | Point at "disappearing technology" linked to "presence" | "Across the course: the lecturer's idea that the best technology disappears is the same as presence." |
| 6 | **Lecture 30 "Auditory Sense"** -> Activities | **Crossword 30/A15**: fill AZIMUTH and ELEVATION live; **quiz 30/A9** (ILD/ITD/HRTF): answer one wrong on purpose, the explanation links to the moment in the video | "Every question has a right answer stated in the lecture; the wrong options are real neighbouring concepts." |
| 7 | **Lecture 36 "Usability requirements"** -> Activities | **Put in order 36/A5** (the five contextual-inquiry stages), **complete the map 36/A12**, **odd one out 36/A15** | "Different games from the same knowledge, consistent with each other." |
| 8 | **Lecture 9** (optional) | Quiz **9/A6** (the three fidelities), recap **9/A7** | "The uncanny valley lecture, as a quiz and a recap." |
| 9 | **Before this lecture** on lecture 5 | Recall **5/A0** (AR, MR, the reality-virtuality continuum, VR, from lectures 1 and 4) | "The course graph knows what each lecture builds on." |
| 10 | **The question box** | The questions below; click one citation after each | "It answers only from the course, and you can check every claim." |

## The questions, in order (verified; times with the GPU free)

1. **"What is the difference between immersion and presence?"** (6.9 s, 9 citations, lectures 2, 8, 9). Immersion is
   technological, presence psychological; immersion aids presence but does not ensure it. A strong opener.
2. **"What are the causes of cybersickness?"** (6.1 s, lectures 10, 11, 49). A full taxonomy: internal factors, then
   hardware and content factors, then height, speed and angular velocity.
3. **"What is the field of view and why does it matter for cybersickness?"** (7.4 s, lectures 11, 12, 28). The nuance
   impresses: a narrower field of view helps, too narrow hurts.
4. **"Why are GPUs used for rendering in VR?"** (4.6 s, lectures 14 and 58). Joins hardware and rendering lectures.
5. **"What is an IMU?"** (4.2 s, lecture 17). The acronym is resolved; gyroscope, accelerometer, magnetometer.
6. **"what is HRTF"** (6.7 s, lecture 30). Lower case, no question mark: still found.
7. **"what is cybersicknes"** (7.3 s, 10 citations). Misspelt on purpose: still matched.
8. **"How does the Wizard of Oz approach work?"** (7.0 s, lecture 42). The 1984 IBM listening typewriter story.
9. **"What is lecture 36 for?"** (3.7 s). The goals tree: the lecture's aim and objectives.
10. **"What do I need to know before lecture 30?"** (5.2 s). Lecture 29 first, then XR, VR, presence, cybersickness from
    earlier lectures, each with its definition and time.
11. **"Who won the 2022 FIFA World Cup?"** (2-5 s). "The course does not cover the 2022 FIFA World Cup." End here: it
    does not make things up.
12. Optional, near the topic: **"How does a Kalman filter fuse IMU and camera data for tracking?"** (about 20 s: talk
    while it runs). It declines, then offers what the course does say about IMU and vision tracking.

Click the "(lecture N, m:ss)" links inside an answer: they open the lecture at that moment.

## Avoid on stage

- **Match pairs** (all lectures) and most **recall / review cards**: their "definitions" are each concept's first fact
  (model-written definitions are still to come), so many read oddly. Show only recall **5/A0** or **3/A0**.
- **Crosswords** 13/A19, 21/A11, 29/A11, 51/A21 (a wrong clue), 58/A20, 60/A13, 16/A13, 2/A8.
- **Selecting a hub concept** in a full ("All N concepts") view (e.g. "game engine" in lecture 20): a crowded fan of labels. Select hubs in the key view.
- **Duplicate concepts** (the synonym merge is still to come): headset / head-mounted display / virtual reality headset
  appear together on several maps (lectures 2, 6, 10, 11, 13, 15, 16, 17, 20, 28, 44); AR Toolkit / augmented reality
  toolkit; 3D model / three-dimensional model. Do not open those cards or search them in the glossary.
- Weak items: 59/A5, 11/A18, 15/A16, 51/A22, 57/A1 Q1, 28/A4 Q4-Q5, 3/A3 Q2, 5/A10.
- Questions: "before lecture 16 or 40" (odd items; lecture 30's is clean); formula questions (raw math); several
  concepts compared at once (can take about 19 s).

## Talking points if asked

- **Grounding**: every fact cites transcript sentences; every answer cites facts; citations become lecture and time.
  Identifiers a tool did not return are dropped before the answer is shown.
- **Models**: Qwen 3.8 27B on one cloud GPU built the knowledge overnight; Gemma 4 12B answers questions and wrote the
  simpler activities on a desktop GPU. The demo runs on one modest GPU.
- **Quality loop**: every model answer is checked in code and retried with the problems shown; a measured study found
  the fact judge did more harm than good, so the MVP keeps the extracted facts as they are (slide 9 of the deck).
- **Next**: the synonym merge (3b), model-written definitions (4a), judges for activities, the scored question set,
  other courses (the preprocessing already runs on five MIT and NPTEL courses).
