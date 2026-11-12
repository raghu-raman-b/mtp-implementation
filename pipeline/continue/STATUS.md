PIPELINE v3 STATUS - MVP DAY  (updated 02:05 IST, 13 Nov; full state: pipeline/continue/PROMPT.md)

NOW
  [running] EC2 queue (L40S, Qwen only): 2b all 63 -> 2c -> 3a -> 3b -> 3c -> 4a -> 4b -> 4c -> 4d
  [running] Opus agents: activities stage + prompts; question answering (Gemma 4 12B local)
  [done]    Viewer merged: python pipeline/viewer/serve.py nptel_vr  -> http://localhost:8765
NEXT
  1. Merge agents; append activities job to the EC2 queue
  2. Merge EC2 results (ec2_sync/ -> pipeline/output/), run the viewer on them, check everything
