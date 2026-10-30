# LIR build report: Foundation for Virtual and Augmented Reality Systems

2026-10-30 16:37 · generator **unsloth/gemma-4-E4B-it-GGUF:gemma-4-E4B-it-UD-Q8_K_XL.gguf (llama.cpp, KV f16)** · judge **gpt-6-luna (OpenAI API, reasoning medium)** · 32 parallel slots · thinking on for every call · temperature 0

## Summary

- **63 lectures, 1860.5 min of video, built in 170.8 min** (about **2.7 min per lecture**, **5.5 min of processing per hour of video**).
- 5,089 LLM calls, 4,997,424 output tokens (including thinking), 5,253,977 input tokens.
- Videos: 63/63 downloaded.
- API spend: **$0.517** this run (993 calls); $0.536 of the $2.40 budget used so far (ledger: `api_spend.json`).
- Open-answer scorer: m = 2, tau = 0.8 (calibrated, 57% agreement on 42 generated answers).

## Per lecture

Processing time is attributed: each stage's wall time is split across lectures by how long their calls held a server slot.

| Lecture | Title | Video (min) | Segments | LLM calls | Output tokens | Processing (min) | min per video hour |
|---|---|--:|--:|--:|--:|--:|--:|
| L01 | General Intro to XR | 33.4 | 7 | 0 | 0 | 0.0 | 0.01 |
| L02 | Application Domains and System Categories | 28.0 | 3 | 0 | 0 | 0.0 | 0.01 |
| L03 | Application Domains and System Categories | 21.2 | 3 | 0 | 0 | 0.0 | 0.01 |
| L04 | Definitions | 24.4 | 2 | 42 | 40,764 | 1.42 | 3.49 |
| L05 | Definitions | 21.8 | 4 | 46 | 51,103 | 1.81 | 4.97 |
| L06 | Historical Evolution | 27.9 | 5 | 67 | 71,120 | 2.44 | 5.26 |
| L07 | Historial Evolution | 25.6 | 5 | 70 | 71,355 | 2.44 | 5.74 |
| L08 | Issues & Challenges | 32.2 | 5 | 59 | 63,976 | 2.21 | 4.12 |
| L09 | Issues & Challenges | 26.4 | 3 | 47 | 50,902 | 1.85 | 4.19 |
| L10 | Cybersickness | 26.4 | 3 | 48 | 44,765 | 1.57 | 3.57 |
| L11 | Cybersickness | 32.8 | 3 | 44 | 47,781 | 1.68 | 3.08 |
| L12 | Cybersickness | 36.6 | 9 | 94 | 101,603 | 3.54 | 5.79 |
| L13 | VR Hardware | 34.1 | 5 | 70 | 69,042 | 2.35 | 4.13 |
| L14 | VR Hardware | 26.2 | 5 | 84 | 84,826 | 2.98 | 6.82 |
| L15 | AR Hardware | 34.9 | 8 | 120 | 105,302 | 3.59 | 6.18 |
| L16 | Understanding Tracking I | 27.8 | 5 | 65 | 65,923 | 2.3 | 4.97 |
| L17 | Understanding Tracking - I | 25.3 | 6 | 67 | 64,414 | 2.19 | 5.18 |
| L18 | Understanding Tracking II | 33.1 | 8 | 115 | 108,145 | 3.65 | 6.62 |
| L19 | VR Software | 26.2 | 7 | 87 | 79,245 | 2.71 | 6.2 |
| L20 | VR Software | 36.3 | 7 | 86 | 84,608 | 2.94 | 4.86 |
| L21 | AR Software | 26.8 | 3 | 59 | 54,069 | 1.89 | 4.23 |
| L22 | AR Software | 19.8 | 5 | 86 | 73,863 | 2.54 | 7.68 |
| L23 | XR as Interactive Systems | 21.7 | 6 | 81 | 78,062 | 2.69 | 7.43 |
| L24 | XR as Interactive Systems | 26.5 | 6 | 67 | 69,698 | 2.43 | 5.51 |
| L25 | Human Factors in XR | 26.3 | 5 | 66 | 65,387 | 2.21 | 5.05 |
| L26 | Human Factors in XR | 25.0 | 6 | 85 | 77,099 | 2.66 | 6.37 |
| L27 | Visual Perception & Displays I | 31.0 | 10 | 103 | 103,136 | 3.52 | 6.81 |
| L28 | Visual Perception & Displays II | 28.8 | 9 | 118 | 119,689 | 4.03 | 8.38 |
| L29 | Auditory Sense & Immersive Experience | 20.2 | 5 | 74 | 68,959 | 2.34 | 6.94 |
| L30 | Auditory Sense & Immersive Experience | 29.1 | 7 | 91 | 87,134 | 3.01 | 6.22 |
| L31 | Other Senses & Full Immersion | 34.3 | 5 | 74 | 74,679 | 2.53 | 4.43 |
| L32 | Interactive System Development Life Cycle Stages | 37.7 | 8 | 121 | 119,399 | 4.1 | 6.52 |
| L33 | Introduction to Majuli case study | 23.6 | 5 | 76 | 75,368 | 2.6 | 6.6 |
| L34 | Introduction to Majuli case study | 22.4 | 3 | 62 | 56,190 | 1.9 | 5.08 |
| L35 | Usability requirement gathering and specification | 23.0 | 6 | 81 | 88,089 | 2.9 | 7.59 |
| L36 | Usability requirement gathering and specification | 32.4 | 9 | 103 | 108,155 | 3.73 | 6.9 |
| L37 | Usability requirement gathering and specification | 29.1 | 8 | 113 | 102,576 | 3.42 | 7.06 |
| L38 | System Design | 30.5 | 9 | 126 | 116,214 | 3.96 | 7.8 |
| L39 | System Design | 46.8 | 6 | 77 | 79,945 | 2.77 | 3.55 |
| L40 | System Design | 31.9 | 6 | 85 | 85,303 | 2.86 | 5.37 |
| L41 | System Design | 29.1 | 9 | 106 | 98,667 | 3.38 | 6.97 |
| L42 | System Implementation | 40.8 | 9 | 116 | 107,891 | 3.65 | 5.36 |
| L43 | System Implementation | 23.0 | 4 | 59 | 63,438 | 2.11 | 5.51 |
| L44 | System Implementation | 32.2 | 4 | 61 | 58,525 | 2.02 | 3.76 |
| L45 | System Implementation | 31.8 | 6 | 86 | 85,073 | 2.88 | 5.44 |
| L46 | System Implementation | 36.9 | 7 | 91 | 95,562 | 3.27 | 5.32 |
| L47 | System Implementation | 30.4 | 9 | 107 | 100,160 | 3.43 | 6.77 |
| L48 | System Implementation | 21.2 | 5 | 73 | 72,632 | 2.45 | 6.92 |
| L49 | VR experience optimisation | 27.1 | 8 | 117 | 106,628 | 3.68 | 8.14 |
| L50 | VR experience optimisation | 29.4 | 7 | 93 | 85,566 | 3.0 | 6.13 |
| L51 | VR experience optimisation | 45.7 | 9 | 122 | 117,283 | 4.03 | 5.29 |
| L52 | VR experience optimisation | 21.4 | 6 | 70 | 67,344 | 2.3 | 6.43 |
| L53 | VR experience optimisation | 20.2 | 5 | 87 | 88,604 | 2.99 | 8.87 |
| L54 | VR resource optimization | 35.6 | 11 | 123 | 125,035 | 4.21 | 7.09 |
| L55 | VR resource optimization | 39.8 | 5 | 59 | 65,517 | 2.3 | 3.47 |
| L56 | VR resource optimization | 43.5 | 8 | 96 | 96,538 | 3.27 | 4.51 |
| L57 | VR resource optimization | 42.1 | 8 | 127 | 120,301 | 4.03 | 5.75 |
| L58 | VR resource optimization | 37.7 | 8 | 115 | 109,762 | 3.74 | 5.95 |
| L59 | VR resource optimization | 15.9 | 5 | 74 | 74,027 | 2.5 | 9.42 |
| L60 | Linking theory to practice | 20.4 | 6 | 89 | 87,208 | 2.89 | 8.5 |
| L61 | Linking theory to practice | 29.1 | 6 | 97 | 92,948 | 3.18 | 6.56 |
| L62 | Linking theory to practice | 44.3 | 10 | 123 | 132,856 | 4.45 | 6.03 |
| L63 | Concluding remarks | 15.2 | 3 | 37 | 34,860 | 1.24 | 4.92 |

