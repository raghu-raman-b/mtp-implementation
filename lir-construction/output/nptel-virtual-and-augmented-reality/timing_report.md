# LIR build report: Foundation for Virtual and Augmented Reality Systems

2026-10-31 00:32 · generator **unsloth/gemma-4-E4B-it-GGUF:gemma-4-E4B-it-UD-Q8_K_XL.gguf (llama.cpp, KV f16)** · judge **gpt-6-luna (OpenAI API, reasoning medium)** · 32 parallel slots · thinking on for every call · temperature 0

## Summary

- **63 lectures, 1860.5 min of video, built in 12.1 min** (about **0.2 min per lecture**, **0.4 min of processing per hour of video**).
- 473 LLM calls, 345,291 output tokens (including thinking), 518,003 input tokens.
- API spend: **$0.075** this run (227 calls); $1.338 of the $2.40 budget used so far (ledger: `api_spend.json`).
- Open-answer scorer: m = 2, tau = 0.7 (calibrated, 64% agreement on 39 generated answers).

## Per lecture

Processing time is attributed: each stage's wall time is split across lectures by how long their calls held a server slot.

| Lecture | Title | Video (min) | Segments | LLM calls | Output tokens | Processing (min) | min per video hour |
|---|---|--:|--:|--:|--:|--:|--:|
| L01 | General Intro to XR | 33.4 | 7 | 0 | 0 | 0.01 | 0.02 |
| L02 | Application Domains and System Categories | 28.0 | 3 | 0 | 0 | 0.01 | 0.02 |
| L03 | Application Domains and System Categories | 21.2 | 3 | 2 | 1,087 | 0.05 | 0.13 |
| L04 | Definitions | 24.4 | 2 | 0 | 0 | 0.01 | 0.02 |
| L05 | Definitions | 21.8 | 4 | 1 | 372 | 0.02 | 0.05 |
| L06 | Historical Evolution | 27.9 | 5 | 10 | 7,946 | 0.27 | 0.59 |
| L07 | Historial Evolution | 25.6 | 5 | 9 | 6,212 | 0.2 | 0.47 |
| L08 | Issues & Challenges | 32.2 | 5 | 6 | 5,485 | 0.21 | 0.4 |
| L09 | Issues & Challenges | 26.4 | 3 | 2 | 914 | 0.04 | 0.1 |
| L10 | Cybersickness | 26.4 | 3 | 8 | 6,243 | 0.23 | 0.52 |
| L11 | Cybersickness | 32.8 | 3 | 2 | 1,282 | 0.06 | 0.1 |
| L12 | Cybersickness | 36.6 | 9 | 8 | 4,737 | 0.15 | 0.25 |
| L13 | VR Hardware | 34.1 | 5 | 2 | 1,699 | 0.08 | 0.13 |
| L14 | VR Hardware | 26.2 | 5 | 6 | 5,826 | 0.21 | 0.47 |
| L15 | AR Hardware | 34.9 | 8 | 8 | 6,086 | 0.21 | 0.37 |
| L16 | Understanding Tracking I | 27.8 | 5 | 2 | 1,925 | 0.08 | 0.17 |
| L17 | Understanding Tracking - I | 25.3 | 6 | 4 | 1,746 | 0.06 | 0.15 |
| L18 | Understanding Tracking II | 33.1 | 8 | 11 | 10,574 | 0.36 | 0.64 |
| L19 | VR Software | 26.2 | 7 | 10 | 5,623 | 0.2 | 0.46 |
| L20 | VR Software | 36.3 | 7 | 11 | 9,075 | 0.32 | 0.53 |
| L21 | AR Software | 26.8 | 3 | 0 | 0 | 0.01 | 0.02 |
| L22 | AR Software | 19.8 | 5 | 9 | 7,258 | 0.26 | 0.78 |
| L23 | XR as Interactive Systems | 21.7 | 6 | 6 | 4,754 | 0.16 | 0.44 |
| L24 | XR as Interactive Systems | 26.5 | 6 | 7 | 4,825 | 0.15 | 0.35 |
| L25 | Human Factors in XR | 26.3 | 5 | 3 | 1,258 | 0.05 | 0.11 |
| L26 | Human Factors in XR | 25.0 | 6 | 6 | 4,098 | 0.14 | 0.35 |
| L27 | Visual Perception & Displays I | 31.0 | 10 | 7 | 4,924 | 0.18 | 0.35 |
| L28 | Visual Perception & Displays II | 28.8 | 9 | 13 | 9,134 | 0.31 | 0.64 |
| L29 | Auditory Sense & Immersive Experience | 20.2 | 5 | 6 | 4,904 | 0.17 | 0.5 |
| L30 | Auditory Sense & Immersive Experience | 29.1 | 7 | 8 | 5,659 | 0.21 | 0.43 |
| L31 | Other Senses & Full Immersion | 34.3 | 5 | 5 | 2,987 | 0.1 | 0.18 |
| L32 | Interactive System Development Life Cycle Stages | 37.7 | 8 | 12 | 9,538 | 0.33 | 0.53 |
| L33 | Introduction to Majuli case study | 23.6 | 5 | 6 | 4,103 | 0.14 | 0.35 |
| L34 | Introduction to Majuli case study | 22.4 | 3 | 6 | 4,966 | 0.18 | 0.48 |
| L35 | Usability requirement gathering and specification | 23.0 | 6 | 16 | 10,920 | 0.39 | 1.01 |
| L36 | Usability requirement gathering and specification | 32.4 | 9 | 15 | 11,516 | 0.4 | 0.74 |
| L37 | Usability requirement gathering and specification | 29.1 | 8 | 22 | 17,735 | 0.61 | 1.25 |
| L38 | System Design | 30.5 | 9 | 11 | 9,883 | 0.34 | 0.66 |
| L39 | System Design | 46.8 | 6 | 8 | 5,431 | 0.22 | 0.28 |
| L40 | System Design | 31.9 | 6 | 4 | 4,683 | 0.17 | 0.32 |
| L41 | System Design | 29.1 | 9 | 11 | 5,753 | 0.2 | 0.4 |
| L42 | System Implementation | 40.8 | 9 | 10 | 6,873 | 0.23 | 0.34 |
| L43 | System Implementation | 23.0 | 4 | 3 | 1,708 | 0.07 | 0.18 |
| L44 | System Implementation | 32.2 | 4 | 4 | 2,381 | 0.09 | 0.17 |
| L45 | System Implementation | 31.8 | 6 | 12 | 9,146 | 0.33 | 0.62 |
| L46 | System Implementation | 36.9 | 7 | 10 | 5,847 | 0.21 | 0.35 |
| L47 | System Implementation | 30.4 | 9 | 11 | 6,720 | 0.22 | 0.44 |
| L48 | System Implementation | 21.2 | 5 | 16 | 15,219 | 0.54 | 1.52 |
| L49 | VR experience optimisation | 27.1 | 8 | 19 | 11,936 | 0.38 | 0.84 |
| L50 | VR experience optimisation | 29.4 | 7 | 13 | 11,301 | 0.37 | 0.75 |
| L51 | VR experience optimisation | 45.7 | 9 | 5 | 2,015 | 0.08 | 0.11 |
| L52 | VR experience optimisation | 21.4 | 6 | 4 | 2,753 | 0.1 | 0.27 |
| L53 | VR experience optimisation | 20.2 | 5 | 4 | 2,162 | 0.07 | 0.22 |
| L54 | VR resource optimization | 35.6 | 11 | 9 | 4,733 | 0.15 | 0.25 |
| L55 | VR resource optimization | 39.8 | 5 | 4 | 3,295 | 0.14 | 0.22 |
| L56 | VR resource optimization | 43.5 | 8 | 8 | 5,092 | 0.17 | 0.24 |
| L57 | VR resource optimization | 42.1 | 8 | 12 | 8,094 | 0.28 | 0.4 |
| L58 | VR resource optimization | 37.7 | 8 | 10 | 8,857 | 0.31 | 0.49 |
| L59 | VR resource optimization | 15.9 | 5 | 9 | 4,676 | 0.16 | 0.61 |
| L60 | Linking theory to practice | 20.4 | 6 | 8 | 7,211 | 0.24 | 0.7 |
| L61 | Linking theory to practice | 29.1 | 6 | 4 | 3,759 | 0.12 | 0.25 |
| L62 | Linking theory to practice | 44.3 | 10 | 12 | 7,682 | 0.27 | 0.36 |
| L63 | Concluding remarks | 15.2 | 3 | 3 | 2,670 | 0.1 | 0.39 |

