# QA latency and weak points: state (paused on request, 2026-11-17 10:55 IST)

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

## Done on 2026-11-17 (commits adbf84d, 1e9b6e8 on worktree-agent-a5b92c4a8975db27d)
1. `qa/answer.py`: rounds after 0 sent with `chat_template_kwargs.enable_thinking=false` (the config's other switches
   kept); llama.cpp honours it per request (think_chars 0 in every later round, KV reuse intact). Early exit: when
   every tool result so far has `found is False` (errors / bad args are None and block it), the next round is the
   answer (tool_choice none + FINAL_NUDGE); logged as `early_exit` in answers.jsonl.
2. `cite()`: model-written time before a citation removed (needs a lead-in word "at/from/around/near/between/by", or a
   parenthesised range; "16:9 [ID]" kept); adjacent labels merged; a run of equal labels written once **within one
   line** (first version did it per paragraph and list items lost their label, B10/B17; fixed in 1e9b6e8); a list
   whose items all share one label gets it once on the lead-in line. The citations list is unchanged.
3. `tests/fake_qa.py`: lecture_dependencies checked against the synthetic layer by hand (lecture 6 relies on
   stereoscopy, revise 2; lecture 8 nothing earlier, 4 in passing); new checks: thinking per round, early exit
   (and not with one found result, nor after bad tool calls), unknown-name closest facts, citation tidying incl. a
   mixed list. **PASS** (also with the WIP below).
4. Bench (`bench.py after --runs 2`, local RTX 5070, Gemma 4 12B QAT llama.cpp, QA_CONFIG = scratch copy with
   server_log outside output/; nothing tracked touched). Runs 0-1 of bench_after were made before fix 1e9b6e8 (only
   the label tidying of the text differs; timing is the same code).

| (34 answers each) | median | mean | p90 | max | > 8 s |
|---|---|---|---|---|---|
| before | 5.4 | 6.4 | 12.1 | 16.2 | 9 |
| after (shipped: think round 0 only + early exit) | 4.8 | 5.2 | 8.0 | 9.3 | 4 |
| experiment: thinking off in every round | 3.1 | 3.2 | 5.4 | 5.9 | 0 |

Per kind, median s (max), before / after / think-off-everywhere: not_covered 7.5 (13.6) / 4.7 (5.3) / 4.0 (5.4);
off_topic 4.0 / 4.7 / 0.7; compare 10.3 (16.2) / 8.1 (9.3) / 5.4 (5.9); list 4.2 / 5.7 / 3.2; where 2.6 / 3.7 / 2.4;
prereq 6.5 (8.5) / 4.8 (5.9) / 3.5; definition 4.3 / 3.7 / 2.9; how 5.9 / 4.1 / 2.3; lookup 4.9 / 4.8 / 0.4.

Answers read (all 34 after): grounded, every claim cited, no wrong citation seen. B01 Kalman and B03 redirected walking
now answered "not covered as such; closest: drift-correction complementary filter / full gait" in one round
(check_concept's unknown-name facts score 0.49 / 0.53 < 0.55 -> early exit); covered stays True when the model writes
"COVERED: partly" (old rule: partly counts as covered). B16 answers from the unknown-name facts without a fact_lookup.
Left-over oddities: B14 run 0 wrote "[1, 4]" (lecture numbers, not IDs; left as is since "[0, 1]" can be math).
Remaining time is (a) round-0 thinking 1-3 s and (b) long final answers (compare/prereq 200-280 tokens at ~55 tok/s,
B07 immersion vs presence 9.3 s both runs: 3.3 s thinking + 6 s for 277 tokens). Where/list got ~1 s slower than the
baseline: longer answers from the new cards (temperature 1.0 variance too).
**Think-off-everywhere is NOT safe**: B17 (statistical test, covered by lecture 46) answered "the course does not cover
this" with no tool call (0.4 s), both runs; B04 off-topic answered without a tool. Not shipped. Partial experiment
(uncommitted runner, round 0 tool_choice "required" + thinking off): B01 3.9 s, B02 2.7 s, B03 3.4 s, tools called;
stopped at the pause (bench_nothink_required.jsonl, 3 lines). Both are design choices for the user.

## Half-done (WIP commit, untested against a real server)
- **Streaming** (coordinator request: an option the viewer can use, blocking API unchanged): `qa.answer_stream(q,
  course, lecture)` yields `{"event":"step",tool,args,result_summary}`, `{"event":"draft","text"}` (whole answer so far
  with labels; replaces the previous draft), `{"event":"reset"}`, last `{"event":"done","result":<answer() dict>}`.
  Rounds are sent with `stream: true` + `stream_options.include_usage` by `stream_round()` (body from `llm._body`, so
  the same fields; tool-call deltas assembled by index; logged via `llm._log_attempt`). `draft_text()` holds back a
  half-written word, an unclosed bracket and a begun COVERED line. `scripts/llm/fake_server.py` streams SSE when asked
  (content pieces, tool call id+name then args in 2 pieces, usage, [DONE]). fake_qa still PASSes (blocking path).
- **vLLM demo config** `pipeline/configs/gemma4_12b_vllm_demo.json` written (google/gemma-4-12B-it BF16, port 8096,
  launch false, 32k ctx, 8 slots, reasoning_parser gemma4, extra_args `--enable-auto-tool-choice --tool-call-parser
  gemma4`, think_budget 0 so no `thinking_token_budget` is sent). Parser names from recipes.vllm.ai (Gemma 4 12B
  recipe; vLLM >= 0.23 or the `vllm/vllm-openai:gemma4-unified` image; the recipe also passes `--chat-template
  examples/tool_chat_template_gemma4.jinja` from the vLLM repo: add it if tool calls come back as text). To verify
  on the box. Static check: the client sends the same request fields (tools, tool_choice, chat_template_kwargs
  enable_thinking per request); differences: `repetition_penalty` (llama.cpp: `repeat_penalty`), the request hash
  (engine and model_path are in it; qa uses no cache so nothing depends on it), the answers (BF16 vs the local QAT Q4).

## Next steps (in order)
1. fake_qa: add streaming checks (answer_stream with the fake: step events in order, drafts with labels and no raw
   IDs/COVERED, reset when a round with content ends in tool calls, done == answer() for the same script) and a run
   of qa against the vLLM config with the fake server (port override, engine vllm: body has repetition_penalty, no
   thinking_token_budget, tools/tool_choice/enable_thinking as with llama.cpp). Fake server only, no EC2.
2. Try answer_stream on the local llama.cpp (does it stream tool-call deltas with --jinja for Gemma 4?) on 3-4 bench
   questions; time to first draft.
3. viewer: `POST /api/ask_stream` in viewer/serve.py (text/event-stream, one `data:` line per event; falls back to
   ask()) and app.js ask(): read the stream (status line "Looking through the course…" / "Writing the answer…", draft
   rendered with mdBlock, final render as now on done; steps only in dev mode; fall back to /api/ask on 404). Keep
   /api/ask unchanged. Run tests/viewer_smoke.py.
4. `python -m qa --stop` kills only llama-server: also `vllm serve.*--port N` for an engine vllm config.
5. Rerun `bench.py after --runs 2` (fresh file) on the final code; read answers; update this file; commit `qa: ...`.
6. Decisions for the user: thinking off in round 0 (+ tool_choice "required" in round 0, to be benched fully) saves
   ~1.5 s per answer; a shorter-answer wording in prompts/qa_system.txt (Fable's file) for compare/prereq; demo
   should keep `viewer/serve.py --warm` (embedder + server warm at start).
