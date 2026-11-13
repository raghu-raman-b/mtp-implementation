PIPELINE v3 STATUS - MVP  (updated 07:25 IST, 13 Nov; full state: pipeline/continue/PROMPT.md)

MVP READY. Demo plan: pipeline/continue/DEMO_PLAN.md
  Knowledge layer, all 63 lectures: 2,006 facts, 3,384 concepts, 7,479 relationships, goals, lecture graph (pushed)
  Activities: all ten kinds in lectures 1-8 and 16; maps, match pairs, recall in every lecture; 1,107 review cards
  Question answering (Gemma 4 12B): verified on 8 demo questions, cites lecture + time, refuses off-course
STILL RUNNING (tmux mvp): wave 2 model activities for lectures 9-63 (EC2 Qwen ~09:35, local Gemma ~10:00)
VIEWER:  cd pipeline && python viewer/serve.py nptel_vr  -> http://localhost:8765