## Per stage

| Stage | Wall time (s) | LLM calls | Input tokens | Output tokens | Output tok/s |
|---|--:|--:|--:|--:|--:|
| transcripts | 3.9 | 0 | 0 | 0 | 0.0 |
| stage1_segment | 0.6 | 0 | 0 | 0 | 0.0 |
| stage2_annotate | 1.5 | 0 | 0 | 0 | 0.0 |
| stage3_goals | 0.0 | 0 | 0 | 0 | 0.0 |
| stage4_course_state | 29.5 | 0 | 0 | 0 | 0.0 |
| stage5_generate | 1.1 | 0 | 0 | 0 | 0.0 |
| stage6_calibrate | 0.0 | 0 | 0 | 0 | 0.0 |
| stage6_judge | 684.7 | 473 | 518,003 | 345,291 | 504.3 |
| stage7_assemble | 6.6 | 0 | 0 | 0 | 0.0 |
| docs | 0.0 | 0 | 0 | 0 | 0.0 |

## Validation: code checks (layer 2)

| Stage | Items | Passed first time | Passed after retry | Still failing (resolved by code) |
|---|--:|--:|--:|--:|
| stage1_segment | 63 | 63 | 0 | 0 |
| stage2_annotate | 776 | 690 | 45 | 41 |
| stage3_goals | 64 | 56 | 8 | 0 |
| stage4_canonicalize | 948 | 948 | 0 | 0 |
| stage4_edges | 63 | 34 | 22 | 7 |
| stage5_open_questions | 252 | 108 | 122 | 22 |
| stage5_primer | 62 | 62 | 0 | 0 |
| stage5_quiz | 386 | 225 | 118 | 43 |
| stage5_summary | 388 | 314 | 70 | 4 |
| stage6_calibrate | 16 | 16 | 0 | 0 |
| stage6_repair | 1020 | 925 | 70 | 25 |

