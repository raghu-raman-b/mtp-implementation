# Partial judge run with Qwen 3.8 27B (6k thinking), all 63 lectures, stopped (2026-11-13)

The MVP run first started 2b on all 63 lectures with Qwen as judge (`configs/qwen38_27b_vllm_6k.json`, the revised
judge prompt e86d22b6a041 of review 1) and rewriter. The user then skipped the judge for the MVP (block 1's review found
it did more harm than good), so 2b became a pass-through (`--no-judge`). The answers the judge had given by then are
kept here: `llm/cache.jsonl` (judge answers, with the thinking), `llm/calls.jsonl`, `run.log` (the log of the first
attempt is lost; this is the queue's job log of the stopped run, if copied). Usable for block 1 later: these are the
revised prompt's first verdicts, with Qwen instead of Sage.
