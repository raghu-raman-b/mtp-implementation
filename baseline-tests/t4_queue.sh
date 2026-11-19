#!/bin/bash
# T4: ours_v2 / ours_v2_nothink reruns (detached; resumable). Run from baseline-tests/.
cd "$(dirname "$0")"
PY=../bin/python
say() { echo "[$(date '+%H:%M:%S')] $*"; }
say "run1 start"; flock gpu.lock $PY run_systems.py ours_v2 ours_v2_nothink; say "run1 done"
for r in 2 3; do
  say "run$r start"
  flock gpu.lock $PY run_systems.py ours_v2 ours_v2_nothink --run $r --categories not_covered where prerequisite structure formula multihop
  say "run$r done"
done
say T4_DONE
