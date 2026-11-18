#!/usr/bin/env bash
# Get a fresh GPU instance (EC2, Ubuntu + NVIDIA driver + CUDA toolkit) ready to serve the pipeline's models.
# The pipeline itself runs on the local PC and reaches the servers through an SSH port forward (see ec2.md).
# Safe to rerun: every step skips what is already done.
#
#   bash setup_ec2.sh                  # vLLM, Qwen 3.8 27B FP8, Sage-A1.5 FP8, the embedding model, smoke test
#   SKIP_MODEL=1 bash setup_ec2.sh     # no model downloads (and no smoke test)
#   SMOKE=sage bash setup_ec2.sh       # smoke-test the judge instead of the writer; SMOKE=none: no smoke test
#   HF_TOKEN=... bash setup_ec2.sh     # Hugging Face token; without it the script reads .hf_token next to it (gitignored)
#   NO_NVME=1 bash setup_ec2.sh        # keep the model cache on the EBS root volume (survives a stop; loads ~10x slower)
#   EMBED_MODELS="a b" bash setup_ec2.sh   # other embedding models (block 3 compares several)
#
# Expects to sit in ~/pipeline next to scripts/llm/ and configs/ (copied from the local PC, see ec2.md).
#
# What it does:
#   1. checks the GPU; puts the Hugging Face cache (~/.cache/huggingface) on the local NVMe (/opt/dlami/nvme) when the
#      instance has one (wiped on a stop: rerun the script after a start); saves the Hugging Face token (if any)
#   2. starts the model downloads in the background (into the Hugging Face cache)
#   3. system tools: ninja-build (vLLM compiles kernels on its first start), tmux (servers run in tmux sessions)
#   4. vLLM in its own venv (~/vllm-venv; it pins its own torch), the binary the configs name
#   5. waits for the downloads, then the smoke test: starts one model server from its config, sends one request,
#      stops it (scripts/llm/serve.py --smoke)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VLLM_MODELS="${VLLM_MODELS:-Qwen/Qwen3.8-27B-FP8 InternScience/Sage-A1.5-FP8}"
EMBED_MODELS="${EMBED_MODELS:-Qwen/Qwen3-Embedding-0.6B}"
VLLM_DIR="${VLLM_DIR:-$HOME/vllm-venv}"
VLLM_VERSION="${VLLM_VERSION:-0.32.0}"
HF_VENV="${HF_VENV:-$HOME/hf-venv}"               # a small venv with huggingface_hub, for the downloads
NVME="${NVME:-/opt/dlami/nvme}"                   # the instance's local NVMe (instance store), for the model cache
SMOKE="${SMOKE:-qwen}"                            # qwen, sage or none
export PATH="/usr/local/cuda/bin:$PATH"
LOG="$HERE/output/logs"; mkdir -p "$LOG"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

step "1/5 GPU and model cache"
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader
# The Hugging Face cache goes on the instance's local NVMe when it has one (the Deep Learning AMI mounts it at
# /opt/dlami/nvme): the EBS root volume reads at ~125 MB/s (gp3 default), so vLLM spends ~4 min loading a 30 GB model
# from it, every time, since two models do not fit in the page cache together; the NVMe reads at GB/s.
# ~/.cache/huggingface becomes a link to it, so every tool finds the models where it always does. Instance store is
# wiped when the instance stops: after a stop and start, rerun this script (it downloads the models again).
HF_DIR="$HOME/.cache/huggingface"
if [ -z "${NO_NVME:-}" ] && mountpoint -q "$NVME" 2>/dev/null && [ -w "$NVME" ]; then
  if [ "$(readlink -f "$HF_DIR")" != "$NVME/huggingface" ]; then
    mkdir -p "$NVME/huggingface"
    if [ -d "$HF_DIR" ] && [ ! -L "$HF_DIR" ]; then         # an existing cache on EBS: move it over first
      rsync -a "$HF_DIR/" "$NVME/huggingface/" && rm -rf "$HF_DIR"
    fi
    rm -f "$HF_DIR"; mkdir -p "$(dirname "$HF_DIR")"; ln -s "$NVME/huggingface" "$HF_DIR"
  fi
  mkdir -p "$NVME/huggingface"                              # a link left from before a stop: the folder is gone
  echo "  Hugging Face cache: $HF_DIR -> $NVME/huggingface (local NVMe, $(df -h --output=avail "$NVME" | tail -1 | tr -d ' ') free)"
