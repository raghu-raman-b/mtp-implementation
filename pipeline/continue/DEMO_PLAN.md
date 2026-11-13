# Demo plan: the VR course as a learning companion (MVP, 2026-11-13)

**The one-line story.** From nothing but 63 lecture videos and their transcripts, the pipeline builds a learning
companion: every lecture cut into the steps it teaches, every concept traced to the moment it is taught, a question box
that answers only from the course and cites lecture and time, and a full set of activities and games. Nothing in the
demo was written by hand.

**Numbers to quote** (`knowledge/index.json`): 63 lectures, 347 segments, 2,006 facts, 3,384 concepts, 7,479
relationships, 7 course goals, 127 objectives; activities in all 63 lectures (all ten kinds in lectures 1-8 and 16),
1,107 spaced-review cards.

## Before you start (5 min)

1. Let the activity run finish or stop it, so the GPU is free for answers: `tmux attach -t mvp` (check the log says
   COMPLETE), or `tmux kill-session -t mvp`. With the GPU shared, an answer took 23-94 s this morning; alone it is much
   faster.
2. `cd pipeline && python viewer/serve.py nptel_vr`, open http://localhost:8765 (full screen, light theme reads best on a
   projector).
3. Warm the answer model: ask "What is extended reality?" once (the first question loads Gemma 4 12B and the
   embedder).
4. Keep developer mode off (no IDs or statistics on screen). Keep a second tab open on lecture 4 as a fallback.

## The walk (about 10 minutes)

| # | Show | Say | Why it lands |
|---|---|---|---|
| 1 | **Course home**: course goals and the lectures by week | "Seven course goals and the lectures that serve each were generated from the transcripts." | The whole course, structured, at a glance |
| 2 | **Lecture 4 "Definitions"**: the video with its segments beside it; click a segment; let it play and watch the current segment and the transcript follow | "The lecture is cut into the steps it teaches, each with its goal." | Navigation by meaning, not by scrubbing |
| 3 | **Concepts tab -> "virtual reality system"**: definition, "where it is defined" (click: the video jumps to 6:01), facts with times, relationships both ways | "Every concept is traced to the sentence where it is taught." | Grounding you can click |
| 4 | **Concept map tab**: click a node to open its card | "How the ideas of this lecture connect." | Visual, interactive |
| 5 | **Before this lecture**: recall card "What is immersive experience?" (from lecture 1) | "The course graph knows what this lecture builds on." | Personalised readiness |
| 6 | **Activities**: quiz on segment 0 (answer one wrong: the explanation links to the moment in the video), then the **crossword** (fill VIRTUAL, REALITY), **odd one out** (CAD / video conferencing / VR vs 3D movie), **open question** "Why can a CAD system support a virtual environment and interaction, yet not be a VR system?" (reveal the reference answer and key facts), **complete the map**, **match pairs** | "All generated from the same knowledge, each answerable from facts the lecture states." | Breadth; games are fun to click live |
| 7 | **Spaced review** on the home page: flip three cards | "1,107 cards, scheduled per learner." | Retention, not just content |
| 8 | **The question box** (below) | | The showstopper |
| 9 | **Close**: lecture 16 "Understanding Tracking I" home -> "Before this lecture" | "Ask what you need before any lecture; the answer is the course itself." | Ends on the graph |

## The questions (all verified on the real layer this morning)

Ask them in this order; click one citation after each to show the video jumping to the moment.

1. **"What is extended reality?"** - a definition with lecture 1 (11:38) and lecture 25 cited. Opens the topic.
2. **"How is augmented reality different from virtual reality?"** - a comparison built from lecture 1 and lecture 5,
   three bullets (environment, physical presence, immersion). Shows synthesis across lectures.
3. **"What is an HMD?"** - the acronym is resolved to head-mounted display, cites lectures 6 and 14. Shows it
   understands the course's vocabulary.
4. **"What are the three characteristics of a virtual reality system?"** (on lecture 4's page) - exact list, cites lecture 4 at
   6:01, 10:15, 11:20 and 13:24. Perfect lecture-level recall.
5. **"what is stereoscopy"** (lower case, no question mark) - lecture 28 (14:25). Robust to casual typing. (A
   misspelling such as "steroscopy" is matched to the closest name too.)
6. **"What do I need to know before lecture 16?"** - prerequisites with concepts from lectures 1 and 5, ten citations.
   Shows the course graph.
7. **"Why does tracking matter in a VR system?"** (on lecture 16's page) - cites lecture 16 (2:05, 2:33) and 19.
8. **"What is the recipe for butter chicken?"** - "The course does not cover the recipe for butter chicken." End on
   this: it does not make things up.

Avoid in the live demo: very long multi-part questions (slow), and questions about lectures 9-63's quizzes (their
model-made activities may still be arriving; their maps, match pairs and recall cards are there).

## Talking points if asked

- **Grounding**: every fact cites transcript sentences; every answer cites facts; citations become lecture and time.
- **Models**: Qwen 3.8 27B on one cloud GPU builds the knowledge; Gemma 4 12B on this PC answers questions and writes
  the simpler activities. It runs on a desktop.
- **Quality loop**: every model answer is checked in code and retried with the problems shown; a measured judge study
  (block 1) found the fact judge does more harm than good, so the MVP keeps the extracted facts as they are.
- **What is next**: concept merging across synonyms (stage 3b), model-written definitions (4a), activity judges, the
  question set with scores, other courses (the preprocessing already runs on five MIT and NPTEL courses).
