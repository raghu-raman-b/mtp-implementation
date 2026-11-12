#!/usr/bin/env bash
# The MVP run from 2c on, driven from the local PC (2026-11-13): model stages on the EC2 queue (Qwen), embeddings on
# the local CPU, simple activities on the local GPU (Gemma 4 12B), every stage copied home, committed and pushed as soon
# as it lands (the EC2 is a spot instance).
#
#   tmux new -d -s mvp 'bash ~/Documents/mtp-implementation/pipeline/mvp_run.sh'
#   log: pipeline/output/logs/mvp_run.log; a step that is done is skipped on a rerun (marker files in output/logs/mvp/)
#
# EC2 queue (pipeline/queue/jobs.txt on the EC2) at the start: line 1 pip, 2 2b pass-through, 3 2c (running).
# This script appends: 4 3b, 5 4b, 6 activities (Qwen kinds). A failed step stops the script (fix, rerun: done steps
# are skipped).
set -uo pipefail
R=/home/prex_san/Documents/mtp-implementation
P=$R/pipeline
O=$P/output/nptel_vr
PY=$R/bin/python3                                    # the repo's Python (sentence-transformers, torch)
M=$P/output/logs/mvp; mkdir -p "$M"
LOG=$P/output/logs/mvp_run.log
SSH=(ssh -o ClearAllForwardings=yes -o ConnectTimeout=20 -o ServerAliveInterval=30)
RSH="ssh -o ClearAllForwardings=yes -o ConnectTimeout=20"
QWEN=configs/qwen38_27b_vllm_6k.json
GEMMA=configs/gemma4_12b_llamacpp.json
EC2_KINDS=quiz,open_question,odd_one_out,put_in_order     # the user's mapping: complex kinds on Qwen (EC2)
LOCAL_KINDS=recap,crossword                               # simple kinds on Gemma 4 12B (local GPU)

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
die() { log "FAILED: $*"; log "fix it, then rerun this script (done steps are skipped)"; exit 1; }
done_step() { [ -e "$M/$1.done" ]; }
mark() { touch "$M/$1.done"; log "step done: $1"; }
retry() { local n=0; until "$@"; do n=$((n + 1)); [ $n -ge 5 ] && return 1; sleep 30; done; }

