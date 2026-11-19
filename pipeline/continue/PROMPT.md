# Continue pipeline v3 (prompt for a new session)

Paste this file's path into a new chat, or say "continue from pipeline/continue/PROMPT.md". The session that writes
this file updates it after every finished step, so the state below is current; `STATUS.md` next to it is the short live
status (shown by `progress.sh`).

## Who you are and the rules (the user's standing instructions)

You carry out pipeline v3 in this repository as **"O"** in `pipeline/PLAN.md`: scripts, tests, reports, commits. Read
`pipeline/PLAN.md` in full first, then the notebook sections and run notes you need (`pipeline/pipeline.ipynb`; read it
with python, it is large), then this file's "State" and "Next".

- After every item: tick its box in PLAN.md, commit only that item's files, push. A Fable session may work in the same
  tree and commit gold sets under `analysis/`; leave its files alone. Update this file and `STATUS.md` after every step.
- Items owned by **F** (Fable): gold sets, question set, new prompts. Do not write them; carry on with what does not
  depend on them and say what is waiting. For a prompt revision after a report, call the **`block-reviewer`** agent
  (runs on Fable) and apply the exact text in its CHANGES. **Check every decision with Fable** (the user's rule): a
  Fable agent (`Agent` with `model: "fable"`, or `block-reviewer` at gates).
- At each gate: write the report (`analysis/<block>/report.md`), call `block-reviewer` with the block number and the
  report path, follow its verdict. On "proceed" commit `block N done`.
- Do not change the design (what a stage takes in and puts out, which stages exist, what a fact or concept is). Design
  ideas go under "Decisions for you" in PLAN.md; carry on with the current design.
- Real models only on the EC2 the user started. **Keep the EC2 working**: queue long runs on it (`ec2_queue.sh`), so they
  go on when the local session's usage runs out. Plumbing is checked with the fake model first.
- The user wants work parallelised: spawn **Opus** agents (`model: "opus"`, `isolation: "worktree"`) for independent
  code; they commit in their branch, you cherry-pick onto main one commit per item, tick boxes, run their tests, push.
- Stop and tell the user if: a push fails; `block-reviewer` does not load or does not run on Fable; a gate fails twice;
  an item would delete or overwrite existing outputs under `pipeline/output/` (the user allowed recomputing 2b on
  2026-11-12).
- Quality matters most (user, D12): every model answer gets a code check and a retry; read the outputs, not only counts.

## How things run

- **EC2** (SSH host `mtp`; the user starts and stops it): `pipeline/ec2.md`. After every start: the NVMe is wiped, so
  `rsync` the pipeline over and run `setup_ec2.sh` in tmux (~25 min, mostly downloads), then start the queue:
  ```bash
  rsync -a -e "ssh -o ClearAllForwardings=yes" --exclude __pycache__ --exclude 'input/*/media' --exclude 'output/logs' --exclude '.hf_token' pipeline/ mtp:pipeline/
  rsync -a -e "ssh -o ClearAllForwardings=yes" pipeline/.hf_token mtp:pipeline/.hf_token
  ssh -o ClearAllForwardings=yes mtp "tmux new -d -s setup 'bash ~/pipeline/setup_ec2.sh 2>&1 | tee ~/pipeline/output/logs/setup.log'"
  ssh -o ClearAllForwardings=yes mtp "cd pipeline && tmux new -d -s queue 'bash ~/pipeline/ec2_queue.sh'"   # after setup
  ssh -o ClearAllForwardings=yes mtp "echo 'qwen <command>' >> pipeline/queue/jobs.txt"                       # add jobs
  ```
  The queue starts the server each job needs (qwen on 8094, sage on 8095; one at a time). Results come home through
  the sync loop into `ec2_sync/` (gitignored); merge them into `pipeline/output/` (check the caches are append-only:
  local cache = prefix of the EC2's), commit, push. If the user copies the EC2 folder by hand, merge from that and
  remove the duplicate copies.
- **Local live view**: `bash pipeline/continue/progress.sh` (needs tmux) makes the tmux session `mtp` with the status
  view, logs, EC2 server logs and the **sync loop**; `tmux attach -t mtp`. Recreate it after a PC restart.
- **To run a stage from the PC against the EC2** instead: port forward `ssh -f -N -L 8094:127.0.0.1:8094 -L
  8095:127.0.0.1:8095 mtp` (no `ClearAllForwardings` here: it clears `-L` too; the user's config also forwards 8000,
  which may warn). The configs attach only and wait up to 30 min for their server.
- **Gotchas**: zsh does not word-split `$var` (spell commands out); tests that snapshot `pipeline/output/` trip on logs
  that other runs are writing under `output/logs/` (rerun when nothing runs); never `pkill -f` a pattern that matches
  your own shell; fake servers in tests must not use 8094/8095 while a forward is up.

## QA OPTIMISATION 2026-11-19 (~20:15 IST) — READ THIS FIRST
User decisions: check_concept takes a list (one call, all concepts); fact_lookup/lecture tools stay separate calls
(explainable); new tool course_structure fed by a new stage 4f (Gemma 4 12B, per segment, picks sentence IDs about
course logistics only; text copied verbatim by code); viewer names each concept loaded; same 65 questions (no new
set), no RAG rerun; ours rerun with thinking vs no-thinking in the tool round (label "thinking"/"no thinking"
latency); docs: targeted edits by a new Opus agent (tool table + new optimisation section, minimal tokens); graphs:
SciencePlots, paper-ready, professional labels, all studies, folder pipeline/results/. Roles: Sonnet = code/running/judging,
Opus = docs only; main session orchestrates.
Tasks: T1 QA code (Sonnet, worktree) | T2 stage 4f (Sonnet, worktree, local GPU) | T3 pipeline/results/ (Sonnet, worktree)
-> R1 review/merge -> T4 rerun ours think/nothink, 65 q + repeats (Sonnet, GPU) -> T5 Sonnet judges -> T6 graphs
update -> T7 docs (Opus, targeted) -> R2 merge/push. T1 merged (d6cb9c6), T3 merged (d059584: pipeline/results/, 21 figures). RUNNING: T2 (GPU).
User 20:05 (then away for the day): cache-warm pings every 50 min while the GPU runs (session one-shot crons 20:55 ...
02:45; say "warmed"); EVERY graph regenerated with our latest (v2) scores, the optimisation before/after graphs in a
separate folder; T6 also fixes the activities "Serves the course goals" label -> lecture goals; at the end move
graphs/ to pipeline/results/ (update README, script paths, any docs links).
20:20 T2 run1: 61 statements, ~half signposting, 7 segments cut at max_tokens (1/S0, 1/S4 ...) -> agent revising
prompt + max_tokens, rerun all 386 (run1 kept in history/run1). User 20:58: wire 4f into the pipeline -> T2b (Sonnet,
after 4f merge): rebuild_queue.sh (+4e +4f after 4d), schemas/course_structure.md, demo launcher check warns if missing,
failure inventory + 4f kinds; docs stage 4f entry goes into T7. Schedule: T2 ~22:15, R1 ~22:25, T2b ~22:50, T4 ~23:05,
T5 ~23:25, T6 ~23:50, T7 ~00:20, R2 ~00:35.
22:15 status: T2 merged (039cacb; rerun with explicit exclusions: 28 statements, 0 failed, six-module outline from
lecture 63), T2b merged (cbbb835), T4 done (2056544), T5 judged 290 (cd2ef37). Results run 1: correct ours 0.80 ->
ours_v2 0.854 / ours_v2_nothink 0.831 (RAG 0.815); false-claim answers 5 -> 1 / 0; latency median 5.66 -> 5.59 / 3.90 s
(RAG 4.24); structure 0.6 -> 0.9; multihop 0.5 -> 0.708 / 0.583; not_covered 8/9 -> 7/9 (N05). RUNNING: T6 graphs
regen + qa_optimisation/ + move to pipeline/results/ (Sonnet, worktree); T7 docs targeted (Opus, worktree).
DONE ~23:00: T6 merged (01fb5df: all 25 figures regenerated, qa_optimisation/ before-after, folder now
pipeline/results/), T7 merged (docs: tool table, stage 4f, measured optimisation section #qa-opt, build totals
10.8 -> 11.4 h measured, "about 12 GPU hours"; build byte-identical). QA OPTIMISATION COMPLETE.
Open for the user: default QA mode for the demo (no-reasoning is faster than RAG and as accurate); sample questions
still from the earlier run.
User 20:10: graph text professional and crisp, no over-explaining: short correct titles and axis labels, no
parenthetical asides like "(lower is better)", no explanatory notes on the plot; explanations belong in README.md.

## DAY 2026-11-19 (from 11:30 IST) — READ THIS FIRST; supersedes NIGHT below
User (11:35): finish today: activities study, judging answers + activities, results to docs, sample questions; then
merge. User's point for the docs: QA can be optimised to ONE tool call fetching every needed concept at once, so latency
is about one call (design point, not measured; memory qa-one-call-optimization).
- Night queue had died after multihop GPU runs (02:38); activities study never started (READY not touched).
- DONE: multihop judged by 2 Sonnet agents (168, judge/sonnet_M{A,B}.jsonl), merged; tables/figures/run_stats for 65
  questions (6f3b22f). Overall correct: ours 0.80, rag 0.815, rag_think 0.808, graphrag_text 0.777, abl_graph 0.785,
  abl_facts 0.762, plain 0.254. Multihop ours 0.5 vs rag 0.625 (M08/M09: "earlier ideas" routed to the prereq graph).
  make_samples.py (0d7f665): 6 samples D02 D06 P01 P02 P04 S01 (ours beats every baseline, no hallucination).
- Activities study: fake test failed (summarize lacked ours_gemma; generate.py never made ours_gemma) -> fixed:
  generate.py runs s5 on Gemma for the sample (code checks + retry, no judge) (5fc5204). GPU queue restarted 11:37
  (detached queue.sh; log baseline-tests/queue.log; marker activities_study/GPU_DONE).
- RUNNING: docs part 2 (Opus agent, worktree agent-afef209db8fea72c8): baseline section "what the method buys" + full
  method in the Evaluation part; activities subsection waits for the study's out/summary.md (send it to the agent).
- **DONE 19 Nov ~20:00**: activities study GPU 16:12; 6 Sonnet blind judges (1037 items); summary (d5db9fa); baseline
  branch merged (1ae5f6d); sample_questions.json + multihop label (6dfd0de, viewer smoke PASS); docs part 1+2 merged
  (Opus; build byte-identical). Activities: layer-only gains = typed concept maps (Sonnet 97% vs 75/69%), recall (grounded
  83% vs 66/69%), complete_map/match/crossword/review cards; B1 clearly worse; B2 (our prompts + transcript) ~ties on
  single-lecture kinds. NEXT (deferred by the user): DEMO_PLAN rewrite, rehearsal; design question: structure facts
  (rule 7); QA one-call optimisation (not built).
- (was) NEXT: GPU_DONE -> 3 Sonnet agents judge out/sonnet/packets (blind) -> summarize.py -> send summary to docs agent ->
  review docs -> merge baseline + docs branches to main, sample_questions.json via make_samples.py on main, push.

## NIGHT 2026-11-19 (from 02:05 IST) — READ THIS FIRST; supersedes everything below where they differ

**User (02:00):** get every test done tonight (studies, GPU runs), queued so they go on if the session's limit runs
out; minimal tokens until everything is ready for reports + docs; keep this file updated after every step; say
"warmed" on a ~55-min timer (session one-shot crons 02:59 ... 13:04; re-create them if the session restarted).
**Goal of the baseline study (user): sell the method** — show where ours is worth it and why ~12 h of build compute
is fine; keep RAG's honest wins in (credibility). Judge = Sonnet (user).

Baseline worktree: `.claude/worktrees/agent-ac043cfbb4e8a782d` (branch `worktree-agent-ac043cfbb4e8a782d`, pushed
37d80cf). Folder `baseline-tests/`.
- DONE: all GPU runs for the 53 questions; Sonnet judged all 592 answers (`judgments.jsonl`; Opus's 257 in
  `judgments_opus.jsonl`, agreement kappa 0.715, `judge_agreement.md`); ablations were INVALID (restrict_tools patched
  the function `qa.answer`, not the module) -> fixed, rerun, re-judged (old in `runs/invalid/`). Tables/figures by
  `summarize.py`, `figures.py`. Results run 1: ours 0.868, rag 0.858, rag_think 0.858, graphrag_text 0.821,
  graphrag_notext 0.717, plain 0.255, abl_facts 0.802, abl_graph 0.887. Prerequisite: ours 0.5, abl_graph 0.75,
  abl_facts 0.0, all baselines <=0.125. RAG wins structure (S02 six modules, S05 what the course skips): those are
  excluded from facts BY DESIGN (prompts/fact_extraction.txt rule 7), not a bug — a design question for the user.
  RAG = 738 sentence chunks within a lecture (~400 tok, 60 overlap, whole course), Qwen3-Embedding-0.6B, top 8;
  median ctx 4,027 tok vs ours 4,804.
- **GPU queue (detached, `setsid nohup bash baseline-tests/queue.sh > baseline-tests/queue.log`)**, lock
  `baseline-tests/gpu.lock`: (1) waits for `"category": "multihop"` in questions.jsonl -> all 8 systems + r2/r3 for
  ours/rag/rag_think -> `MULTIHOP_DONE`; (2) waits for `activities_study/READY` -> `activities_study/gpu.sh` ->
  `activities_study/GPU_DONE`. If the queue died: rerun the same command (steps resume, markers skip done steps).
- RUNNING agents: (a) Sonnet writes 12 multihop questions -> `questions_multihop.jsonl` + `.md` (kinds: chain,
  spread 4+ lectures, course order, connect; gold checked against transcripts, written blind to answers). NEXT: the
  orchestrator reviews, then appends them to questions.jsonl (that releases queue step 1).
  (b) Opus builds `baseline-tests/activities_study/` (user-approved design: 6 lectures by code; ours vs B1 plain
  transcript prompt vs B2 our prompts with the transcript in place of facts; kinds quiz, recap, open_question,
  odd_one_out, put_in_order + concept_map and recall attempts; judges: pipeline's Gemma activity judges, code checks,
  blind Sonnet packets; summarize script; "only possible with the layer" list). Fake-tested, then touches READY.
- AFTER the queue: Sonnet judges multihop answers (render_for_judge.py -> todo packets -> judge/sonnet_M*.jsonl ->
  append to judgments.jsonl) and the activities blind packets; summarize.py, figures.py, judge_agreement.py,
  activities summarize; commit + push the branch.
- THEN docs part 2 (docs agent's branch `worktree-agent-afef209db8fea72c8`, part 1 done: 085adc3 + 59b4dee, rebased on
  main 1ab20c7, not merged): baseline section framed "what the method buys": (1) where ours wins and which part of
  the layer causes it (multihop, prerequisites, definitions, ablations), (2) activities only the layer makes possible,
  (3) activity quality drop without it, (4) cost: ~12 h one-off build vs per-question cost similar to RAG, (5) where
  RAG ties/wins (single-lecture lookups; structure, excluded by design). Method + question set + per-category tables.
  Then sample_questions.json from demo_questions.json (by code), merge docs + baseline branch to main, push.
- Main: `--no-qa` merged (1ab20c7). The user's own commits (stats/) are on main too; rebase before pushing.

## State (updated 2026-11-18 00:05 IST) — READ THIS FIRST; it supersedes the older sections below where they differ

**Roles now (user, 2026-11-17/18).** The main session is the **reviewer + orchestrator**: it briefs agents, reviews
their output, merges to main and pushes. Opus agents (worktrees) write code and docs. Fable only decides and reviews,
never writes (memory `fable-review-only`); when Fable is unavailable, Opus agents review. The user may skip a review
("no review needed"): then merge after the agent's own tests. Do not run agents unrelated to the demo. Cache-warm pings
only when the user asks.

**Goal: the best possible demo of the MVP** (nptel_vr, 63 lectures). The user writes the slides themselves.
**No fallback on demo day** (user: "we rawdog this"): no replay mode, no recorded backup.

### Done on 2026-11-17 evening (main 6cc8c67, pushed)
- **Docs v3**: `pipeline/docs/pipeline.html` (one offline page, ~551 KB; Parts I–V + appendix; story of v1 -> v2 -> v3
  with real failed prompts, "why this pipeline" vs plain LLM / RAG / GraphRAG (argued, not measured yet), "why this
  design" (14 arguments, each marked measured/argued), every stage with prompts, samples, commands, times; Evaluation
  part with every eval set written out and what-fails-where tables; upcoming fixes; future work). Sources:
  `pipeline/docs/src/` — rebuild with `python3 pipeline/docs/src/build.py <repo root>` (byte-identical). Opus-reviewed,
  fixes applied (01df357). Has a placeholder "Measured comparison (baseline tests)" to fill.
- **Remote-model demo setup** (merged 6cc8c67, user skipped review): model on the GPU instance only, app on the
  laptop. Instance: `pipeline/demo/ec2_model_server.sh --engine llamacpp|vllm` (asks if no flag; `--status`, `--stop`,
  `--no-embed`; vLLM needs ≥40 GB). The query embedder also runs there (`demo/embed_server.py`, cosine ≥0.9997 vs stored
  vectors), so the laptop needs only numpy. Laptop: `python -m demo setup|run|check|bench|push|tunnel`
  (`demo/launcher.py`, stdlib only); Windows wrappers `setup_windows.ps1`, `run_demo.ps1` (-Check, -Bench, -Push).
  Stream events documented in `pipeline/schemas/qa_stream.md` (round, thinking, call, step with display line + details,
  answer_start, done; every event has `t`). Tests: fake_qa, viewer_smoke, demo_remote pass (fake_qa's "nothing under
  output/ changed" trips only while the shared llama-server writes its log). NOT yet run on Windows, a real instance,
  or vLLM: checklist in `analysis/demo/remote_setup.md` (do it at the rehearsal).
- **Design mockups** (not code): canvas https://claude.ai/artifact/UDrY88AbBdhTbKoRHQ3HDm, 3 directions × 6 screens
  (roadmap, lecture player with quiz overlay + caption-to-notes, activities tab, recap tab with animated cards, Ask
  full-window chat with the "what the model is doing" sequence, lecture/concept maps): A Folio (editorial, light),
  B Theatre (dark cinematic, raw tool-call trace in Ask), C Signal (bold product, light + dark glass player; phone view).
  Working copies: scratchpad `design/project/` (may be gone; the canvas is the source). **The user has not picked yet**;
  recommended: C Signal + B's tool-call trace in Ask.

### In flight
- **Baseline tests** (Opus agent, branch `worktree-agent-ac043cfbb4e8a782d`, folder `baseline-tests/`): ours vs plain
  LLM vs RAG over transcripts vs GraphRAG-style/graph-only, same Gemma 4 12B on the local GPU, ~50 questions with gold,
  Opus-judged (correct, hallucination, citation validity, context tokens, latency). **Paused 00:10 on 11-18, WIP commit
  932c303** (branch pushed). 53 questions (9 categories, gold + fact IDs); ours, plain and RAG (738 chunks, top 8) ran on
  all 53; light GraphRAG extraction 176/476 text units (graph, community reports and its answers not run); long context:
  all transcripts = 244,971 tokens, 1.87× the 131,072 context. PARTIAL (24 of 53 judged: definitions, explanations,
  comparisons, lists; ours/plain/RAG only): correct ours 1.00 / RAG 0.96 / plain 0.79; hallucinations 1 / 0 / 5; valid
  citations 108/110 / 118/121 / none. Median latency 6.5 / 3.85 / 1.56 s. RAG nearly ties on the easy categories; the
  not-covered, where, prerequisite, structure and formula questions (where systems should differ most) are not judged
  yet. Resume with the commands in `baseline-tests/STATE.md` (~45–60 min extraction, then judge 29 + GraphRAG), then
  merge, then fill the docs placeholder. RAG embeddings not committed (`python3 rag.py build`, 27 min CPU).
  **Docs must include the method** (user, 00:15): how each system was built and run (chunking, embedding, top-k,
  prompts, GraphRAG extraction/communities/reports/query, model and sampling, the judge and its criteria, how to
  rerun), the full question set, and per-category tables, not only the results. **Fairness points to settle before
  finishing** (raised by the orchestrator, for the user to confirm): the GraphRAG query leaves out source text units
  (real GraphRAG local search includes them; run it with text units, optionally also without); the baselines run with
  thinking off while ours thinks in round 0 (consider a RAG run with thinking on); one sample per question at
  temperature 1.0 (consider 2–3 runs on the categories that differ).

### Decisions recorded (user, 2026-11-17/18)
- **Lecture experience**: roadmap (sequential) · lecture map · concept map as the top tabs; a lecture opens with the
  video playing full-window, own controls only; the video is cut by segment (play ranges; no file cutting) and **pauses
  at each segment end with the activities overlaid** (start: goal + prerequisites + recall; after each part: recap ->
  quiz (+ put in order where it exists); end: complete the map, match pairs, crossword, odd one out, open question);
  subtitle sentences clickable -> saved to Notes with ID and time, shown at the end; an **Activities tab** with all
  activities; a **Recap tab** with animated cards; activities animated; **Ask is the highlight**: its own full-window
  professional chat, sample questions, and a "what the model is doing" sequence from the stream events (concepts
  loaded, facts checked, writing the answer). Clean, uncluttered, professional fonts, responsive.
- **Connecting concepts** (concepts with `defined: false`, 1,806): **no concept cards, not in the glossary, a different
  (muted, non-clickable) representation in the concept graph; never use their model-written definition anywhere** —
  in QA (check_concept etc.) give the model their lecture **facts only**. Only the 1,316 defined concepts have cards and
  are in the glossary. (Yesterday's viewer brief wrongly kept their cards open; fix in the redesign.)
- **Recaps**: show only judge-passing points; hide the summary text when it failed (222 of 347 texts; 371 failed
  points); 6 recaps with no passing point vanish (that break shows only the quiz). Display-side, no regeneration.
- **Crosswords with failed clues**: keep the grid, show the failed words **pre-filled**; never show their clues.
- **Part (segment) titles**: the design needs a short title per segment (386; the data has only goals). **Generate them
  with Gemma 4 12B from the segment's facts and goal** (3–6 words; code check on length/wording; review a sample).
- Still to do from the weak-spot list: duplicate concepts (HMD / VR headset, interaction / user interaction, iOS /
  iPhone OS) via a reviewed merge list + remap (code); the FOV alias on horizontal field of view; odd alias lists
  (fragments/generic words); KaTeX for formulas in answers (vendored, offline). Warm-up at start is done (setup merge).

### UPDATE 2026-11-18 10:15 IST (user) — supersedes the FINAL TASK LIST below where they differ
- **O2 dropped.** No Opus-decided merge list or alias removal list: a stronger model must not decide changes to pipeline
  outputs (memory `no-stronger-model-fixes`). Duplicates/aliases are not fixable by display rules (no pipeline signal).
  Instead **S7 (Sonnet)**: code-only failure inventory `analysis/failures/inventory.{py,json,md}` (every failure kind:
  activities, crosswords, recaps, duplicates/aliases by code rules, 2c flags, 0a, part titles; with how each was handled:
  fixed in the pipeline / display rule / hidden / not fixed) -> O4 turns it into the docs' "what fails where" table.
- Part titles contract: `output/<course>/stage_4e_part_titles/titles.json` = {"run", "segments": {"1/S0": {"title"|null,
  "ok", "problems"}}}; failed titles stay null (no one fills them in). S1 exposes `title` per segment in /api/view.
- O3: ours does not need a rerun (layer unchanged); GPU order S6 -> O3 -> O5.
- **O4 also documents the demo setup on a Windows machine** (user, 10:15): setup_windows.ps1, run_demo.ps1 (-Check,
  -Bench, -Push), python -m demo, tunnel to the instance; mark it untested on real Windows until the rehearsal.
- **10:25**: S1, S2, S3 merged. User picked **design C (Signal)** with changes (home: no stats, no course goals,
  keep the 12-week route and the dev mode toggle; player: subtitles centred; an activity hides subtitles and controls
  and blurs the video). Mockups + changes: `analysis/demo/design_c/`. O1 (Opus) building since 10:25 (C's Ask rail,
  B's raw tool-call trace as a collapsed detail per step; null part title -> "Part N").
  New schedule: S7 ~11:00, S6 ~11:30, O1 ~14:30 + review ~15:15, O3 11:30-17:00, O4 15:15-18:00 (baselines last),
  O5 17:00-18:30.
- **10:45 (user)**: demo prep (O5 DEMO_PLAN, rehearsal) deferred; work up to the docs. Sample questions that only our
  design answers go into the Ask screen itself (`pipeline/viewer/sample_questions.json`, filled from O3's
  `baseline-tests/demo_questions.json`, chosen by code). O3 (Opus) runs in the old baseline worktree with minimal
  tokens: numbers, tables, method README only; O4 draws the inferences. O4 starts after 15:00 (cron at 15:03). Cache-warm
  pings every 50 min until 19:05 (session crons). O1 told: looks + agreed behaviours only, performance budget measured.
- **~10:55**: S6 merged (49f7ef4; 386/386 titles ok, 12 retried). O3 stopped by the user after its setup (51e57b9:
  all systems coded, `baseline-tests/gpu_all.sh`, method README draft); a fresh Opus runner runs gpu_all.sh, judges,
  writes tables/figures/demo_questions.json (minimal tokens) in the same worktree.
- **11:07**: the session restarted; O1 and the baseline runner stopped and were resumed by message; gpu_all.sh had
  stopped at abl_graph 44/53 and was restarted by the orchestrator (resumable, log `baseline-tests/gpu_all.log`).
- **11:18**: O1 merged (b405a4c..14f4743; user waived the review: "it did the tests"). Screens in
  `analysis/viewer/design_c_screens/`; home 211->140 kB. Sample questions file is a placeholder until the baseline
  runner's demo_questions.json. Only the baseline runner is still running; docs at 15:03.
- **11:30 plan (user)**: the baseline runner only finishes gpu_all.sh + run-side numbers, no judging. At 15:03 in
  parallel: a fresh Opus judge (remaining ~335 answers, then summarize/figures/demo_questions by script), S8 `--no-qa`
  (serve.py, python -m demo run, run_demo.ps1), O4 targeted docs: demo loading (no GPU / local GPU / EC2 / Windows),
  what-fails table, baseline section (method, results, strengths/weaknesses of each, how ours overcomes them) after the
  judge. Nothing about the viewer or part titles in the docs. Sample questions filled after the judge (~16:30).
- Running since 10:10 (Sonnet, worktrees): S1 serve.py display rules, S2 QA facts-only, S3 KaTeX, S6 part titles
  (local GPU), S7 failure inventory. Design pick: the user gives it soon (gates O1).
- Schedule: S3 ~10:30, S2 ~10:45, S1 ~10:50, S7 ~11:15, S6 ~11:30; O1 11:00-15:45 (if picked by 11:00); O3 11:30-17:00;
  O5 17:00-18:30; O4 17:00-19:00; rehearsal after the user's docs + slides.

- **2026-11-19 (new session)**: the 15:03 jobs never ran (session crons died with the session). Baseline GPU runs
  had finished 11-18 ~13:11 (all 8 systems x 53 + repeats r2/r3 on 28 for ours/rag/rag_think); committed + pushed on
  the baseline branch (6c20dff). **User: judge with Sonnet.** To keep one judge across systems, Sonnet re-judges all
  592 answers (4 parallel Sonnet agents, packets todo_00-21 -> judge/sonnet_{A,B,C,D}.jsonl -> judgments.jsonl); the
  257 Opus judgments moved to judgments_opus.jsonl and serve as a second-judge agreement check
  (`judge_agreement.py` -> judge_agreement.md). Running in parallel: S8 `--no-qa` (Sonnet, worktree; serve.py
  --no-qa, `python -m demo run --no-qa`, `run_demo.ps1 -NoQa`), O4 docs part 1 (Opus, worktree: demo loading in 4
  setups + what-fails table). After judging: merge judgments, summarize.py, figures.py, run_stats.py,
  judge_agreement.py; O4 part 2 (baseline section); sample_questions.json from demo_questions.json; merge all to main.

### FINAL TASK LIST (user-approved 2026-11-18 00:25; supersedes "Next" below). Sonnet = simple, Opus = complex.
Baselines: finish GraphRAG (run it WITH source text units, and also without) + add two ablations of ours
(facts only = fact_lookup alone; graph only = concept cards/prerequisites/overview/goals, no fact search) + RAG with
thinking on + 2–3 runs on the categories that differ. Local GPU fits one model: order GPU users S6 -> O3 -> O5.
- Wave 0 (user): design pick.
- Wave 1 (parallel):
  - S1 (Sonnet) serve.py display rules as API data: recaps = passing points only (failed text dropped, empty recaps
    dropped); crossword failed entries `prefilled: true`, clue removed; connecting concepts: no card route, glossary
    defined-only, map nodes flagged `connecting`. Keep viewer_smoke passing.
  - S2 (Sonnet) qa: connecting concepts never return a definition, facts only (check_concept etc.); fake_qa test;
    also make fake_qa's output snapshot ignore `output/logs/`.
  - S3 (Sonnet) KaTeX vendored into viewer/vendor (offline) + a `renderMath(el)` helper for the design build.
  - S6 (Sonnet, local GPU) part titles: Gemma 4 12B, one 3–6-word title per segment (386) from its facts + goal; code
    check + retry; output into the knowledge layer; Opus reviews a sample.
  - O2 (Opus) duplicates + aliases: candidate finder (shared alias, name = other's alias, acronym expansion, generic
    head, embedding similarity) -> Opus reviewer decides -> `stage_3_registry/merge_overrides.json` -> 3c applies
    (survivor = the defined concept, its ID + definition) -> 4c/4d rebuilt (code) -> activity concept IDs remapped,
    code-made kinds rebuilt -> alias rules (shared alias kept only where defined; generic head word; fragments) with a
    reviewed removal list -> 4d ref check, activities --check, viewer smoke.
- Wave 2: O1 (Opus) build the chosen design (after S1–S3 merge; renders S1's flags, S3's math, S6's titles);
  O3 (Opus, GPU after S6) baselines as above, Opus-judged, README with method + tables + examples.
- Wave 3: O4 (Opus) docs update (baseline method/results/ablations, fixes, part titles, new viewer, remote setup);
  O5 (Opus, GPU) DEMO_PLAN rewrite on the new build.
- Wave 4: rehearsal (user + orchestrator) after the user's docs and slides.
Orchestrator reviews every merge (Opus reviewer for O-tasks unless the user waives).

### Next (in order)
1. **User picks the design** on the canvas (and any mix).
2. In parallel: (a) a **fresh Opus agent builds the chosen design** into `pipeline/viewer/` (keep the speed work and
   routes; includes the viewer-side fixes: recap/crossword display rules, connecting concepts, KaTeX, part titles shown);
   (b) **weak-spot fixes, data side** (duplicates merge list, aliases; connecting-concept facts-only in QA);
   (c) **part titles** with Gemma 4 12B on the local GPU (free it first: the baseline agent used the shared llama-server
   on 8092).
3. **Docs update** with the baseline results, the weak-spot fixes, part titles and the new viewer (edit
   `pipeline/docs/src/`, rebuild).
4. **DEMO_PLAN.md update** for the new design (screens, chat flow, item IDs, questions rechecked).
5. **Rehearsal** once the user has finished docs + slides: Windows laptop + an instance near the venue, run the
   `analysis/demo/remote_setup.md` checklist, network test first (SSH to us-east-1 was ~40 kB/s from the user's network).
6. Later: plan the next course's MVP run (deep learning; ask which dataset: `mit_6_7960_deep_learning` or
   `introduction_to_machine_learning`).

## State (updated 2026-11-15 13:10 IST)

**2026-11-15 session: complete the MVP (user).** Git tag `mvp-2026-11-13` marks the MVP as it was demoed.
- **Rebuild of the skipped stages** on the EC2: 3b (synonym merge) -> 3c (with the model's groups) -> real 4a (Qwen)
  -> 4b -> 4c -> 4d -> the whole activities stage again on Qwen (every model kind reads concept lists and definitions,
  so a remap alone is not enough; ~380 calls) -> `--check` -> merge home once verified. 2b's judge stays off (block 1
  found it did more harm than good; block 1 continues separately).
- **EC2**: the user is swapping instances (an RTX PRO 4500 32 GB was too small for the FP8 27B: weights ~28 GB; if a
  32 GB GPU comes back, `nvidia/Qwen3.8-27B-NVFP4` (~22 GB, ModelOpt, Blackwell-native) is the fallback in vLLM).
- **Agents running** (worktrees; cherry-pick, test, push): viewer rebuild like the earlier pipelines' viewers
  (segment-cut video, activities between segments, lazy per-lecture loading) (Opus); QA weak points 1-5 (Opus);
  block 1 CHANGES 8-9 gold (Fable; user granted Fable writes, `.claude/settings.json` allows `analysis/**`,
  `pipeline/prompts/**`); activity prompt review + judge prompts before the activities rerun (Fable); gold sets: block 6
  question set, block 3 pair gold, block 2 gold for 4 segments (Fable). After the activity review: an Opus agent adds
  the code checks it lists (quiz option length etc.) and the judge to `s5_activities.py`.

- **Agents' work in progress is saved and pushed** (19:30 IST, before a usage limit; WIP commits on their branches):
  viewer `worktree-agent-a761733a118c47330` (serve.py started), QA `worktree-agent-a5b92c4a8975db27d` (timing logs,
  bench before, calibration), activity prompts `worktree-agent-aedc2d89f3f3e6d76` (six prompts revised, judges not yet),
  block 1 gold `fable-block1-gold-changes-8-9` (gold.json edits), gold sets `fable-gold-sets` (nothing yet). If the
  agents cannot be resumed, start new ones on these branches with the original briefs (in this file's agent list).
  EC2: the old instance is gone; the user brings a new one; then `pipeline/rebuild_queue.sh <config>`.

## State (as of 2026-11-13)

Done and pushed (see `git log`):
- **Block 0** complete. Fresh 2b on lectures 1, 4, 16: 62 facts in, 54 kept, 7 rewritten, 1 removed, 62 out.
- **Block 1**: `analysis/fact_judge/compare.py`; runs `base`, `seed1`, `seed2`, `old_1112`, `rejudge` in
  `analysis/fact_judge/runs/` (old prompt 09a26b62f66a); report draft `analysis/fact_judge/report.md`.
  **Review 1 = "change"**: `analysis/fact_judge/reviews/review_1_2026-11-13.md` (keep it: its findings go into the
  next report). Done from it: CHANGES 1-7 (judge and rewrite prompts revised, exact text; new prompt hash
  e86d22b6a041); CHANGE 11 (`compare.py`: thinking-budget calls, pooled verdicts per gold fact, 2b outcome vs gold,
  majority/any of three, flips without borderline, prompt hashes; runs now record their calls).
  Open from it: CHANGES 8-9 (F: gold edits, label the 8 rewrites in `gold_rewrites.json`, ~12 subtle seeded entries in
  `seeded_subtle.json`) - **a Fable agent for this was blocked by the permission check** (it would edit `gold.json` and
  push); the user decides how (allow / write to new files only / do it themselves). CHANGE 10 (25+ real failures)
  needs the user's word on the source. CHANGE 12 (rerun on the EC2) and 13 (report additions) after 8-9.
  Note: the rerun must also cover `seeded_subtle.json` once it exists (compare.py reads only `seeded.json` today: add it).
- **Block 2**: `s2c_concepts.py` + checks; trial on real facts `analysis/concepts/data/trial_fresh_2b/`.
- **Block 3**: `embed.py`, `s3a/s3b/s3c`, `analysis/registry/embed_compare.py` (waits for F's pair gold).
- **Block 4**: `s4a`-`s4d` + `schemas/knowledge.schema.json`.
- **2a on all 63 lectures** (EC2 queue): 2006 facts in `stage_2a_fact_extraction/` (must not be used for tuning; rerun
  if the extraction prompt changes).
- **Decisions** (user answered D8, D9, D11, D12, D13; Fable's review with exact texts:
  `analysis/decisions/fable_review_2026-11-13.md`). Shared code done: `llm/client.py` keeps the attempt with the
  fewest problems when retries run out (`res.ok` False, `res.parsed` set) + new FEEDBACK text; `fact_checks.is_acronym`.

- **2c decisions merged** (D8, D12; `tests/fake_2c.py`, 44 checks; 2c removed from `fake_run.py`). Its problem lines
  other than F's two are O's wording, for F to review.

**FOCUS NOW: THE MVP (user, 2026-11-13, ~02:00 IST).** The user's definition: (1) the current pipeline run on the
FULL course; (2) ALL activities built and run, including games (O may write the prompts); (3) the viewer updated, showing
everything; (4) EC2 ready; (5) use Qwen only (the instance is an L40S, 46 GB); (6) everything built and working by the
end of the day (the vision); tests and gates come after.

State of the MVP (2026-11-13 02:05 IST):
- `configs/qwen38_27b_vllm.json`: server flags for the 46 GB GPU (context 32768, 32 slots, fp8 KV, 0.93); request
  hashes unchanged (2a cache still answers). Qwen judges in 2b too (no `--judge`; Sage not downloaded).
- The lectures 1, 4, 16 2b run (Sage judge) moved to `analysis/fact_extraction/data/history/2b_2026-11-12_fresh_sage/`
  (block 1's analysis refers to it; `compare.py`'s STAGE_CACHE path now points at a missing folder: fix when block 1
  resumes).
- Stage 3/4 decision agent merged (D8, D9, D11, D12; tests: fake_registry 59, fake_knowledge 88 checks). Its notebook
  markdown is NOT inserted yet (in the agent's report; redo from the code's docstrings if lost).
- **Thinking budget 6k** (user, 2026-11-13: "6k is optimal for speed and quality"): `configs/qwen38_27b_vllm_6k.json`
  (think_budget 6144, max_tokens 12288) for every stage from 2b's judge on; 2b's rewriter keeps
  `qwen38_27b_vllm.json` (it must find 2a's answers in 2a's cache, whose hashes include the 16k budget). The activities
  job: `qwen python3 -u scripts/s5_activities.py nptel_vr --llm configs/qwen38_27b_vllm_6k.json`.
- **EC2 queue running** (restarted 20:39 UTC with the 6k config): jobs in `pipeline/queue/jobs.txt` on the EC2: pip sentence-transformers
  (done) -> 2b all -> 2c all -> 3a (CPU embeddings, vllm-venv python) -> 3b -> 3c -> 4a -> 4b -> 4c -> 4d (CPU).
  Next to append: `qwen python3 -u scripts/s5_activities.py nptel_vr --llm configs/qwen38_27b_vllm.json` once the
  activities agent's script is merged and rsynced. Local tmux `mtp` (window `sync`) copies results into `ec2_sync/`;
  merge them into `pipeline/output/` (caches append-only), commit, push.
- **Three Opus agents in worktrees** (cherry-pick when they report): (a) activities stage `scripts/s5_activities.py` +
  prompts `prompts/activity_*.txt` + `tests/fake_activities.py`, per the contract `pipeline/schemas/activities.md`;
  (b) question answering `pipeline/qa/` (`qa.answer(question, course, lecture)`, tools over `knowledge/`, Gemma 4 12B
  locally, `tests/fake_qa.py`); (c) viewer `pipeline/viewer/` + `viewer/serve.py` (Range video, `/api/ask`),
  `tests/viewer_smoke.py`.
- **Viewer merged** (commit 609e434; `python pipeline/viewer/serve.py nptel_vr [--port 8765]`, `/?dev=1` for dev mode;
  `tests/viewer_smoke.py` 40 checks). It already shows segments and videos from 1b/0a for lectures without
  `knowledge/`; reload picks up new layers. Its data wishes went to the activities agent (complete_map must not show a
  hidden concept elsewhere; per-item `facts` in match_pairs, crossword, concept_map). Other data notes: 0a sentences
  with `start: null` (filled from the previous end), long prerequisite lists from hub concepts, dense course map.
- **Question answering merged** (`pipeline/qa/`; `python -m qa "question" --lecture 4` from `pipeline/`; Gemma 4 12B
  on local port 8092, started on demand, `python -m qa --stop`; `tests/fake_qa.py` 31 checks; client gained
  `Request.tools`/`tool_choice`, `Result.tool_calls`, hashes unchanged; runtime logs `output/<course>/qa/` gitignored).
  The viewer's `/api/ask` loads `qa` from `--qa-path` (default `pipeline/`). The "no close match" cut-off 0.4 is a guess.
- **Activities merged** (`scripts/s5_activities.py`, prompts `prompts/activity_*.txt` written by O, `tests/fake_activities.py`
  37 checks; contract additions: per-item `facts` in concept_map/complete_map edges, crossword entries, match pairs).
  First real run is the queue's job 11: read `activities/activities.txt` and `checks.json` (clue masking, unresolved).
- **4a skipped** (user, 02:30 IST): `s4a_definitions.py --from-facts` writes `definitions.json` from each concept's first
  defining fact (`"source": "facts"`), no model; 4d and the viewer work from it. Run real 4a later (`run()`).
- **Judge skipped** (user, 02:22 IST, after block 1's review): `s2b_verify_facts.py --no-judge` passes the 2a facts
  through unchanged (2a IDs kept; judgements say "not judged"). The 27 segments the Qwen judge had answered are saved
  in `analysis/fact_judge/data/qwen_judge_partial_2026-11-13/`.
- **WEAK POINTS TO WORK ON NEXT (user, 10:15: "record them, we work on them later")**, in rough priority:
  1. **Definitions (4a ran `--from-facts`)**: each concept's "definition" is its first defining fact; only ~26% of the
     1,107 review cards read like a definition. Hurts match pairs (~70% of pairs problematic), recall (10 of 22 sampled
     not a definition), crossword clues, concept cards, QA's "what is X". Fix: run real 4a (Qwen) - one call per concept,
     ~3,400 calls (fewer after 3b), cap 40 facts, checks with retry already built.
  2. **Synonym merge (3b skipped; `s3c --no-model`)**: duplicates on screen (headset / head-mounted display / virtual
     reality headset / VR headset on 11 lecture maps; AR Toolkit / augmented reality toolkit; 3D model / three-dimensional
     model; xr engine / extended reality engine; ios / iPhone operating system). Plan in the "Deferred" bullet below
     (425 clusters ~1.5 h; 9 answers cached in `stage_3_registry/llm/`; remap activity concept IDs after the rebuild).
     Also "VR headset" (C0077) breaks D8: `acronym_in_name` is report-only in 2c.
  3. **The fact judge (2b skipped)**: block 1 is open (review 1 CHANGES 8-13; F's gold edits blocked by the permission
     check; `compare.py` STAGE_CACHE points at the moved 2b folder; the revised prompt's first 27 Qwen verdicts are in
     `analysis/fact_judge/data/qwen_judge_partial_2026-11-13/`).
  4. **Activities**: quiz correct option is the longest in 52% of questions (bias; add a check or shuffle-length rule);
     odd one out 4/20 contestable; put in order 3/7 weak (59/A5 not a sequence); crosswords: 5 unresolved (13/A19,
     21/A11, 29/A11, 51/A21 wrong SHORTESTPATH clue, 58/A20), 60/A13, 16/A13, 2/A8, over-masking ("graphics" for
     SCENEGRAPH); match pairs: masked blanks read oddly, truncated, twin rows; complete_map 5/A10 blanks one edge twice;
     no activity judges yet; prompts written by O, never reviewed by F.
  5. **Concept maps**: DONE 2026-11-13 (agent, commit 0965ba9): key-concepts view (~20) by default, "all N, by part"
     view, focus mode, course map as a lecture overview by week/topic with prerequisite arcs, concept explorer
     (screenshots `analysis/mvp/maps/`). Left: hub concepts (~40 links) crowded when selected in the full view; long
     by-part pages for the biggest lectures; the card can overlap the question drawer; overview arcs cross topic titles
     in row 1; touch and keyboard-only use untested.
  6. **QA**: "not covered" answers take ~20 s; multi-concept comparisons up to ~19 s; prerequisite lists include odd
     items (lecture 16: "HMDs: displays from the 1950s", augmented virtuality; lecture 40); "where is X taught" shows two
     times (fact vs segment); a citation repeated 5x (Q09); the no-match cut-off 0.4 is a guess; raw LaTeX now shown
     plain; no scored question set yet (block 6).
  7. **2c noise**: borderline concepts ("earliest computer", "connected computer", "real time", "mouse"), `defined` set
     on mere mentions, model-coined names ("body-part tracking"); 437 `reverse`, 322 `name_not_in_facts` flags reported.
  8. **Pipeline/infra**: `checks.json` in activities only describes the last run (see `checks_demo.json`,
     `activities_ec2/`); notebook lacks the agents' updated stage 3/4 texts (D8/D9/D12 changes); embeddings on CPU are
     too slow (use GPU); 0a leaves null times at cuts inside a cue (4d now tolerates them); `pkill -f` matches own shell.
  9. **Demo setup** never run on a real instance (llama.cpp build with the instance's CUDA is the risk; `LLAMA_REF=master`).
  Test evidence: `analysis/mvp/test_report.md`, `analysis/mvp/showcase.md`.
- **10:05 MVP wrapped up**: testing agent's report `analysis/mvp/test_report.md` (integrity clean; quizzes and open
  questions strong; match pairs, recall and review cards weak because 4a is from facts; duplicates from skipped 3b; QA
  median 6.1 s, no wrong citation in 56 answers) and `analysis/mvp/showcase.md`; viewer answers now rendered as
  markdown with clickable "(lecture N, m:ss)"; `DEMO_PLAN.md` rewritten from the showcase (lectures 4, 23, 30, 36).
  Next when the user returns: the demo instance setup (they start it; `pipeline/demo/README.md`), then 3b + model 4a
  on a faster instance, then the blocks' tests.
- **09:20 MVP RUN COMPLETE**: 1,208 activities, all kinds in all 63 lectures (37 retried, 5 unresolved); everything
  copied home from the EC2 (partial 3b answers in `stage_3_registry/llm/`, queue and logs in `output/logs/ec2/`); the
  user released the instance. **Demo setup merged**: `pipeline/demo/setup_demo.sh` (llama.cpp Gemma 4 12B, embedder,
  viewer in tmux, warm-up), `check_demo.sh`, `README.md`, `configs/gemma4_12b_demo.json`, `QA_CONFIG` in qa, YouTube
  fallback in the viewer when a video file is missing; dry-run tested only (the first real instance run is pending).
  A testing agent (Opus) checks all 63 lectures and QA and writes `analysis/mvp/test_report.md`, `analysis/mvp/showcase.md`;
  then O rewrites `pipeline/continue/DEMO_PLAN.md` from them. Notebook sections for stage 5, qa, viewer, the MVP run added.
- **09:02 user: pause the merge, release the instance at ~09:30, demo later on a similar instance.** 3b stopped on the
  EC2 (job 8 killed; 9 answers cached in the EC2's stage_3_registry/llm). Wave 2 finishing (Qwen half done 470/470,
  Gemma ~09:15, merge ~09:20). Then: copy everything from the EC2 home (stage_3_registry/llm, queue/, output/logs/ ->
  pipeline/output/logs/ec2/), commit; the user releases the instance. An Opus agent writes `pipeline/demo/setup_demo.sh`,
  `check_demo.sh`, `README.md`, `configs/gemma4_12b_demo.json`, `QA_CONFIG` env in qa, YouTube fallback in the viewer
  when a video file is missing. After: test all 63 lectures, QA re-test, rewrite DEMO_PLAN.md.
- (superseded) **08:50 plan (user: "once all is done, test and update demo; it should be more impressive"):** wave 2 merges ~09:20
  -> test all 63 lectures (contract, read later lectures' quizzes/recaps/crosswords/open questions), viewer pages, QA
  re-test with the GPU free (latency, cross-lecture, learning paths, misspellings) -> rewrite DEMO_PLAN.md around the best
  real items across the course. 3b queued as EC2 job 8 (runs after job 7, ~09:00-10:30; writes only on the EC2); the
  rebuild into the MVP waits for the user's OK.
- **Deferred by the user (08:35): the synonym merge (3b).** Cost now: e.g. "headset" C0005, "head-mounted display"
  C0040, "virtual reality headset" C0222, "VR headset" C0077 (also breaks D8; `acronym_in_name` is report-only) are
  separate concepts. Plan when asked: 3b on the EC2 (425 clusters, ~1.5 h, partial answers cached) -> 3c (without
  --no-model) -> 4a --from-facts -> 4b (mostly cached) -> 4c -> 4d -> remap the activities' concept IDs old -> new via
  segment concepts (code) -> rerun the code-made kinds. Keep the MVP until the rebuilt layer is verified.
- **07:25 MVP READY** (the user's 08:30 deadline met): knowledge layer for all 63 lectures (2,006 facts, 3,384 concepts,
  7,479 relationships, 7 course goals, 127 objectives), activities: all kinds in lectures 1-8, 16 (147); code-made kinds
  (recall, concept_map, complete_map, match_pairs) in every lecture (363 activities); QA verified on 8 questions (see
  `pipeline/continue/DEMO_PLAN.md`, written for the user's staged demo). Quality pass: activities good; weak spots: masked
  match-pair definitions read awkwardly, some crossword clues use far-away facts. 4d fixed for null sentence times.
  Wave 2 (model activities for 9-63) still running in tmux `mvp` (EC2 job 7 + local Gemma), est. 09:35-10:00; its merge
  rebuilds those lectures' files with all kinds. After the MVP: 3b (synonym merges), real 4a definitions, notebook
  sections for stages 3, 4, 5, qa, viewer (agents' texts are in their commit messages/docstrings), block 1 resumes
  (review 1 CHANGES 8-13; `compare.py` STAGE_CACHE now points at the moved 2b folder), then blocks 2-9 tests.
- **06:23: 3b skipped** (425 clusters = ~1.5 h of Qwen): `s3c_registry.py --no-model` builds the registry from 3a's exact
  merges (3,384 concepts, 7,479 relations; HMD/headset-type synonyms stay apart; run 3b later, its partial answers are in
  the EC2's stage_3_registry/llm). EC2 queue line 4 is a no-op. 3a and 4d now embed on the local GPU (the CPU took 90 s
  per batch). 2c: 5,805 segment concepts, 7,502 relations, no unresolved. New est.: 4b ~06:45, 4d ~06:50, demo activities
  ~07:30, the rest after.
- **04:50: now `mvp_run2.sh`** (tmux `mvp`): 2c turn 2 ran slow (2c lands ~06:20), so the activities run in two waves:
  demo lectures 1-8, 16 first (EC2 job 6 + local Gemma), then the rest (EC2 job 7 + local). Est.: 3b ~07:00, 4b ~07:20,
  4d ~07:25, demo activities ~07:50, the rest after 08:30 (the user: whatever exists at 08:30 is final).
- (older) **mvp_run.sh drives the rest** (user, 02:28 IST: embeddings on the local 14900K CPU, local GPU for Gemma 4 12B
  (simple activities), Qwen on the EC2 for complex ones, thinking on everywhere, save each stage at once). Local tmux
  session `mvp` runs `pipeline/mvp_run.sh`: waits for EC2 job 3 (2c) -> pulls -> 3a local CPU -> EC2 job 4 (3b) -> 3c,
  4a --from-facts local -> EC2 job 5 (4b) -> 4c, 4d local CPU -> activities: EC2 job 6 (quiz, open_question,
  odd_one_out, put_in_order on Qwen) while recap, crossword run locally on Gemma 4 12B (`--out activities_local`) ->
  merge (local cache joined, local run adds simple + code kinds) -> `--check`. Commits and pushes after each stage.
  Log `pipeline/output/logs/mvp_run.log`; done steps marked in `output/logs/mvp/` (rerun skips them). On a failure it
  stops: fix, rerun `tmux new -d -s mvp 'bash pipeline/mvp_run.sh'`. The EC2 queue was cut to lines 1-3; the script
  appends 4-6. The activities mapping awaits the user's confirmation (asked 02:30).
  New schedule: 2c ~04:50, 3a ~04:55, 3b ~05:40, 3c/4a ~05:45, 4b ~06:00, 4c/4d ~06:05, activities ~08:00 (EC2 kinds
  ~07:35, local Gemma kinds ~07:55), merged ~08:00.
- (Superseded) **Schedule (IST, set 02:25)**: 2c ~04:50 -> 3a ~05:05 -> 3b ~05:45 -> 3c, 4a (from facts) ~05:50 -> 4b ~06:10 -> 4c, 4d
  ~06:20 -> activities: ~09:10 at 6k thinking, ~07:00 without thinking. Then merge, viewer check (~30 min).
- (Superseded) **EC2 queue now**: 2 2b (running) / 3 2c / 4 3a / 5 3b / 6 3c / 7 4a --from-facts / 8 4b / 9 4c / 10 4d / 11 activities
  (6k). Estimated end ~10:45 IST at 6k; ~08:30 if the activities run without thinking (the user has not answered yet;
  to switch, edit line 11 on the EC2 before it starts: a config copy with `"thinking": false`).
- (Superseded) Pending the user's answer (asked 02:25 IST): skip 4a's model calls (a code-only `definitions.json` from each
  concept's first defining fact, so 4d and the viewer still work) and run the activities without thinking, to finish
  ~08:30; the user asked whether all can finish by 07:00 (no: ~10:45 without 4a at 6k everywhere).
- Then: run the viewer on the real `knowledge/` + `activities/`, check every page and activity kind, a few questions.

## Open questions for the user (also in the decisions file)

D11 (redefined concepts in links), D8 product/acronym names, D12 "check all outputs" incl. rejudging rewrites (D2),
D13 approvals (judge answer fields, majority of three as fallback, D1 narrowed, a look at the 14 gold labels),
`mixed` field in `concept_same.txt`; still open from before: D1, D2, D3, D4, D5, D6, D10.
