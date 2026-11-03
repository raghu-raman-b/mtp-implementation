#!/usr/bin/env bash
# Get a fresh GPU instance (e.g. EC2 g7e, Ubuntu + NVIDIA driver + CUDA toolkit) ready to run generate_lir2.py.
# Safe to rerun: every step skips what is already done.
#
#   bash setup_ec2.sh               # vLLM + Qwen 27B FP8 (lir2_config.toml) + Gemma 4 E4B and 12B (lir2_config_small.toml)
#   LLAMA=1 bash setup_ec2.sh       # also llama.cpp + the Q8 GGUF (slower on this model; ~20 min more to build)
#   SKIP_MODEL=1 bash setup_ec2.sh  # no model downloads
#   HF_TOKEN=... bash setup_ec2.sh  # faster Hugging Face downloads
#
# What it does:
#   1. checks the GPU
#   2. starts the model downloads in the background (Hugging Face cache, ~/.cache/huggingface; survives a stop)
#   3. system tools: ffmpeg (videos), ninja-build (vLLM compiles kernels on its first start), tmux (run_v2.sh)
#   4. pipeline venv (.venv): torch (CUDA 13) + requirements.txt
#   5. vLLM in its own venv (~/vllm-venv; it pins its own torch)
#   6. llama.cpp's llama-server built for this GPU, in ~/llama.cpp (only with LLAMA=1)
#   7. waits for the downloads, then runs the fake-model smoke test
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VLLM_MODELS="${VLLM_MODELS:-Qwen/Qwen3.8-27B-FP8 google/gemma-4-E4B-it google/gemma-4-12B-it}"   # large + small setups
VLLM_DIR="${VLLM_DIR:-$HOME/vllm-venv}"
VLLM_VERSION="${VLLM_VERSION:-0.32.0}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
LLAMA_REF="${LLAMA_REF:-master}"                 # a tag or commit to pin llama.cpp
GGUF_REPO="${GGUF_REPO:-unsloth/Qwen3.8-27B-GGUF}"
GGUF_FILE="${GGUF_FILE:-Qwen3.8-27B-Q8_0.gguf}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu130}"
export PATH="/usr/local/cuda/bin:$PATH"
LOG="$HERE/logs"; mkdir -p "$LOG"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

step "1/7 GPU"
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader
ARCH="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d '.')"   # e.g. 120 for Blackwell

step "2/7 model downloads (background, log: logs/setup_download.log)"
[ -d "$HERE/.venv" ] || python3 -m venv "$HERE/.venv"
PY="$HERE/.venv/bin/python"
"$PY" -m pip install -q --upgrade pip huggingface_hub
DL_PID=""
if [ -z "${SKIP_MODEL:-}" ]; then
  "$PY" - "$VLLM_MODELS" "$GGUF_REPO" "$GGUF_FILE" "${LLAMA:-}" > "$LOG/setup_download.log" 2>&1 <<'EOF' &
import sys
from huggingface_hub import hf_hub_download, snapshot_download
vllm_models, gguf_repo, gguf_file, llama = sys.argv[1:5]
for m in vllm_models.split():
    print(snapshot_download(m), flush=True)
print(snapshot_download("sentence-transformers/all-mpnet-base-v2"), flush=True)   # pipeline/embed.py
if llama:
    print(hf_hub_download(gguf_repo, gguf_file), flush=True)
print("done")
EOF
  DL_PID=$!
  echo "  $VLLM_MODELS${LLAMA:+, $GGUF_FILE} and the embedding model (pid $DL_PID)"
fi

step "3/7 system tools"
missing=""
command -v ffmpeg >/dev/null || missing="$missing ffmpeg"
command -v ninja  >/dev/null || missing="$missing ninja-build"
command -v tmux   >/dev/null || missing="$missing tmux"
if [ -n "$missing" ]; then
  sudo apt-get update -qq && sudo apt-get install -y -qq $missing || echo "  apt install of$missing failed"
fi
echo "  ffmpeg $(command -v ffmpeg >/dev/null && echo ok || echo missing), ninja $(ninja --version 2>/dev/null || echo missing)"

step "4/7 pipeline venv"
"$PY" -c "import torch" 2>/dev/null || "$PY" -m pip install -q torch --index-url "$TORCH_INDEX"
"$PY" -m pip install -q -r "$HERE/requirements.txt"
"$PY" -c "import torch; print('  torch', torch.__version__, 'cuda', torch.cuda.is_available())"

step "5/7 vLLM $VLLM_VERSION"
[ -d "$VLLM_DIR" ] || python3 -m venv "$VLLM_DIR"
"$VLLM_DIR/bin/python" -c "import vllm" 2>/dev/null || {
  "$VLLM_DIR/bin/pip" install -q --upgrade pip && "$VLLM_DIR/bin/pip" install -q "vllm==$VLLM_VERSION"; }
"$VLLM_DIR/bin/pip" install -q ninja        # also in the venv: vLLM finds it there when started by the pipeline
"$VLLM_DIR/bin/python" -c "import vllm, torch; print('  vllm', vllm.__version__, 'torch', torch.__version__)"
"$VLLM_DIR/bin/ninja" --version > /dev/null && echo "  ninja in the vLLM venv: ok"

step "6/7 llama.cpp"
if [ -n "${LLAMA:-}" ]; then
  [ -d "$LLAMA_DIR/.git" ] || git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
  git -C "$LLAMA_DIR" fetch -q origin "$LLAMA_REF" && git -C "$LLAMA_DIR" checkout -q FETCH_HEAD
  echo "  llama.cpp at $(git -C "$LLAMA_DIR" log -1 --format='%h %cd' --date=short), CUDA sm_$ARCH"
  cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="$ARCH" \
        -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release > /dev/null
  cmake --build "$LLAMA_DIR/build" --config Release -j "$(nproc)" --target llama-server 2>&1 | grep -E "error" || true
  "$LLAMA_DIR/build/bin/llama-server" --version 2>&1 | head -1
else
  echo "  skipped (LLAMA=1 to build it)"
fi

step "7/7 downloads and smoke test"
if [ -n "$DL_PID" ]; then
  echo "  waiting for the downloads..."
  wait "$DL_PID" || { echo "  download failed: see logs/setup_download.log"; exit 1; }
  sed 's/^/  /' "$LOG/setup_download.log" | grep -v Warning
fi
cd "$HERE" && "$PY" tests/smoke_pipeline2.py 2>&1 | tail -1

echo
echo "Ready. vllm: $VLLM_DIR/bin/vllm (lir2_config.toml [engine] vllm)."
echo "Run VR on the small setup, then on the large one:  bash run_v2.sh --setups small,large --courses vr"
echo "To run vllm by hand, put its venv and CUDA on the PATH first:"
echo "  export PATH=$VLLM_DIR/bin:/usr/local/cuda/bin:\$PATH"
