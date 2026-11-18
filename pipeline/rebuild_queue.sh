#!/usr/bin/env bash
# Queue the stages the MVP skipped on the EC2 (2026-11-15, "complete the MVP"): 3b (synonym merge) -> 3c with the
# model's groups -> real 4a definitions -> 4b -> 4c -> 4d. Run from the local PC after the EC2 setup and the queue
# are up (ec2.md, continue/PROMPT.md). The activities job is appended separately, once the reviewed activity prompts
# and checks are merged and rsynced:
#   ssh -o ClearAllForwardings=yes mtp "echo 'qwen python3 -u scripts/s5_activities.py nptel_vr --llm CFG' >> pipeline/queue/jobs.txt"
#
#   bash pipeline/rebuild_queue.sh configs/qwen38_27b_vllm_6k.json
#
# The rebuild writes into the EC2's copy of output/nptel_vr; the local MVP (git tag mvp-2026-11-13) stays until the
# rebuilt layer is checked and merged home. 4d needs no model: every fact embedding is in its cache.
set -euo pipefail
CFG=${1:?usage: rebuild_queue.sh <llm config, relative to pipeline/>}
SSH=(ssh -o ClearAllForwardings=yes -o ConnectTimeout=20)
jobs=(
  "qwen python3 -u scripts/s3b_same.py nptel_vr --llm $CFG"
  "none python3 -u scripts/s3c_registry.py nptel_vr"
  "qwen python3 -u scripts/s4a_definitions.py nptel_vr --llm $CFG"
  "qwen python3 -u scripts/s4b_goals.py nptel_vr --llm $CFG"
  "none python3 -u scripts/s4c_lecture_graph.py nptel_vr"
  "none python3 -u scripts/s4d_assemble.py nptel_vr"
)
for j in "${jobs[@]}"; do
  "${SSH[@]}" mtp "grep -qxF '$j' pipeline/queue/jobs.txt 2>/dev/null || echo '$j' >> pipeline/queue/jobs.txt"
  echo "queued: $j"
done
