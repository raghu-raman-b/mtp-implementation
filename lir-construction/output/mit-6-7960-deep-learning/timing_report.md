# LIR build report: MIT 6.7960 Deep Learning

2026-10-31 04:28 · generator **unsloth/gemma-4-E4B-it-GGUF:gemma-4-E4B-it-UD-Q8_K_XL.gguf (llama.cpp, KV f16)** · judge **gpt-6-luna (OpenAI API, reasoning medium)** · 32 parallel slots · thinking on for every call · temperature 0

## Summary

- **23 lectures, 1738.5 min of video, built in 214.0 min** (about **9.3 min per lecture**, **7.4 min of processing per hour of video**).
- 4,914 LLM calls, 5,881,843 output tokens (including thinking), 8,285,000 input tokens.
- Videos: 23/23 downloaded.
- API spend: **$0.742** this run (959 calls); $2.080 of the $2.28 budget used so far (ledger: `api_spend.json`).
- Open-answer scorer: m = 3, tau = 0.75 (calibrated, 67% agreement on 42 generated answers).

## Per lecture

Processing time is attributed: each stage's wall time is split across lectures by how long their calls held a server slot.

| Lecture | Title | Video (min) | Segments | LLM calls | Output tokens | Processing (min) | min per video hour |
|---|---|--:|--:|--:|--:|--:|--:|
| L01 | Introduction to Deep Learning | 60.7 | 10 | 107 | 135,599 | 5.1 | 5.05 |
| L02 | How to Train a Neural Net | 79.4 | 17 | 215 | 270,982 | 9.87 | 7.46 |
| L03 | Approximation Theory | 82.6 | 21 | 285 | 329,411 | 11.93 | 8.66 |
| L04 | Architectures: Grids | 83.8 | 19 | 205 | 248,185 | 9.07 | 6.49 |
| L05 | Architectures: Graphs | 81.1 | 11 | 141 | 169,358 | 6.31 | 4.67 |
| L06 | Generalization Theory | 80.3 | 13 | 190 | 228,625 | 8.34 | 6.23 |
| L07 | Scaling Rules for Optimization | 80.8 | 15 | 226 | 267,720 | 9.6 | 7.12 |
| L08 | Architectures: Transformers | 74.4 | 19 | 252 | 305,657 | 10.98 | 8.85 |
| L09 | Hacker's Guide to Deep Learning | 75.6 | 22 | 290 | 354,809 | 12.74 | 10.11 |
| L10 | Architectures: Memory | 73.3 | 14 | 161 | 198,988 | 7.3 | 5.98 |
| L11 | Representation Learning: Reconstruction-Based | 80.9 | 12 | 151 | 197,981 | 7.32 | 5.43 |
| L12 | Representation Learning: Similarity-Based | 76.1 | 24 | 337 | 386,489 | 13.77 | 10.86 |
| L13 | Representation Learning: Theory | 75.2 | 19 | 208 | 251,427 | 8.93 | 7.12 |
| L14 | Generative Models: Basics | 81.1 | 18 | 230 | 266,000 | 9.78 | 7.23 |
| L15 | Generative Models: Representation Learning Meets Generative Modeling | 80.6 | 17 | 229 | 287,499 | 10.47 | 7.8 |
| L16 | Generative Models: Conditional Models | 81.3 | 12 | 156 | 197,481 | 7.51 | 5.54 |
| L17 | Generalization: Out-of-Distribution (OOD) | 64.4 | 13 | 164 | 188,706 | 6.95 | 6.48 |
| L18 | Transfer Learning: Models | 85.3 | 14 | 201 | 234,596 | 8.7 | 6.12 |
| L19 | Transfer Learning: Data | 75.4 | 15 | 188 | 228,592 | 8.24 | 6.55 |
| L20 | Scaling Laws | 38.4 | 12 | 151 | 183,873 | 6.66 | 10.41 |
| L21 | Language Models | 77.1 | 24 | 309 | 354,796 | 13.02 | 10.13 |
| L23 | Metrized Deep Learning | 67.7 | 17 | 265 | 284,042 | 10.17 | 9.02 |
| L24 | Inference Methods for Deep Learning | 83.0 | 20 | 252 | 310,446 | 11.3 | 8.17 |

## Per stage

| Stage | Wall time (s) | LLM calls | Input tokens | Output tokens | Output tok/s |
|---|--:|--:|--:|--:|--:|
| transcripts | 0.2 | 0 | 0 | 0 | 0.0 |
| stage1_segment | 512.0 | 23 | 456,231 | 58,599 | 114.5 |
| stage2_annotate | 3292.8 | 910 | 1,511,339 | 1,395,611 | 423.8 |
| stage3_goals | 66.7 | 26 | 12,489 | 22,101 | 331.2 |
| stage4_course_state | 994.1 | 682 | 416,046 | 428,145 | 430.7 |
| stage5_generate | 4425.0 | 1211 | 2,072,607 | 1,828,521 | 413.2 |
| stage6_calibrate | 44.5 | 16 | 30,948 | 14,339 | 322.5 |
| stage6_judge | 3502.4 | 2046 | 3,785,340 | 2,134,527 | 609.4 |
| stage7_assemble | 5.0 | 0 | 0 | 0 | 0.0 |

## Validation: code checks (layer 2)