## Per stage

| Stage | Wall time (s) | LLM calls | Input tokens | Output tokens | Output tok/s |
|---|--:|--:|--:|--:|--:|
| transcripts | 5.3 | 0 | 0 | 0 | 0.0 |
| stage1_segment | 342.6 | 60 | 309,278 | 85,567 | 249.7 |
| stage2_annotate | 2768.8 | 894 | 974,859 | 1,246,691 | 450.3 |
| stage3_goals | 174.1 | 66 | 21,755 | 69,069 | 396.7 |
| stage4_course_state | 1317.2 | 1116 | 375,359 | 698,652 | 530.4 |
| stage5_generate | 3546.2 | 1252 | 1,365,869 | 1,523,473 | 429.6 |
| stage6_calibrate | 23.5 | 8 | 14,217 | 7,736 | 328.8 |
| stage6_judge | 2061.7 | 1693 | 2,192,640 | 1,366,236 | 662.7 |
| stage7_assemble | 6.6 | 0 | 0 | 0 | 0.0 |
| docs | 0.4 | 0 | 0 | 0 | 0.0 |

## Validation: code checks (layer 2)

| Stage | Items | Passed first time | Passed after retry | Still failing (resolved by code) |
|---|--:|--:|--:|--:|
| stage1_segment | 63 | 63 | 0 | 0 |
| stage2_annotate | 776 | 675 | 37 | 64 |
| stage3_goals | 64 | 58 | 6 | 0 |
| stage4_canonicalize | 1049 | 1049 | 0 | 0 |
| stage4_edges | 63 | 45 | 16 | 2 |
| stage5_open_questions | 252 | 106 | 126 | 20 |
| stage5_primer | 60 | 60 | 0 | 0 |
| stage5_quiz | 388 | 357 | 27 | 4 |
| stage5_summary | 388 | 386 | 1 | 1 |
| stage6_calibrate | 16 | 16 | 0 | 0 |
| stage6_repair | 654 | 600 | 42 | 12 |

