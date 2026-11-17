# QA latency and weak points: state (2026-11-17 afternoon: ready to merge)

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

## Done on 2026-11-17 afternoon (commits 9bdb150 and the one after it)
All runs: local RTX 5070, Gemma 4 12B QAT on llama.cpp (port 8092), QA_CONFIG = a scratch copy of
configs/gemma4_12b_llamacpp.json with server_log outside output/, QA_OUTPUT = a scratch copy of the layer (so the qa
logs never went into pipeline/output/). Nothing tracked was touched by the runs.

1. **Streaming finished.** `qa.answer_stream()` checked in `tests/fake_qa.py` (stream section): a step event per tool
   call in order (two calls in one message assembled from the deltas by index), drafts with labels and never a raw
   ID / half bracket / COVERED line, the last draft equal to the answer, `reset` when a round's text ended in tool
   calls, `done` == `answer()` for the same question, rounds sent with `stream` + `include_usage` and the same tools,
   tool_choice and thinking, tokens logged. Blocking `answer()` unchanged. **On the real llama.cpp** (5 questions, new
   layer): tool-call deltas arrive fine (parallel immersion + presence calls), answers equal in kind to the blocking
   ones; **time to first draft 2.3-4.6 s (median 3.2 s)** against 3.2-6.6 s to the whole answer. The viewer does not
   use it yet (`/api/ask_stream` + app.js: next steps).
