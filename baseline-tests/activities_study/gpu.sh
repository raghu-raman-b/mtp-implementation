#!/bin/bash
# Every GPU step of the activities study, then the CPU steps. Rerunnable: answers are cached by request hash
# (out/llm/cache.jsonl), so a rerun sends only what is missing. The model server: the client attaches to the
# llama-server of pipeline/configs/gemma4_12b_llamacpp.json (port 8092), or starts it when none answers.
# GPU lock: each GPU step runs under `flock baseline-tests/gpu.lock`, unless this script already runs under it
# (the queue: `flock gpu.lock bash activities_study/gpu.sh`; taking it again would wait forever).
set -x
cd "$(dirname "$0")"
LOCK=../gpu.lock
exec > >(tee -a gpu.log) 2>&1
if [ -z "$ACT_GPU_LOCKED" ] && ps -o args= -p "$PPID" | grep -q "flock.*gpu.lock"; then ACT_GPU_LOCKED=1; fi
gpu() { if [ -n "$ACT_GPU_LOCKED" ]; then "$@"; else flock "$LOCK" "$@"; fi; }
date
gpu python3 generate.py || exit 1        # B1 and B2: 6 lectures x 7 kinds each
gpu python3 judge_gemma.py || exit 1     # pipeline judges (Gemma) on ours, B1, B2
python3 checks.py && python3 packets.py && python3 summarize.py || exit 1
date
echo ACT_STUDY_GPU_DONE