pull() { for d in "$@"; do retry rsync -a -e "$RSH" "mtp:pipeline/output/nptel_vr/$d/" "$O/$d/" || die "pull $d"; done; }
push() { for d in "$@"; do retry rsync -a -e "$RSH" "$O/$d/" "mtp:pipeline/output/nptel_vr/$d/" || die "push $d"; done; }
ec2_lines() { "${SSH[@]}" mtp 'wc -l < pipeline/queue/done.txt' 2>/dev/null || echo -1; }
ec2_add() {                                    # append a job unless the queue already has that exact line
  retry "${SSH[@]}" mtp "grep -qxF '$1' pipeline/queue/jobs.txt || echo '$1' >> pipeline/queue/jobs.txt" || die "ec2_add"
}
ec2_wait() {                                   # until job line $1 has run; its exit code must be 0
  local n=$1 c
  log "waiting for EC2 job $n ($2)"
  while true; do
    c=$(ec2_lines); [ "${c:-0}" -ge "$n" ] 2>/dev/null && break
    sleep 60
  done
  local rc; rc=$("${SSH[@]}" mtp "sed -n '${n}p' pipeline/queue/done.txt | cut -f2")
  [ "$rc" = 0 ] || die "EC2 job $n ($2) exit $rc: see pipeline/queue/logs/$n.log on the EC2 (ec2_sync/queue/logs/)"
}
commit() {                                     # commit the stage outputs and the log, push (a failed push only warns)
  ( cd "$R" && git add -A pipeline/output/nptel_vr "$LOG" "$M" >/dev/null 2>&1 &&
    git commit -q -m "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >/dev/null 2>&1 ) && log "committed: $1"
  ( cd "$R" && retry git push -q ) >/dev/null 2>&1 || log "WARNING: push failed (outputs are committed locally)"
}

cd "$P" || exit 1
log "mvp_run started"

# 1. 2c (EC2 job 3) -> home
if ! done_step 2c; then
  ec2_wait 3 "2c"
  pull stage_2b_verify_facts stage_2c_concepts
  commit "MVP: 2b pass-through and 2c on all 63 lectures (EC2, Qwen 6k)"
  mark 2c
fi

# 2. 3a here (CPU embeddings), 3b on the EC2 (job 4), back
if ! done_step 3a; then
  log "3a: candidates, embeddings on the local CPU"
  CUDA_VISIBLE_DEVICES= "$PY" -u scripts/s3a_candidates.py nptel_vr --device cpu >> "$LOG" 2>&1 || die "3a"
  commit "MVP: 3a candidates (local CPU embeddings)"
  mark 3a
fi
if ! done_step 3b; then
  push stage_3_registry
  ec2_add "qwen python3 -u scripts/s3b_same.py nptel_vr --llm $QWEN"
  ec2_wait 4 "3b"
  pull stage_3_registry
  commit "MVP: 3b same-concept groups (EC2, Qwen 6k)"
  mark 3b
fi

# 3. 3c and 4a (from facts) here, 4b on the EC2 (job 5), back
if ! done_step 3c4a; then
  python3 -u scripts/s3c_registry.py nptel_vr >> "$LOG" 2>&1 || die "3c"
  python3 -u scripts/s4a_definitions.py nptel_vr --from-facts >> "$LOG" 2>&1 || die "4a"
  commit "MVP: 3c registry, 4a definitions from facts"
  mark 3c4a
fi
if ! done_step 4b; then
  push stage_3_registry stage_4a_definitions
  ec2_add "qwen python3 -u scripts/s4b_goals.py nptel_vr --llm $QWEN"
  ec2_wait 5 "4b"
  pull stage_4b_goals
  commit "MVP: 4b goals (EC2, Qwen 6k)"
  mark 4b
fi

# 4. 4c and 4d here (4d embeds the facts on the local CPU)
if ! done_step 4cd; then
  python3 -u scripts/s4c_lecture_graph.py nptel_vr >> "$LOG" 2>&1 || die "4c"
  CUDA_VISIBLE_DEVICES= "$PY" -u scripts/s4d_assemble.py nptel_vr >> "$LOG" 2>&1 || die "4d (see its checks)"
  commit "MVP: 4c lecture graph, 4d knowledge layer"
  mark 4cd
fi

# 5. activities: complex kinds on the EC2 (job 6) while the simple kinds run here on Gemma 4 12B
if ! done_step activities; then
  push knowledge stage_4a_definitions stage_4b_goals stage_4c_lecture_graph
  ec2_add "qwen python3 -u scripts/s5_activities.py nptel_vr --llm $QWEN --kinds $EC2_KINDS"
  if ! done_step activities_local; then
    log "activities ($LOCAL_KINDS) on Gemma 4 12B, local GPU"
    python3 -u scripts/s5_activities.py nptel_vr --llm "$GEMMA" --kinds "$LOCAL_KINDS" \
      --out "$O/activities_local" >> "$LOG" 2>&1 || die "local activities"
    commit "MVP: activities $LOCAL_KINDS (local, Gemma 4 12B)"
    mark activities_local
  fi
  ec2_wait 6 "activities on Qwen"
  pull activities
  commit "MVP: activities $EC2_KINDS (EC2, Qwen 6k)"
  # one folder: the local answers join the cache, then a local run adds the simple and code-made kinds to the EC2's
  cat "$O/activities_local/llm/cache.jsonl" >> "$O/activities/llm/cache.jsonl"
  cat "$O/activities_local/llm/calls.jsonl" >> "$O/activities/llm/calls.jsonl" 2>/dev/null
  ALL_OTHER=$(python3 -c "
import sys; sys.path.insert(0, '.')
from scripts.s5_activities import KINDS
print(','.join(k for k in KINDS if k not in '$EC2_KINDS'.split(',')))")
  python3 -u scripts/s5_activities.py nptel_vr --llm "$GEMMA" --kinds "$ALL_OTHER" >> "$LOG" 2>&1 || die "activities merge"
  python3 -u scripts/s5_activities.py nptel_vr --check >> "$LOG" 2>&1 || log "WARNING: activities --check found problems"
  commit "MVP: all activities (complex on Qwen, simple on Gemma 4 12B, the rest by code)"
  mark activities
fi
log "MVP RUN COMPLETE: knowledge/ and activities/ for all 63 lectures are in pipeline/output/nptel_vr/"