## Validation: judge (layer 3)

| Check | Judged | Passed first time | Repaired and passed | Dropped | Replaced by code | Not judged (budget) |
|---|--:|--:|--:|--:|--:|--:|
| sub-goal describes segment | 388 | 378 | 10 | 0 | 0 | 0 |
| key term worth learning, definition faithful + useful | 1560 | 970 | 231 | 359 | 0 | 0 |
| quiz item worth asking, answerable + correct | 1316 | 1154 | 118 | 44 | 0 | 0 |
| summary + review questions supported | 388 | 234 | 133 | 0 | 21 | 0 |
| open question sound | 252 | 176 | 60 | 16 | 0 | 0 |
| edge true | 753 | 493 | 0 | 260 | 0 | 0 |
| recall item sound | 246 | 159 | 0 | 87 | 0 | 0 |

## Notes

Items that failed code checks and were repaired or replaced by code:

- L01: S3: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L02: S3: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be True or False']
- L04: S2: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be True or False']
- L07: S4: quiz failed validation: ['question 4: the question copies the key point it tests; ask about it instead']
- L08: S2: quiz failed validation: ['question 4: the question copies the key point it tests; ask about it instead']
- L08: S4: quiz failed validation: ["question 1: write the question so it ends with '?'", 'question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No', 'question 4: the question copies the key point it tests; ask about it instead']
- L09: OQ3: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['representational fidelity'] do not"]
- L10: S1: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be True or False']
- L12: S1: quiz failed validation: ['question 3: correct_answer must be True or False']
- L12: OQ3: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['intensity gradually decreases'] do not"]
- L13: S3: quiz failed validation: ['question 1: "discussed in this segment" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for', 'question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L13: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['track how eyes'] do not"]
- L14: OQ3: open question failed validation: ['key point 4 needs at least 2 keywords that appear word for word in the reference answer']
- L15: S1: quiz failed validation: ['question 1: multiple choice needs exactly 4 options and 4 explanations', 'question 1: for multiple choice, put the correct option first and set correct_answer to "first option"', 'question 2: multiple choice needs exactly 4 options and 4 explanations']
- L16: S3: quiz failed validation: ['question 3: the question copies the key point it tests; ask about it instead']
- L18: S1: quiz failed validation: ['question 1: the correct option is much longer than the others (88 vs about 43 characters); make them similar in length']
- L19: S2: summary failed validation: ["review question for S2.K2 must end with '?'"]
- L21: OQ2: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['create a framework'] do not"]
- L22: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['complete package'] do not"]
- L22: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['existing tools'] do not"]
- L23: S4: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L23: S6: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be Yes or No']
- L23: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['user capabilities'] do not"]
- L24: S1: quiz failed validation: ['question 2: for multiple choice, put the correct option first and set correct_answer to "first option"', 'question 3: for multiple choice, put the correct option first and set correct_answer to "first option"']
- L24: S6: quiz failed validation: ['question 1: "in this lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L26: S4: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L26: S6: quiz failed validation: ['question 2: "did the lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L27: S3: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L27: OQ3: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['extended reality systems'] do not"]
- L28: S2: quiz failed validation: ['question 3: the question copies the key point it tests; ask about it instead']
- L28: S3: quiz failed validation: ['question 2: correct_answer must be Yes or No']
- L28: S7: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L29: S5: quiz failed validation: ['question 4: the question copies the key point it tests; ask about it instead']
- L30: S3: quiz failed validation: ['question 2: options must all be different']
- L30: S5: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be True or False']
- L31: S5: quiz failed validation: ['question 3: correct_answer must be True or False']
- L35: OQ3: open question failed validation: ["key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['categorize the users'] do not"]
- L37: S7: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: multiple choice needs exactly 4 options and 4 explanations', 'question 4: correct_answer must be Yes or No']
- L38: S3: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L38: OQ4: open question failed validation: ["the learner never sees segments: name the topic instead of saying 'this segment'"]
- L39: S2: quiz failed validation: ['question 3: correct_answer must be True or False']
- L39: S2: summary failed validation: ['review question for S2.K1: "discussed in the lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for', 'review question for S2.K4: "mentioned in the lecture" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L40: S1: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L41: S1: quiz failed validation: ['question 2: correct_answer must be True or False']
- L41: S9: summary failed validation: ['review question for S9.K3: "the lecture focus" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L44: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['involve the users'] do not", "key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['quick evaluation techniques', 'quick feedback'] do not"]
- L45: S3: quiz failed validation: ['question 3: correct_answer must be Yes or No']
- L46: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['simple methods'] do not"]
- L47: S2: quiz failed validation: ['question 3: correct_answer must be True or False']
- L47: S4: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be True or False', 'question 4: correct_answer must be True or False']
- L47: S6: quiz failed validation: ['question 4: correct_answer must be Yes or No']
- L48: S2: summary failed validation: ["review question for S2.K3 must end with '?'"]
- L51: OQ4: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['optimal path'] do not"]
- L52: S1: quiz failed validation: ['question 1: "discussed in this segment" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L53: S2: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 3: correct_answer must be True or False']
- L53: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['whole day exposure'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['whole day exposure'] do not"]
- L54: S7: quiz failed validation: ['question 3: "from the video" — test the subject itself, not what the lecture or course says, and do not ask what an abbreviation stands for']
- L54: OQ3: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['constructed with objects'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['zeros and ones'] do not"]
- L55: S3: quiz failed validation: ['question 3: for multiple choice, put the correct option first and set correct_answer to "first option"']
- L55: OQ1: open question failed validation: ["key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['more polygons', 'complex vertex list'] do not"]
- L56: S3: quiz failed validation: ['question 2: multiple choice needs exactly 4 options and 4 explanations', 'question 2: for multiple choice, put the correct option first and set correct_answer to "first option"', 'question 4: multiple choice needs exactly 4 options and 4 explanations', 'question 4: for multiple choice, put the correct option first and set correct_answer to "first option"', "question 4: write the question so it ends with '?'"]
- L58: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['local coordinate'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['treated independently'] do not", "key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['texture images'] do not"]
- L58: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['continuous coordinate system'] do not"]
- L61: S3: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L61: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['rich animation system'] do not"]
- L62: S4: quiz failed validation: ['question 2: correct_answer must be True or False', 'question 4: correct_answer must be Yes or No']
- L62: S9: quiz failed validation: ['question 2: correct_answer must be Yes or No', 'question 4: correct_answer must be True or False']
- L62: OQ3: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['console output'] do not", "key point 4 needs at least 2 keywords that appear word for word in the reference answer; ['see the script'] do not"]
- L63: OQ4: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['experience optimization'] do not"]

Raw numbers: `timing.json`. Per-call tokens, retries and validator results: the `origin` list in each lecture file; judge results: its `quality` field.
