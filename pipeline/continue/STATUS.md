PIPELINE v3 STATUS - MVP DAY  (updated 02:32 IST, 13 Nov; full state: pipeline/continue/PROMPT.md)

ALL MVP CODE MERGED. Judge skipped. mvp_run.sh (tmux `mvp`) drives the rest; log pipeline/output/logs/mvp_run.log
SCHEDULE                                               ends about
  2c  concepts + relationships      EC2 Qwen 6k        04:50   <- running
  3a  candidates                    local CPU          04:55
  3b  same-concept groups           EC2 Qwen 6k        05:40
  3c, 4a (from facts)               local              05:45
  4b  goals                         EC2 Qwen 6k        06:00
  4c, 4d knowledge/                 local CPU          06:05
  activities: quiz, open questions, odd one out, put in order   EC2 Qwen     07:35
              recap, crossword clues                            local Gemma 12B  07:55
              maps, match pairs, recall, review cards           code         08:00
VIEWER:  python pipeline/viewer/serve.py nptel_vr  -> http://localhost:8765
