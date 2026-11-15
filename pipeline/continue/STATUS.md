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
