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

In progress at the time of writing (Opus agents in worktrees; cherry-pick their commits when they report):
- Agent "2c": D8 checks, D12 retries/best answer/lost-added log, `appears` fix, prompt rules for
  `concept_extraction.txt` (4, 5) and `concept_relations.txt` (5).
- Agent "3/4ab": s3b name rule (D8), s3a `--embed-facts` (D9) + embed_compare metrics, 4a/4b checks and retries (D12),
  `concept_definition.txt`, `course_goals.txt`, `lecture_goals.txt`, `concept_same.txt` (without `mixed`), 4c list of
  all-`redefined` links.
- EC2: the user said they are starting it; `ssh mtp` still timed out at 01:10 (if the public IP changed, the HostName
  in `~/.ssh/config` must be updated). After it is up: rsync + `setup_ec2.sh` + queue (see "How things run").

## Open questions for the user (also in the decisions file)

D11 (redefined concepts in links), D8 product/acronym names, D12 "check all outputs" incl. rejudging rewrites (D2),
D13 approvals (judge answer fields, majority of three as fallback, D1 narrowed, a look at the 14 gold labels),
`mixed` field in `concept_same.txt`; still open from before: D1, D2, D3, D4, D5, D6, D10.