2. **Speed experiment: thinking off in every round + forced tool call in round 0. NOT shipped.**
   - `tool_choice "required"` on llama.cpp with Gemma 4 and thinking off does not force a call: the model writes its
     plain answer ("the course does not cover this ... COVERED: no") and then cannot stop, so the round runs to
     max_tokens (12288 tokens, 3 min 20 s per attempt, retried 3 times). Bench B04 (FIFA) hung this way; stopped
     after B01-B03 (`bench_fast_old.jsonl`, 3 lines: 3.3 / 2.1 / 4.0 s). Reproduced with max_tokens 300 for B04 and
     B17: finish "length", content = a "not covered" answer.
   - A named function (`{"type":"function","function":{"name":"fact_lookup"}}`) is ignored by llama.cpp: B17
     (statistical test, taught in lecture 46) answered "the course does not cover statistical tests" with no call in
     0.8 s, B04 too. Same as this morning's think-off-everywhere run (B17 "not covered" both runs).
   - So the round-0 switches stay **thinking on, tool_choice auto** (shipped). They are now module switches
     (`qa.answer.ROUND0_THINK`, `ROUND0_TOOL_CHOICE`; `bench.py --variant shipped|fast|think`) so the experiment can be
     repeated on vLLM, where `required` and named functions are enforced by structured outputs (untested here: no
     EC2). Options for the user if more speed is wanted: (a) on vLLM, bench `--variant fast` first; (b) a code-side
     guard (round 0 without a tool call and thinking off -> run fact_lookup on the question, then answer); (c) shorter
     compare/prereq answers via prompts/qa_system.txt (Fable's file). None done: design choices.
3. **Bench, shipped code, `--runs 2`, 34 answers each, every answer read.**

| (34 answers each) | median | mean | p90 | max | > 8 s | covered false |
|---|---|---|---|---|---|---|
| before (morning baseline) | 5.4 | 6.4 | 12.1 | 16.2 | 9 | |
| after (morning, adbf84d) | 4.8 | 5.2 | 8.1 | 9.3 | 4 | 5 |
| shipped, current layer (`bench_think_old`) | 5.1 | 5.2 | 8.0 | 8.8 | 3 | 4 |
| shipped, NEW layer (`bench_think_newlayer`) | 4.9 | 5.2 | 7.6 | 8.9 | 3 | 3 |
| fast (think off + required), current layer | hung on B04 (3+ min per attempt) | | | | | |
| think off everywhere (morning, `bench_nothink`) | 3.1 | 3.2 | 5.4 | 5.9 | 0 | 6 (B17 wrong) |

   Per kind, median (max), current / new layer: not_covered 5.4 (5.7) / 4.4 (5.9); off_topic 5.9 / 5.9 (6.8); compare
   8.2 (8.8) / 8.0 (8.9); list 4.6 / 4.9; where 3.8 (5.2) / 3.4 (5.3); prereq 4.8 (5.2) / 5.8 (7.5); definition 3.9 /
   4.0 (4.4); how 3.5 / 3.2; lookup 5.5 / 5.0. Where the time goes (both): round 0 (thinking + tool choice) median
   1.6-1.7 s, the final answer median 2.6-2.7 s (compare 4-4.6 s for 220-280 tokens at ~60 tok/s); tools <= 0.7 s.
   Over 8 s: B05-B07 comparisons only (8.3-8.9 s; some runs call the second check_concept in round 1 instead of in
   parallel, +1.3 s). Grounding: 0 failures in both runs of both layers: B17 answered from lecture 46 (paired t-test,
   Wilcoxon, McNemar) every time; B01-B03 "not covered as such; closest: ..." with real citations; B04 "not covered",
   nothing cited; every claim cited, no wrong citation seen. Oddity left: B14 writes "[1]" / "[4]" (lecture numbers,
   not IDs) for the assumed concepts, as this morning.
4. **New knowledge layer** (ec2_sync/output/nptel_vr/knowledge, synonym merge + real definitions; 3122 concepts
   instead of 3384, 262 names merged into others, 3113 definitions rewritten). qa takes it with
   `QA_OUTPUT=<folder holding nptel_vr/knowledge>` (used a scratch copy; logs land next to it). Bench above: same speed,
   same grounding; prereq answers a bit longer (B13 lecture 40 now lists 5 concepts, 7.3-7.5 s). "What is X" checked
   on both layers (presence, behavioral data, x-ray visualization, application software, a VR headset, a fully
   immersive system, a game engine): **the new cards' definitions are used as the answer's first sentence**, and are
   better: old "a fully immersive system" answered only "one of the categories of VR systems" (the old card's
   definition was that category sentence), new gives the definition (blocks all senses ...); old "a VR headset" led
   with "a common example of a semi-immersive system", new leads with the HMD definition (the headset names merged
   into head-mounted display); old "x-ray visualization" / "behavioral data" paraphrased a history/questionnaire fact,
   new define the term. No regressions seen.
5. **vLLM demo config** `configs/gemma4_12b_vllm_demo.json` checked against the fake OpenAI server (fake_qa "vllm"
   section): the body carries `repetition_penalty` (not `repeat_penalty`), no `thinking_token_budget` (think_budget 0),
   the five tools, tool_choice auto, enable_thinking true in round 0 / false after; the answer is identical to the
   llama.cpp config's, blocking and streamed. `python -m qa --stop` now stops `vllm serve ... --port N` (or
   `vllm.entrypoints.openai.api_server ... --port N`) for an engine "vllm" config; checked with dummy processes (the
   one on the config's port stopped; another port and port N1 left alone).
6. `tests/fake_qa.py --layer DIR`: **PASS** (all old checks + stream, round 0, vllm; 26 logged questions). Note:
   `tests/fake_knowledge.py` (which fake_qa runs to build its layer when no --layer is given) FAILs one check on
   main as merged today ("capped: ... the prompt's new THE FACTS paragraph and first bullet": the 4a prompt changed on
   main), so fake_qa was run with `--layer` on the layer fake_knowledge still builds. Not a qa problem.

### How demo setup would start vLLM Gemma on the instance (not run: no EC2)
On the RTX PRO 6000 box, from the pipeline folder, with vLLM >= 0.23 in `~/vllm-venv` (the config's `binary`; or
change `binary`):

```bash
tmux new -d -s gemma -c ~/mtp-implementation/pipeline \
  "env PATH=$HOME/demo-venv/bin:$PATH python -m scripts.llm.serve configs/gemma4_12b_vllm_demo.json"
```

`scripts.llm.serve` launches whatever the config says (launch false only means clients attach), i.e.

```
~/vllm-venv/bin/vllm serve google/gemma-4-12B-it --served-model-name gemma-4-12b --host 127.0.0.1 --port 8096
  --max-model-len 32768 --max-num-seqs 8 --gpu-memory-utilization 0.85 --tensor-parallel-size 1 --seed 0
  --enable-prefix-caching --reasoning-parser gemma4 --enable-auto-tool-choice --tool-call-parser gemma4
```

then the viewer with `QA_CONFIG=configs/gemma4_12b_vllm_demo.json viewer/serve.py --warm` (setup_demo.sh does this with
`CONFIG=$PIPE/configs/gemma4_12b_vllm_demo.json`, except that its step 5 builds llama.cpp and its step 4 does not
install vLLM: on the vLLM path skip the llama.cpp build and `python -m venv ~/vllm-venv && ~/vllm-venv/bin/pip install
"vllm>=0.23"`; the gated `google/gemma-4-12B-it` needs the HF token). From the laptop: `ssh -L 8765:127.0.0.1:8765
demo` for the viewer (the model port need not be forwarded: the viewer runs on the box). To check before the demo:
`demo/demo_tool.py wait-model configs/gemma4_12b_vllm_demo.json`, then one `python -m qa "What is an HMD?" --config
configs/gemma4_12b_vllm_demo.json` (tool calls must come back as tool_calls, not text; if they come back as text add
`--chat-template examples/tool_chat_template_gemma4.jinja` from the vLLM repo to extra_args). Stop: `python -m qa --stop
--config configs/gemma4_12b_vllm_demo.json` on the box (a Docker-run vLLM is root-owned: stop the container instead).
**Speed caveat for the user:** BF16 12B is ~24 GB of weights; at the RTX PRO 6000's ~1.8 TB/s that is at most ~70
tok/s per request, about what the local Q4 QAT gives (~60 tok/s), so the demo box will not answer much faster than
the PC. An FP8 checkpoint (or `--quantization fp8`) would roughly double the decode rate; and with vLLM the
`--variant fast` bench is worth one run (forced tool calls are enforced there). Both are the user's choice.

## Next steps (in order)
1. viewer: `POST /api/ask_stream` in viewer/serve.py (text/event-stream, one `data:` line per event; falls back to
   ask()) and app.js ask() reading it (status "Looking through the course…" / "Writing the answer…", draft rendered
   with mdBlock, final render on done; steps only in dev mode; fall back to /api/ask on 404). Keep /api/ask. Run
   tests/viewer_smoke.py. This is what brings the felt wait to ~3 s (first draft median 3.2 s).
2. On the demo box: smoke the vLLM config (above), then `bench.py shipped --runs 2` and `--variant fast` there
   (QA_CONFIG=configs/gemma4_12b_vllm_demo.json); read every answer; ship `fast` only with 0 grounding failures.
3. Decisions for the user: FP8 on the demo box; the code-side search guard (option b above); shorter compare/prereq
   answers (prompt wording, Fable's file); B14's "[1]"-style lecture numbers.