else
  echo "  Hugging Face cache: $HF_DIR (EBS; no local NVMe at $NVME)"
fi
[ -z "${HF_TOKEN:-}" ] && [ -f "$HERE/.hf_token" ] && HF_TOKEN="$(tr -d '[:space:]' < "$HERE/.hf_token")"
if [ -n "${HF_TOKEN:-}" ]; then
  export HF_TOKEN
  mkdir -p "$HOME/.cache/huggingface" && (umask 077; printf '%s' "$HF_TOKEN" > "$HOME/.cache/huggingface/token")
  echo "  Hugging Face token: set"
else
  echo "  Hugging Face token: none (slower downloads)"
fi

step "2/5 model downloads (background, log: output/logs/setup_download.log)"
DL_PID=""
if [ -z "${SKIP_MODEL:-}" ]; then
  [ -d "$HF_VENV" ] || python3 -m venv "$HF_VENV"
  "$HF_VENV/bin/pip" install -q --upgrade pip huggingface_hub
  "$HF_VENV/bin/python" - $VLLM_MODELS $EMBED_MODELS > "$LOG/setup_download.log" 2>&1 <<'EOF' &
import sys
from huggingface_hub import snapshot_download
for m in sys.argv[1:]:
    print(m, "->", snapshot_download(m), flush=True)
print("done")
EOF
  DL_PID=$!
  echo "  $VLLM_MODELS $EMBED_MODELS (pid $DL_PID)"
fi

step "3/5 system tools"
missing=""
command -v ninja >/dev/null || missing="$missing ninja-build"
command -v tmux  >/dev/null || missing="$missing tmux"
if [ -n "$missing" ]; then
  sudo apt-get update -qq && sudo apt-get install -y -qq $missing || echo "  apt install of$missing failed"
fi
echo "  ninja $(ninja --version 2>/dev/null || echo missing), tmux $(tmux -V 2>/dev/null || echo missing)"

step "4/5 vLLM $VLLM_VERSION"
[ -d "$VLLM_DIR" ] || python3 -m venv "$VLLM_DIR"
"$VLLM_DIR/bin/python" -c "import vllm" 2>/dev/null || {
  "$VLLM_DIR/bin/pip" install -q --upgrade pip && "$VLLM_DIR/bin/pip" install -q "vllm==$VLLM_VERSION"; }
"$VLLM_DIR/bin/pip" install -q ninja        # also in the venv: vLLM finds it there when started by serve.py
"$VLLM_DIR/bin/python" -c "import vllm, torch; print('  vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())"

step "5/5 downloads and smoke test"
if [ -n "$DL_PID" ]; then
  echo "  waiting for the downloads..."
  wait "$DL_PID" || { echo "  download failed: see output/logs/setup_download.log"; exit 1; }
  sed 's/^/  /' "$LOG/setup_download.log" | grep -v Warning
fi
case "$SMOKE" in
  qwen) SMOKE_CFG=configs/qwen38_27b_vllm.json ;;
  sage) SMOKE_CFG=configs/sage_a15_vllm.json ;;
  *)    SMOKE_CFG="" ;;
esac
if [ -n "$SMOKE_CFG" ] && [ -z "${SKIP_MODEL:-}" ]; then
  echo "  starting $SMOKE_CFG for one request (a few minutes: model load and vLLM's compile step)"
  (cd "$HERE" && python3 -m scripts.llm.serve "$SMOKE_CFG" --smoke) || { echo "  smoke test failed"; exit 1; }
else
  echo "  skipped"
fi

echo
echo "Ready. Start a server in tmux (one at a time takes the whole GPU), e.g.:"
echo "  tmux new -d -s qwen 'cd $HERE && python3 -m scripts.llm.serve configs/qwen38_27b_vllm.json'"
echo "then forward its port from the local PC (ec2.md)."
