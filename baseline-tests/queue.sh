#!/bin/bash
# Detached GPU queue for the night of 2026-11-19 (survives the Claude session):
#   setsid nohup bash baseline-tests/queue.sh > baseline-tests/queue.log 2>&1 < /dev/null &
# Each step waits for its input, runs under the shared GPU lock, and leaves a DONE marker. Rerunnable (steps resume).
cd "$(dirname "$0")"
LOCK=gpu.lock
say() { echo "[$(date '+%H:%M:%S')] $*"; }

# 1. multihop questions (appended to questions.jsonl after review) -> all systems, repeats for ours/rag/rag_think
if [ ! -e MULTIHOP_DONE ]; then
  say "waiting for multihop questions in questions.jsonl"
  until grep -q '"category": "multihop"' questions.jsonl; do sleep 60; done
  say "multihop runs start"
  flock "$LOCK" python3 run_systems.py ours abl_facts abl_graph plain rag rag_think graphrag_text graphrag_notext \
      --categories multihop
  for r in 2 3; do flock "$LOCK" python3 run_systems.py ours rag rag_think --run $r --categories multihop; done
  touch MULTIHOP_DONE; say "multihop runs done"
fi

# 2. activities study (generation + Gemma judges), when its scripts are ready
if [ ! -e activities_study/GPU_DONE ]; then
  say "waiting for activities_study/READY"
  until [ -e activities_study/READY ]; do sleep 60; done
  say "activities study GPU start"
  flock "$LOCK" bash activities_study/gpu.sh && touch activities_study/GPU_DONE
  say "activities study GPU exit $?"
fi
say "QUEUE_DONE"