| Stage | Items | Passed first time | Passed after retry | Still failing (resolved by code) |
|---|--:|--:|--:|--:|
| stage1_segment | 23 | 23 | 0 | 0 |
| stage2_annotate | 756 | 648 | 58 | 50 |
| stage3_goals | 24 | 22 | 2 | 0 |
| stage4_canonicalize | 642 | 642 | 0 | 0 |
| stage4_edges | 23 | 10 | 10 | 3 |
| stage5_open_questions | 92 | 30 | 53 | 9 |
| stage5_primer | 22 | 22 | 0 | 0 |
| stage5_quiz | 378 | 245 | 103 | 30 |
| stage5_summary | 378 | 295 | 83 | 0 |
| stage6_calibrate | 16 | 16 | 0 | 0 |
| stage6_repair | 993 | 912 | 52 | 29 |

## Validation: judge (layer 3)

| Check | Judged | Passed first time | Repaired and passed | Dropped | Replaced by code | Not judged (budget) |
|---|--:|--:|--:|--:|--:|--:|
| sub-goal describes segment | 378 | 366 | 12 | 0 | 0 | 0 |
| key term worth learning, definition faithful + useful | 1502 | 939 | 235 | 328 | 0 | 0 |
| quiz item worth asking, answerable + correct | 1387 | 1201 | 145 | 41 | 0 | 0 |
| summary + review questions supported | 378 | 207 | 154 | 0 | 17 | 0 |
| open question sound | 92 | 59 | 25 | 8 | 0 | 0 |
| edge true | 305 | 212 | 0 | 93 | 0 | 0 |
| recall item sound | 88 | 61 | 0 | 27 | 0 | 0 |

## Notes

Items that failed code checks and were repaired or replaced by code:

- L01: S10: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L02: S2: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No', 'question 4: the question copies the key point it tests; ask about it instead']
- L02: OQ2: open question failed validation: ["key point 4 needs at least 2 keywords that appear word for word in the reference answer; ['water flowing'] do not"]
- L04: OQ4: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['periodic'] do not"]
- L05: S3: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L06: S3: quiz failed validation: ['question 1: for multiple choice, put the correct option first and set correct_answer to "first option"', 'question 3: for multiple choice, put the correct option first and set correct_answer to "first option"']
- L06: S9: quiz failed validation: ["question 3: write the question so it ends with '?'"]
- L06: S13: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L06: OQ4: open question failed validation: ["key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['just a mapping'] do not", "key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['IID data points'] do not"]
- L07: S10: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L08: S15: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L09: S2: quiz failed validation: ['question 1: "given in the lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L09: S15: quiz failed validation: ['question 2: for multiple choice, put the correct option first and set correct_answer to "first option"', 'question 4: for multiple choice, put the correct option first and set correct_answer to "first option"']
- L09: S18: quiz failed validation: ['question 1: "does the lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L09: S20: quiz failed validation: ['question 3: the question copies the key point it tests; ask about it instead']
- L10: S14: quiz failed validation: ['question 3: the question copies the key point it tests; ask about it instead']
- L10: OQ2: open question failed validation: ["key point 4 needs at least 2 keywords that appear word for word in the reference answer; ['function is shared', 'over time'] do not"]
- L11: S11: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L12: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['good representations', 'similarity and dissimilarity'] do not"]
- L14: S2: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L14: S11: quiz failed validation: ['question 3: correct_answer must be True or False']
- L14: OQ2: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['make things that are new', 'capture the important statistics'] do not"]
- L14: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['generates data'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['make things'] do not", "key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['explicitly or implicitly'] do not", "key point 4 needs at least 2 keywords that appear word for word in the reference answer; ['something to data', 'taking data'] do not"]
- L15: S13: quiz failed validation: ["question 1: write the question so it ends with '?'", "question 3: write the question so it ends with '?'"]
- L15: S15: quiz failed validation: ['question 2: correct_answer must be Yes or No', 'question 3: correct_answer must be True or False']
- L18: S1: quiz failed validation: ['question 2: for multiple choice, put the correct option first and set correct_answer to "first option"']
- L18: S4: quiz failed validation: ['question 2: correct_answer must be Yes or No', 'question 4: correct_answer must be True or False']
- L18: S13: quiz failed validation: ["question 1: write the question so it ends with '?'", 'question 2: correct_answer must be True or False', 'question 4: correct_answer must be True or False']
- L18: OQ2: open question failed validation: ["key point 5 needs at least 2 keywords that appear word for word in the reference answer; ['continue to train'] do not"]
- L19: S3: quiz failed validation: ['question 3: correct_answer must be True or False']
- L19: S13: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L20: S4: quiz failed validation: ['question 2: for multiple choice, put the correct option first and set correct_answer to "first option"', 'question 3: for multiple choice, put the correct option first and set correct_answer to "first option"']
- L20: S9: quiz failed validation: ['question 4: correct_answer must be Yes or No']
- L20: OQ2: open question failed validation: ["key point 4 needs at least 2 keywords that appear word for word in the reference answer; ['valid for models'] do not"]
- L21: S8: quiz failed validation: ['question 2: correct_answer must be True or False']
- L21: S14: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L23: S3: quiz failed validation: ['question 3: "discussed in the lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L23: S12: quiz failed validation: ["question 1: write the question so it ends with '?'", "question 3: write the question so it ends with '?'"]
- L24: S4: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be True or False']

Raw numbers: `timing.json`. Per-call tokens, retries and validator results: the `origin` list in each lecture file; judge results: its `quality` field.
