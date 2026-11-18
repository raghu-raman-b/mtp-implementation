#!/usr/bin/env bash
# Live progress of the pipeline v3 runs.
#   bash progress.sh          tmux session "mtp" (attach: tmux attach -t mtp): status + logs, EC2 server logs, and the
#                             sync loop that copies the EC2's output/ and queue/ into ec2_sync/ every 5 minutes
#   bash progress.sh view     the one-screen view only (what watch shows)
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO=/home/prex_san/Documents/mtp-implementation
LOGS=$REPO/pipeline/output/logs
STATUS=$HERE/STATUS.md

view() {
  cat "$STATUS"
  echo; echo "== 2b (block 0 item 5): $LOGS/facts_fresh_2b.log"
  tail -n 6 "$LOGS/facts_fresh_2b.log" 2>/dev/null | cut -c1-150
  for r in base seed1 seed2; do
    f=$LOGS/judge_test_$r.log
    [ -f "$f" ] || continue
    echo; echo "== judge test $r: $(grep -c '✓\|·' "$f") calls answered"
    tail -n 2 "$f" | cut -c1-150
  done
  echo; echo "== answers cached: 2b $(wc -l < $REPO/pipeline/output/nptel_vr/stage_2b_verify_facts/llm/cache.jsonl 2>/dev/null || echo 0)," \
       "judge tests $(wc -l < $REPO/analysis/fact_judge/llm/cache.jsonl 2>/dev/null || echo 0)"
  echo "== runs saved: $(ls $REPO/analysis/fact_judge/runs 2>/dev/null | tr '\n' ' ')"
  echo; echo "== EC2 queue (copied home every 5 min into ec2_sync/; live: ssh mtp tail -f pipeline/queue/queue.log)"
  tail -n 4 $REPO/ec2_sync/queue/queue.log 2>/dev/null | cut -c1-150
  last=$(ls -t $REPO/ec2_sync/queue/logs/*.log 2>/dev/null | head -1)
  [ -n "$last" ] && { echo "-- $(basename $last):"; tail -n 3 "$last" | cut -c1-150; }
}

if [ "${1:-}" = view ]; then view; exit; fi
if ! command -v tmux >/dev/null; then
  echo "tmux is not installed (sudo dnf install tmux); showing the watch view instead"; sleep 2
  export -f view; export STATUS LOGS REPO
  exec watch -n 5 -t bash "$0" view
fi
tmux kill-session -t mtp 2>/dev/null
tmux new-session -d -s mtp -n now "watch -n 5 -t bash '$0' view"
tmux split-window -t mtp:now -h "tail -F $LOGS/facts_fresh_2b.log"
tmux split-window -t mtp:now.1 -v "tail -F $LOGS/judge_test_base.log $LOGS/judge_test_seed1.log $LOGS/judge_test_seed2.log"
tmux new-window -t mtp -n ec2 "ssh -o ClearAllForwardings=yes -t mtp 'tail -F pipeline/output/logs/llm_server_8095.log pipeline/output/logs/llm_server_8094.log'"
tmux split-window -t mtp:ec2 -v -l 8 "ssh -o ClearAllForwardings=yes -t mtp 'watch -n 5 \"nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv; tmux ls\"'"
tmux new-window -t mtp -n sync "while true; do rsync -a -e 'ssh -o ClearAllForwardings=yes -o ConnectTimeout=20' mtp:pipeline/output/ $REPO/ec2_sync/output/ && rsync -a -e 'ssh -o ClearAllForwardings=yes -o ConnectTimeout=20' mtp:pipeline/queue/ $REPO/ec2_sync/queue/ && echo \"\$(date +%T) synced: \$(tail -1 $REPO/ec2_sync/queue/queue.log)\"; sleep 300; done"
tmux select-window -t mtp:now
echo "tmux session mtp: tmux attach -t mtp   (window 'now': status + local logs; window 'ec2': server logs and GPU)"
