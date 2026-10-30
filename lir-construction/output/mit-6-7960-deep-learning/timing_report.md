# LIR build time: MIT 6.7960 Deep Learning

2026-10-30 12:36 · engine **llamacpp** (unsloth/gemma-4-E4B-it-GGUF:gemma-4-E4B-it-UD-Q8_K_XL.gguf (Q8, KV f16)) · 32 parallel slots · thinking on for every call · temperature 0

## Summary

- **3 lectures, 222.6 min of video, built in 16.7 min** (plus 2 s to start the model server).
- About **5.6 min per lecture** on average, or **4.5 min of processing per hour of video**.
- 311 LLM calls, 369,540 output tokens (including thinking), 459,381 input tokens.
- Validation: 263 generated items, 53 retries, 15 items still failing after retries.

## Per lecture

Processing time is attributed: each stage's wall time is split across lectures by how long their calls held a server slot.

| Lecture | Title | Video (min) | Segments | LLM calls | Output tokens | Processing (min) | min per video hour |
|---|---|--:|--:|--:|--:|--:|--:|
| L01 | Introduction to Deep Learning | 60.7 | 10 | 61 | 73,923 | 3.55 | 3.52 |
| L02 | How to Train a Neural Net | 79.4 | 18 | 117 | 146,016 | 6.39 | 4.83 |
| L03 | Approximation Theory | 82.6 | 19 | 131 | 148,054 | 6.76 | 4.91 |

## Per stage

| Stage | Wall time (s) | LLM calls | Input tokens | Output tokens | Output tok/s |
|---|--:|--:|--:|--:|--:|
| stage1_segment | 71.9 | 3 | 57,210 | 8,272 | 115.0 |
| stage2_annotate | 433.7 | 129 | 196,728 | 177,709 | 409.8 |
| stage3_goals | 27.4 | 5 | 1,758 | 3,359 | 122.7 |
| stage4_course_state | 97.1 | 56 | 23,914 | 34,640 | 356.9 |
| stage5_generate | 372.1 | 118 | 179,771 | 145,560 | 391.2 |
| stage7_assemble | 0.3 | 0 | 0 | 0 | 0.0 |

## Flags for review

- L03: OQ2: open question failed validation: ["key point 1 needs at least 2 keywords that appear word for word in the reference answer; ['scale the depth'] do not"]

Raw numbers: `timing.json`. Per-call tokens, retries and validator results: the `provenance` list in each lecture file.
