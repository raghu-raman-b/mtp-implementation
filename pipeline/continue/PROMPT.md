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

## State (updated 2026-11-13 00:55 IST)

Done and pushed (see `git log`):
- **Block 0** complete. Fresh 2b on lectures 1, 4, 16: 62 facts in, 54 kept, 7 rewritten, 1 removed, 62 out.
- **Block 1**: `analysis/fact_judge/compare.py` (judge vs gold, seeded, flips, rejudge, code checks), runs `base`,
  `seed1`, `seed2`, `old_1112`, `rejudge` (all in `analysis/fact_judge/runs/`); report draft
  `analysis/fact_judge/report.md`. Gate as proposed: seeded 94% (met), false alarms 7% judge / 13% with code checks,
  flips 15% (not met); the judge catches 0-1 of 7 real gold failures; 2 of 8 rewrites still fail when rejudged.
  Open box: "Report with proposed changes; F revises fact_judge.txt; rerun; before and after", and the gate.
- **Block 2**: `s2c_concepts.py` + checks (fake-tested). A trial on real facts: `analysis/concepts/data/trial_fresh_2b/`.
- **Block 3**: `embed.py`, `s3a/s3b/s3c` (fake-tested, 42 checks), `analysis/registry/embed_compare.py` (waits for
  F's `analysis/registry/pairs.json`).
- **Block 4**: `s4a`, `s4b`, `s4c`, `s4d` + `schemas/knowledge.schema.json` (fake-tested, 66 checks).
- **2a on all 63 lectures** (EC2 queue, ahead of block 5): 2006 facts in `stage_2a_fact_extraction/`.
- Decisions D8-D13 added to PLAN.md; the user answered D8, D9, D11, D12, D13 (see
  `analysis/decisions/fable_review_2026-11-13.md`, Fable's review with exact prompt fixes and implementation notes).

In progress at the time of writing:
- `block-reviewer` on block 1 (report `analysis/fact_judge/report.md`), resumed after a usage-limit stop. Its CHANGES
  (judge prompt revision) are to be applied exactly; reconcile with Fable's `fact_judge.txt` fixes in the decisions
  file (the reviewer's CHANGES win for the gate; the judge answer-format change waits for the user, question 4).
- Implementing the shared pieces of the user's decisions (O): in `scripts/llm/client.py` keep the attempt with the
  fewest problems when all retries fail (`res.parsed` set, `res.ok` false) and the new FEEDBACK text; one
  `is_acronym` helper in `scripts/fact_checks.py`; the `appears` fix in `s2c_concepts.py` (apostrophes, "X (Y) Z").
- EC2: stopped; the user is starting it (2026-11-13 ~00:50 IST). Nothing queued yet.

## Next (in order)

1. Finish the shared pieces above; run `tests/fake_run.py`, `fake_registry.py`, `fake_knowledge.py`; commit, push.
2. Spawn Opus agents for the rest of the decisions (worktrees): (a) 2c: D8 checks (`name_is_acronym` retry,
   `acronym_in_name` report), D12 retries and "lost/added" logging, prompt fixes for `concept_extraction.txt` rule 4/5
   and `concept_relations.txt` rule 5; (b) stage 3: D8 name rule in s3b, D9 `--embed-facts` options + embed_compare
   metrics; 4a/4b: D12 checks and retries, prompt fixes for `concept_definition.txt`, `course_goals.txt`,
   `lecture_goals.txt` and their O notes. Items needing the user's answer (questions 1-5 in the decisions file) keep
   the current behaviour until answered.
3. When the EC2 is up: setup, queue. Block 1 rerun after the reviewer's prompt revision: the judge `base`, `seed1`,
   `seed2` with `--seeded` (queue with `sage`, run `compare.py` on the EC2 or locally from synced caches), then 2b on
   lectures 1, 4, 16 with the revised judge (copy the current `stage_2b_verify_facts/` to
   `analysis/fact_extraction/data/history/` first), the report before/after, `block-reviewer` again, gate.
4. Block 2 on the new 2b facts: 2c twice (`--seed 1 --out` for the second), report; F's gold for 4 segments.

## Open questions for the user (also in the decisions file)

D11 (redefined concepts in links), D8 product/acronym names, D12 "check all outputs" incl. rejudging rewrites (D2),
D13 approvals (judge answer fields, majority of three as fallback, D1 narrowed, a look at the 14 gold labels),
`mixed` field in `concept_same.txt`; still open from before: D1, D2, D3, D4, D5, D6, D10.
