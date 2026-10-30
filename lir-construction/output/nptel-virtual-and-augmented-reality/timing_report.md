# LIR build report: Foundation for Virtual and Augmented Reality Systems

2026-10-30 13:46 · generator **unsloth/gemma-4-E4B-it-GGUF:gemma-4-E4B-it-UD-Q8_K_XL.gguf (llama.cpp, KV f16)** · judge **{'subgoal': {'judged': 13, 'passed_first': 13}, 'term': {'judged': 44, 'passed_first': 43, 'repaired': 1}, 'quiz': {'judged': 52, 'passed_first': 44, 'repaired': 7, 'dropped': 1}, 'summary': {'judged': 13, 'passed_first': 11, 'repaired': 2}, 'oq': {'judged': 12, 'passed_first': 7, 'repaired': 3, 'dropped': 2}, 'edge': {'judged': 48, 'passed_first': 24, 'dropped': 24}, 'recall': {'judged': 2, 'dropped': 1, 'passed_first': 1}}** · 32 parallel slots · thinking on for every call · temperature 0

## Summary

- **3 lectures, 82.5 min of video, built in 10.4 min** (about **3.5 min per lecture**, **7.6 min of processing per hour of video**).
- 189 LLM calls, 198,552 output tokens (including thinking), 265,131 input tokens.
- Videos: 3/3 downloaded.
- API spend: **$0.019** this run (39 calls); $0.019 of the $2.40 budget used so far (ledger: `api_spend.json`).
- Open-answer scorer: m = 4, tau = 0.7 (calibrated, 60% agreement on 30 generated answers).

## Per lecture

Processing time is attributed: each stage's wall time is split across lectures by how long their calls held a server slot.

| Lecture | Title | Video (min) | Segments | LLM calls | Output tokens | Processing (min) | min per video hour |
|---|---|--:|--:|--:|--:|--:|--:|
| L01 | General Intro to XR | 33.4 | 7 | 92 | 98,058 | 5.1 | 9.17 |
| L02 | Application Domains and System Categories | 28.0 | 3 | 56 | 55,414 | 3.0 | 6.43 |
| L03 | Application Domains and System Categories | 21.2 | 3 | 40 | 44,145 | 2.3 | 6.5 |

## Per stage

| Stage | Wall time (s) | LLM calls | Input tokens | Output tokens | Output tok/s |
|---|--:|--:|--:|--:|--:|
| transcripts | 0.0 | 0 | 0 | 0 | 0.0 |
| stage1_segment | 21.5 | 3 | 14,795 | 3,195 | 148.6 |
| stage2_annotate | 126.1 | 32 | 47,071 | 44,020 | 349.1 |
| stage3_goals | 40.6 | 5 | 1,324 | 5,337 | 131.5 |
| stage4_course_state | 58.2 | 18 | 7,717 | 12,960 | 222.6 |
| stage5_generate | 170.9 | 51 | 71,556 | 63,619 | 372.2 |
| stage6_calibrate | 34.7 | 12 | 20,217 | 11,793 | 340.3 |
| stage6_judge | 168.6 | 68 | 102,451 | 57,628 | 341.7 |
| stage7_assemble | 3.1 | 0 | 0 | 0 | 0.0 |
| docs | 0.1 | 0 | 0 | 0 | 0.0 |

## Validation: code checks (layer 2)

| Stage | Items | Passed first time | Passed after retry | Still failing (resolved by code) |
|---|--:|--:|--:|--:|
| stage1_segment | 3 | 3 | 0 | 0 |
| stage2_annotate | 26 | 23 | 1 | 2 |
| stage3_goals | 4 | 3 | 1 | 0 |
| stage4_canonicalize | 15 | 15 | 0 | 0 |
| stage4_edges | 3 | 3 | 0 | 0 |
| stage5_open_questions | 12 | 5 | 7 | 0 |
| stage5_primer | 2 | 2 | 0 | 0 |
| stage5_quiz | 13 | 12 | 1 | 0 |
| stage5_summary | 13 | 13 | 0 | 0 |
| stage6_calibrate | 12 | 12 | 0 | 0 |
| stage6_repair | 23 | 19 | 4 | 0 |

## Validation: judge (layer 3)

| Check | Judged | Passed first time | Repaired and passed | Dropped | Replaced by code | Not judged (budget) |
|---|--:|--:|--:|--:|--:|--:|
| sub-goal describes segment | 13 | 13 | 0 | 0 | 0 | 0 |
| definition faithful | 44 | 43 | 1 | 0 | 0 | 0 |
| quiz item answerable + correct | 52 | 44 | 7 | 1 | 0 | 0 |
| summary supported | 13 | 11 | 2 | 0 | 0 | 0 |
| open question sound | 12 | 7 | 3 | 2 | 0 | 0 |
| edge true | 48 | 24 | 0 | 24 | 0 | 0 |
| recall item sound | 2 | 1 | 0 | 1 | 0 | 0 |

Raw numbers: `timing.json`. Per-call tokens, retries and validator results: the `origin` list in each lecture file; judge results: its `quality` field.
