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

## State (updated 2026-11-13 01:30 IST)

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
- **Schedule (IST, set 02:25)**: 2c ~04:50 -> 3a ~05:05 -> 3b ~05:45 -> 3c, 4a (from facts) ~05:50 -> 4b ~06:10 -> 4c, 4d
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
