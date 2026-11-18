# Stage 2b as it was before the fresh run of block 0 (moved here on 2026-11-12)

- `fact_maps/`, `fact_text/`, `judgements/`: lecture 1 only, the old fact definition: 65 facts of 2a (Qwen 3.8 27B),
  judged by Sage-A1.5, 7 failed, all rewritten by Qwen (58 kept + 7 rewritten = 65).
- `llm/cache.jsonl`, `calls.jsonl`: those calls, and the judge round on the 62 facts of the new definition
  (lectures 1, 4, 16; 03:40 UTC) with three of its four rewrites (4/S1 was cut off when the spot instance was lost).

The judge verdicts of that round are `analysis/fact_judge/runs/old_1112.json`. Run notes: `pipeline/pipeline.ipynb`,
"Facts with the new definition (2026-11-12, EC2)". The fresh 2b run replaced this folder in
`pipeline/output/nptel_vr/stage_2b_verify_facts/`.
