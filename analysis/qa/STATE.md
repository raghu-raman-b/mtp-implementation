# QA weak points: state (stopped on request, 2026-11-15)

## Done
- Timing per round in `output/<course>/qa/answers.jsonl` ("timing": model s, tokens, thinking chars, tool s), committed.
- `analysis/qa/bench.py` (17 questions B01-B17). Baseline `bench_before.jsonl` (2 runs): median 5.4 s, mean 6.4 s,
  max 16.2 s (B06 AR vs VR), B01 Kalman 12.3/13.6 s. **Where the time goes: the model thinking before the final
  answer** (1400-2400 thinking chars, 7-14 s); tool calls are 0-0.9 s (fact_lookup embeds on the CPU); prereq
  answers spend 5-7 s writing long lists (330-430 output tokens).
- Calibration (`calibrate.py`, `calibration_queries.json`, `calibration.json`): 38 in-course 0.63-0.86, 3 partly
  taught 0.60-0.69, 39 out-of-course 0.21-0.72 (unrelated 0.21-0.48, neighbouring 0.43-0.72). AUC 0.989 (0.997
  without the rephrasings: rephrasings lift the negatives). Chosen cut-off **0.55** (0.05 under the lowest
  in-course/partly score): flags 27/39 out, 0 in. Old 0.4 flagged 18/39.
- `qa/knowledge.py`: `concept_uses(k)` (facts of lecture k per concept), `is_hub(c)` (graph weight < 1).
- `qa/tools.py` (uncommitted before this WIP): LOW_SCORE_DEFAULT 0.55; `ToolResult.found`; check_concept on an
  unknown name now shows the 5 closest facts (+ low note) so no extra round; card "Defined in" cites the first
  defining fact and its time (one time, matching the citation); `lecture_dependencies` rewritten: earlier concepts
  ranked by uses in the lecture, >= 2 uses shown with definition, hubs named apart, single mentions listed as
  "in passing", lectures to revise ranked by those uses, assumed/introduced capped. Checked by hand on 16, 40, 30:
  the odd items (augmented virtuality, HMD-1950s, location awareness, marker) move to "in passing".
  Cause of the odd items: the graph links K -> L on any single mention, and the old tool listed met_again in ID
  order cut at 12, hiding the most used concepts (tracking: 28 uses in lecture 16, lecture 13 was "indirect").

## Not done (next steps, in order)
1. `qa/answer.py`: thinking off after round 0 (per request: `Request(sampling={"chat_template_kwargs":
   {"enable_thinking": False}})`); early exit: when every tool result so far has `found is False`, make the next round
   the final one (tool_choice "none" + FINAL_NUDGE).
2. `qa/answer.py` `cite()`: drop a model-written time or range right before a citation ("at 14:25-15:00 [28/S1]");
   de-duplicate repeated labels (a run of the same label in a block keeps one; a list whose items all share one
   label gets it once on its lead-in line).
3. `tests/fake_qa.py`: the "before lecture 8" check reads "direct 4, 5, 6" in the summary, which is now
   "revise ..."; rework it to the synthetic layer's hand-worked answer; add checks for the citation de-dup, the
   time strip, the early exit, the unknown-name facts. Run it.
4. Run `bench.py after --runs 2` with `QA_CONFIG` = a copy of the Gemma config whose `server_log` is outside
   `pipeline/output/` (the default writes the tracked `output/logs/llm_server_8092.log`; it was restored with git
   checkout after the baseline). Compare with `bench_before.jsonl`; read each answer. Stop the server (`python -m qa
   --stop`). Commit `qa: ...`.