## Validation: judge (layer 3)

| Check | Judged | Passed first time | Repaired and passed | Dropped | Replaced by code | Not judged (budget) |
|---|--:|--:|--:|--:|--:|--:|
| sub-goal describes segment | 388 | 380 | 8 | 0 | 0 | 0 |
| definition faithful | 1622 | 1453 | 151 | 18 | 0 | 0 |
| quiz item answerable + correct | 1552 | 1391 | 137 | 24 | 0 | 0 |
| summary supported | 388 | 294 | 88 | 0 | 6 | 0 |
| open question sound | 252 | 175 | 54 | 23 | 0 | 0 |
| edge true | 927 | 457 | 0 | 470 | 0 | 0 |
| recall item sound | 113 | 79 | 0 | 34 | 0 | 0 |

## Notes

Items that failed code checks and were repaired or replaced by code:

- L06: S2: summary failed validation: ['the recap has 4 sentences; write 2 to 3']
- L09: OQ3: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['representational fidelity'] do not"]
- L11: OQ3: open question failed validation: ["key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['questionnaire'] do not"]
- L12: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['intensity gradually decreases'] do not"]
- L13: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['track how eyes'] do not"]
- L14: OQ3: open question failed validation: ['key point 4 needs at least 2 keywords that appear word for word in the reference answer']
- L21: OQ1: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['create a framework'] do not"]
- L22: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['existing tools'] do not"]
- L23: S4: quiz failed validation: ['q4: the stem copies the point it tests; ask about it instead']
- L23: OQ3: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['user capabilities'] do not"]
- L31: OQ2: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['reduce cyber sickness'] do not"]
- L32: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['iterations between stages'] do not"]
- L35: OQ1: open question failed validation: ['key point 3 needs at least 2 keywords that appear word for word in the reference answer; ["user\'s goals"] do not']
- L35: OQ3: open question failed validation: ["key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['categorize the users'] do not"]
- L38: OQ4: open question failed validation: ["the learner never sees segments: name the topic instead of saying 'this segment'"]
- L40: OQ1: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['specialized setups'] do not"]
- L42: S8: quiz failed validation: ['q4: the stem copies the point it tests; ask about it instead']
- L46: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['gotten by chance'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['confirm the reliability'] do not", "key point 4 needs at least 2 keywords that appear word for word in the reference answer; ['nature of the input data'] do not"]
- L46: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['simple methods'] do not"]
- L47: S2: quiz failed validation: ['q4: the stem copies the point it tests; ask about it instead']
- L53: S3: quiz failed validation: ['q4: the stem copies the point it tests; ask about it instead']
- L54: OQ3: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['constructed with objects'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['zeros and ones'] do not"]
- L58: OQ1: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['local coordinate'] do not", "key point 2 needs at least 2 keywords that appear word for word in the reference answer; ['treated independently'] do not", "key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['texture images'] do not"]
- L61: OQ4: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['rich animation system'] do not"]
- L63: OQ3: open question failed validation: ["key point 3 needs at least 2 keywords that appear word for word in the reference answer; ['experience optimization'] do not"]

Raw numbers: `timing.json`. Per-call tokens, retries and validator results: the `origin` list in each lecture file; judge results: its `quality` field.
