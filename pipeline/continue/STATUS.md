PIPELINE v3 STATUS - MVP DAY  (updated 02:40 IST, 13 Nov; full state: pipeline/continue/PROMPT.md)

ALL MVP CODE MERGED: activities (s5), question answering (qa/, Gemma 4 12B), viewer (viewer/serve.py), 4a --from-facts
NOW
  [running] EC2 queue: 2b all 63 (26/347) -> 2c -> 3a -> 3b -> 3c -> 4a(from facts) -> 4b -> 4c -> 4d -> activities
            est. done ~10:45 IST (6k thinking), ~08:30 if activities run without thinking
NEXT
  As stages land (ec2_sync/): merge into pipeline/output/, look at the outputs, open the viewer, ask questions
VIEWER (already shows all lectures with videos and segments):  python pipeline/viewer/serve.py nptel_vr  -> :8765
