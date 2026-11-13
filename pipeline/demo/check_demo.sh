#!/usr/bin/env bash
# Check the learner demo end to end on the instance (after setup_demo.sh): one PASS / FAIL / SKIP line per item, and
# the exit code is 1 when anything fails. It changes nothing (one question is asked, which qa logs as it logs any).
#
#   bash pipeline/demo/check_demo.sh
#   QUESTION="What is stereoscopy?" bash pipeline/demo/check_demo.sh
#   VIEWER_URL=http://127.0.0.1:8765 CONFIG=configs/gemma4_12b_demo.json VENV=~/demo-venv ...   (the defaults)
#
# Items: GPU; the venv (torch, sentence-transformers); the llama-server binary; the model file the config names; the
# embedder in the Hugging Face cache; the tmux sessions; then over HTTP (demo_tool.py check-http): the model server
# healthy and serving the config's model, the viewer's page, script, course, lecture and knowledge routes, a Range
# request on a video (or the YouTube fallback when the file is not here), and one question answered with citations.
set -uo pipefail

DEMO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPE="$(dirname "$DEMO")"
VENV="${VENV:-$HOME/demo-venv}"
CONFIG="${CONFIG:-$PIPE/configs/gemma4_12b_demo.json}"
VIEWER_URL="${VIEWER_URL:-http://127.0.0.1:${VIEWER_PORT:-8765}}"
EMBED_MODEL="${EMBED_MODEL:-Qwen/Qwen3-Embedding-0.6B}"
QUESTION="${QUESTION:-What is an HMD?}"
SESSIONS="${SESSIONS:-gemma viewer}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
FAILS=0

item() {   # item <0|1|skip> <what> [detail]
  local tag
  case "$1" in 0) tag="PASS" ;; skip) tag="SKIP" ;; *) tag="FAIL"; FAILS=$((FAILS + 1)) ;; esac
  printf '%s  %s%s\n' "$tag" "$2" "${3:+  ($3)}"
}
cfg() { python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ''))" "$CONFIG" "$1"; }

echo "Checking the demo (config $CONFIG, viewer $VIEWER_URL)"
[ -f "$CONFIG" ] || { item 1 "demo config" "$CONFIG not found"; exit 1; }

gpu="$(nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1)"
[ -n "$gpu" ]; item $? "GPU visible" "${gpu:-nvidia-smi failed}"

v="$("$PY" -c "import torch, sentence_transformers; print('torch', torch.__version__, 'sentence-transformers', sentence_transformers.__version__)" 2>&1 | tail -1)"
"$PY" -c "import torch, sentence_transformers" 2>/dev/null; item $? "Python packages ($PY)" "$v"

bin="$(cfg binary)"; bin="${bin/#\~/$HOME}"
ver="$("$bin" --version 2>&1 | grep -m1 -i version)"
[ -x "$bin" ] && [ -n "$ver" ]; item $? "llama-server binary" "$bin: ${ver:-missing or does not run}"

model="$(cfg model_path)"; model="${model/#\~/$HOME}"
[ -s "$model" ]; item $? "model file" "$model$( [ -s "$model" ] && printf ', %s' "$(du -hL "$model" | cut -f1)")"

emb="$("$PY" - "$EMBED_MODEL" 2>/dev/null <<'EOF'
import sys
from huggingface_hub import snapshot_download
print(snapshot_download(sys.argv[1], local_files_only=True))
EOF
)"
[ -n "$emb" ]; item $? "embedder in the Hugging Face cache" "${emb:-$EMBED_MODEL not downloaded}"

for s in $SESSIONS; do
  tmux has-session -t "$s" 2>/dev/null; item $? "tmux session $s"
done

tmp="$(mktemp)"
"$PY" "$DEMO/demo_tool.py" check-http "$VIEWER_URL" "$CONFIG" --question "$QUESTION" | tee "$tmp"
grep -q '^\(PASS\|FAIL\)' "$tmp" || item 1 "HTTP checks" "demo_tool.py check-http did not run"
FAILS=$((FAILS + $(grep -c '^FAIL' "$tmp" || true)))
rm -f "$tmp"

echo
if [ "$FAILS" -eq 0 ]; then
  printf '\033[1;32mALL PASS\033[0m: open %s/ (through the SSH forward)\n' "$VIEWER_URL"
else
  printf '\033[1;31m%d FAILED\033[0m (logs: %s/logs/; tmux attach -t gemma | viewer)\n' "$FAILS" "$DEMO"
fi
[ "$FAILS" -eq 0 ]
