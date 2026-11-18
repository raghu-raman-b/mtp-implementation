# 2c trial on the fresh 2b facts (2026-11-12)

Stage 2c (`pipeline/scripts/s2c_concepts.py`, prompts as drafted) run once with Qwen 3.8 27B on the verified facts of
lectures 1, 4, 16 (the fresh 2b run, before block 1 revises the judge), written here with `--out` instead of
`pipeline/output/`. A trial to see the prompts on real input early; block 2 runs 2c on the facts block 1 settles.
Log: `pipeline/output/logs/concepts_trial_fresh_2b.log`. 12 segments, 129 concepts (29 defined), 193 relationships,
993 s; checks: no_triple 8, reverse 10, name_not_in_facts 9, alias_not_in_facts 8, alias_not_written 8,
no_shared_fact 3.
