PIPELINE v3 STATUS - DEMO PREP  (updated 00:05 IST, 18 Nov; full state + decisions: pipeline/continue/PROMPT.md)

DONE: docs v3 (pipeline/docs/pipeline.html, sources docs/src/); remote-model demo setup (model on the instance, app on
  the Windows laptop; ec2_model_server.sh, python -m demo, run_demo.ps1); design mockups (3 directions) on the canvas
WAITING: user's design pick; baseline tests paused (branch worktree-agent-ac043cfbb4e8a782d, baseline-tests/STATE.md)
NEXT: design build + weak-spot fixes + part titles (Gemma 12B) in parallel -> docs update -> DEMO_PLAN -> rehearsal
DECIDED: no cards/definitions for connecting concepts (facts only); recaps = passing points; crosswords = failed words
  pre-filled; pause at segment ends with activities overlaid; no demo fallback

PIPELINE v3 STATUS - MVP REBUILT  (updated 17:20 IST, 17 Nov; full state: pipeline/continue/PROMPT.md)

DONE TODAY: layer rebuilt and merged (d3896b9): 3,122 concepts (synonym merge), real definitions (1,316 = glossary),
  goals, graph, knowledge (206,903 refs ok); activities v3 (1,168, judge-checked, failing items hidden per review)
  viewer fast (lean routes, lazy lectures, streamed answers; tunnel 9 s -> 1 s pages); QA median ~5 s, grounded
  demo setup proven on a real instance (check_demo ALL PASS); EC2 released at the user's cue (04a797a)
NEXT: DEMO_PLAN.md rewrite for the new layer (agent running), rehearsal; then docs
NOTE demo day: SSH to us-east was ~40 kB/s from the user's network: use an instance near the venue, test first
MVP as demoed before: git tag mvp-2026-11-13

PIPELINE v3 STATUS - MVP COMPLETION DAY  (updated 10:45 IST, 17 Nov; full state: pipeline/continue/PROMPT.md)

GOAL TODAY: the best working MVP; all GPU work done today. Demo runs locally first, on a cloud instance via SSH on demo day.
EC2: RTX PRO 6000 96 GB, config configs/qwen38_27b_vllm_6k_96gb.json (64 slots, hashes unchanged); queue started 10:34 IST
  jobs: 3b -> 3c -> HOLD (touch queue/go_4a) -> 4a (Fable-reviewed prompt, 716e6b5) -> 4b -> 4c -> 4d; then activities
AGENTS (Opus, existing worktrees): activities checks+judge (aedc...), QA speed + vLLM config (a5b9...), viewer speed for SSH (a761...)
ROLES: Fable reviews/decides only, until 13:30; Opus reviews after. User OK'd merging the rebuilt layer home once checks pass.
NEXT: read 3b merges; release 4a; activities trial 1,4,16 (--out trial); full activities; verify + merge home; demo setup on
  the EC2 (setup_demo.sh first real run); DEMO_PLAN rewrite; rehearse; docs (pipeline.html, final report)
MVP as demoed: git tag mvp-2026-11-13

PIPELINE v3 STATUS - COMPLETING THE MVP  (updated 13:10 IST, 15 Nov; full state: pipeline/continue/PROMPT.md)

NOW: EC2 instance being swapped by the user; then 3b -> 3c -> 4a (real) -> 4b -> 4c -> 4d -> activities (Qwen) on it
AGENTS: viewer rebuild (Opus), QA fixes (Opus), block 1 gold (Fable), activity prompts + judges (Fable),
        gold sets for blocks 6/3/2 (Fable)
MVP as demoed: git tag mvp-2026-11-13

PIPELINE v3 STATUS - MVP DONE  (updated 10:05 IST, 13 Nov; full state: pipeline/continue/PROMPT.md)

MVP COMPLETE. Demo plan: pipeline/continue/DEMO_PLAN.md (final). Demo on an instance: pipeline/demo/README.md
  Knowledge layer, 63 lectures: 2,006 facts, 3,384 concepts, 7,479 relationships, goals, lecture graph
  1,208 activities, all ten kinds in every lecture; 1,107 review cards
  Question answering (Gemma 4 12B): median 6.1 s, grounded, no wrong citation in 56 answers (analysis/mvp/)
  Viewer: answers rendered (lists, bold) with clickable (lecture N, m:ss) links
NEXT (later): 3b synonym merge, model-written definitions (4a), notebook check, block 1 resumes
