#!/usr/bin/env bash
# Run pipeline jobs on the EC2 one after another, each with the model server it needs, without the local session.
#
#   tmux new -d -s queue 'bash ~/pipeline/ec2_queue.sh'      # on the EC2, from ~/pipeline (see ec2.md)
#
# Jobs:  queue/jobs.txt, one per line: "<server> <command>", server = qwen | sage | none; the command runs in
#        ~/pipeline with bash. Lines starting with # are skipped. Lines may be appended while the queue runs.
# Done:  queue/done.txt, one line per job run: line number, exit code, finish time (UTC), the job.
# Logs:  queue/logs/<line>.log per job; queue/queue.log for the queue itself.
# A job that fails stops the queue (later jobs may build on it): fix it, then `touch queue/resume` to go on with
# the next line, or `touch queue/retry` to run the failed line again.
# The server a job needs is started with scripts/llm/serve.py in a tmux session named after it (qwen, sage); the other
# one is stopped first (each takes 92% of the GPU). The stages attach to it and wait while it loads (attach_wait_s).
# When the queue is empty it checks for new lines every minute and leaves the server running.
set -u
cd "$(dirname "$0")"
Q=queue
mkdir -p "$Q/logs" output/logs
touch "$Q/jobs.txt" "$Q/done.txt"
declare -A CFG=([qwen]=configs/qwen38_27b_vllm.json [sage]=configs/sage_a15_vllm.json)

say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$Q/queue.log"; }

ensure() {                      # the server a job needs is running, and the other one is not
  local want=$1 s
  [ "$want" = none ] && return 0
  [ -n "${CFG[$want]:-}" ] || { say "unknown server '$want'"; return 1; }
  for s in "${!CFG[@]}"; do
    if [ "$s" != "$want" ] && tmux has-session -t "$s" 2>/dev/null; then
      say "stopping $s"
      tmux send-keys -t "$s" C-c
      while tmux has-session -t "$s" 2>/dev/null; do sleep 2; done
    fi
  done
  if ! tmux has-session -t "$want" 2>/dev/null; then
    say "starting $want (${CFG[$want]})"
    tmux new -d -s "$want" "python3 -m scripts.llm.serve ${CFG[$want]} 2>&1 | tee -a output/logs/serve_$want.log"
  fi
}

say "queue started"
k=$(( $(wc -l < "$Q/done.txt") + 1 ))     # resume after the last job run
while true; do
  line=$(sed -n "${k}p" "$Q/jobs.txt")
  if [ -z "$line" ]; then sleep 60; continue; fi
  if [[ "$line" == \#* ]]; then echo "$k	skip	$(date -u +%FT%TZ)	$line" >> "$Q/done.txt"; k=$((k + 1)); continue; fi
  server=${line%% *}; cmd=${line#* }
  ensure "$server" || exit 1
  say "start $k [$server]: $cmd"
  t0=$(date +%s)
  bash -c "$cmd" > "$Q/logs/$k.log" 2>&1
  rc=$?
  echo "$k	$rc	$(date -u +%FT%TZ)	$line" >> "$Q/done.txt"
  say "end $k: exit $rc after $(( $(date +%s) - t0 )) s"
  if [ "$rc" -ne 0 ]; then
    say "job $k failed: the queue waits (touch $Q/resume to skip it, $Q/retry to run it again)"
    while [ ! -e "$Q/resume" ] && [ ! -e "$Q/retry" ]; do sleep 30; done
    if [ -e "$Q/retry" ]; then rm -f "$Q/retry"; sed -i '$d' "$Q/done.txt"; say "retrying $k"; continue; fi
    rm -f "$Q/resume"; say "skipping $k"
  fi
  k=$((k + 1))
done
