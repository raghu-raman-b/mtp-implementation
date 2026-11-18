#!/usr/bin/env bash
# One command to run the learner demo (the viewer and its question box) on a fresh cloud GPU instance: Ubuntu with
# the NVIDIA driver and the CUDA toolkit (e.g. an AWS EC2 GPU instance with the Deep Learning AMI), Python 3.12.
# Safe to rerun: every step skips what is already done; the viewer is restarted (it picks up new code).
#
#   bash pipeline/demo/setup_demo.sh               # everything: build, downloads, servers in tmux, one test question
#   HF_TOKEN=... bash pipeline/demo/setup_demo.sh  # Hugging Face token; without it, pipeline/.hf_token (gitignored)
#   NO_NVME=1 ...                 # keep the model cache on the EBS root volume (survives a stop; loads slower)
#   VIEWER_HOST=0.0.0.0 ...       # listen on every interface (open the port in the security group); default:
#                                 # 127.0.0.1, reached through an SSH port forward (printed at the end)
#   VIEWER_PORT=8765 ...          # the viewer's port
#   LLAMA_REF=master ...          # build another llama.cpp (default: the commit the local PC runs)
#   TORCH_CPU=1 ...               # CPU-only torch (the query embedder runs on the CPU anyway; ~3 GB less to fetch)
#   PYTHON=python3.12 ...         # the Python for the venv (3.11 or newer: scripts/llm reads configs with tomllib)
#
# Expects the repository (or at least its pipeline/ folder) at ~/mtp-implementation (any place works); the videos
# are optional (a lecture without its file plays from YouTube). See pipeline/demo/README.md.
#
# What it does:
#   1. checks the GPU and the CUDA compiler (the architecture for the llama.cpp build comes from nvidia-smi)
#   2. the Hugging Face cache on the local NVMe (/opt/dlami/nvme) when there is one; the Hugging Face token
#   3. system packages: git, cmake, build tools, tmux, curl, python3-venv (only the missing ones)
#   4. a venv (~/demo-venv) with what qa and the query embedder need: torch, sentence-transformers, numpy,
#      huggingface_hub (the versions the local PC runs); then the model downloads start in the background:
#      Gemma 4 12B QAT (unsloth/gemma-4-12B-it-qat-GGUF, gemma-4-12B-it-qat-UD-Q4_K_XL.gguf, 7.5 GB, the exact
#      revision the local config names) and the embedder Qwen/Qwen3-Embedding-0.6B (1.2 GB)
#   5. llama.cpp's llama-server built for this GPU (~/llama.cpp)
#   6. the demo config configs/gemma4_12b_demo.json set for this instance (binary, model file, slots by GPU memory;
#      sampling and thinking as on the local PC, so answers behave the same)
#   7. the videos: how many are here (the rest play from YouTube) and the rsync line to copy them
#   8. tmux sessions: "gemma" (the model server) and "viewer" (the viewer with QA_CONFIG set to the demo config,
#      warming qa at start)
#   9. two questions through the viewer (warm-up and test): the answers, their citations and their times
#
# Why llama.cpp and not vLLM: the local PC answers with this exact GGUF (4-bit QAT) on llama.cpp; the same file,
# chat template and reasoning budget give the same behaviour here. vLLM would need another checkpoint of the model
# (its GGUF support does not cover this one), and for one learner at a time it is no faster; llama.cpp also builds
# in minutes and needs no second venv with its own torch.
set -euo pipefail

DEMO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPE="$(dirname "$DEMO")"                         # the pipeline folder
COURSE="${COURSE:-nptel_vr}"
VENV="${VENV:-$HOME/demo-venv}"
PYTHON="${PYTHON:-python3}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
LLAMA_REF="${LLAMA_REF:-69eb250670f471586fcec69caacd3c014aefb185}"   # the local PC's llama.cpp (build 2026-09-15)
GGUF_REPO="${GGUF_REPO:-unsloth/gemma-4-12B-it-qat-GGUF}"
GGUF_FILE="${GGUF_FILE:-gemma-4-12B-it-qat-UD-Q4_K_XL.gguf}"
GGUF_REV="${GGUF_REV:-980b060c40a8539ac159e0501a3e0f66a6365af3}"     # the revision configs/gemma4_12b_llamacpp.json uses
EMBED_MODEL="${EMBED_MODEL:-Qwen/Qwen3-Embedding-0.6B}"             # the layer's (knowledge/index.json "embedding")
CONFIG="${CONFIG:-$PIPE/configs/gemma4_12b_demo.json}"
VIEWER_HOST="${VIEWER_HOST:-127.0.0.1}"
VIEWER_PORT="${VIEWER_PORT:-8765}"
TORCH_PKG="${TORCH_PKG:-torch==2.14.1}"            # the versions the local PC runs (the facts were embedded with them)
PIP_PKGS="${PIP_PKGS:-sentence-transformers==6.1.0 transformers==5.15.0 numpy}"
HUB_PKG="${HUB_PKG:-huggingface_hub==1.33.0}"       # installed first (the downloads use it while the rest installs)
NVME="${NVME:-/opt/dlami/nvme}"
LOG="$DEMO/logs"; mkdir -p "$LOG"
export PATH="/usr/local/cuda/bin:$PATH"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mSTOP: %s\033[0m\n' "$*" >&2; exit 1; }
T0=$(date +%s)

# ---------------------------------------------------------------------------------------------------------------
step "1/9 GPU"
command -v nvidia-smi >/dev/null || die "nvidia-smi not found: this needs a GPU instance with the NVIDIA driver"
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader \
  || die "nvidia-smi sees no GPU"
ARCH="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d '. ')"   # e.g. 86, 89, 90, 120
GPU_MEM="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')"
command -v nvcc >/dev/null || die "nvcc not found (looked in PATH and /usr/local/cuda/bin): install the CUDA toolkit"
echo "  CUDA $(nvcc --version | sed -n 's/.*release \([0-9.]*\).*/\1/p'), build for sm_$ARCH, ${GPU_MEM} MiB"
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
  || die "$PYTHON is $("$PYTHON" --version 2>&1); qa needs Python 3.11 or newer: use the Ubuntu 24.04 AMI, or PYTHON=python3.12"
[ -d "$PIPE/output/$COURSE/knowledge" ] || die "no $PIPE/output/$COURSE/knowledge: copy or clone the repository first (README)"

# ---------------------------------------------------------------------------------------------------------------
step "2/9 model cache and Hugging Face token"
# As in pipeline/setup_ec2.sh: ~/.cache/huggingface becomes a link to the local NVMe when the instance has one (reads
# at GB/s instead of the EBS volume's ~125 MB/s). Instance store is wiped by a stop: rerun this script after a start.
HF_DIR="$HOME/.cache/huggingface"
if [ -z "${NO_NVME:-}" ] && mountpoint -q "$NVME" 2>/dev/null && [ -w "$NVME" ]; then
  if [ "$(readlink -f "$HF_DIR")" != "$NVME/huggingface" ]; then
    mkdir -p "$NVME/huggingface"
    if [ -d "$HF_DIR" ] && [ ! -L "$HF_DIR" ]; then         # an existing cache on EBS: move it over first
      cp -a "$HF_DIR/." "$NVME/huggingface/" && rm -rf "$HF_DIR"
    fi
    rm -f "$HF_DIR"; mkdir -p "$(dirname "$HF_DIR")"; ln -s "$NVME/huggingface" "$HF_DIR"
  fi
  mkdir -p "$NVME/huggingface"                              # a link left from before a stop: the folder is gone
  echo "  Hugging Face cache: $HF_DIR -> $NVME/huggingface (local NVMe, $(df -h --output=avail "$NVME" | tail -1 | tr -d ' ') free)"
else
  mkdir -p "$HF_DIR"
  echo "  Hugging Face cache: $HF_DIR (no local NVMe at $NVME)"
fi
if [ -z "${HF_TOKEN:-}" ] && [ -f "$PIPE/.hf_token" ]; then HF_TOKEN="$(tr -d '[:space:]' < "$PIPE/.hf_token")"; fi
if [ -n "${HF_TOKEN:-}" ]; then
  export HF_TOKEN
  (umask 077; printf '%s' "$HF_TOKEN" > "$HF_DIR/token")
  echo "  Hugging Face token: set"
else
  echo "  Hugging Face token: none (the models are public; downloads may be slower)"
fi

# ---------------------------------------------------------------------------------------------------------------
step "3/9 system packages"
need=""
for pkg in git cmake build-essential tmux curl; do dpkg -s "$pkg" >/dev/null 2>&1 || need="$need $pkg"; done
"$PYTHON" -c "import ensurepip, venv" 2>/dev/null || need="$need python$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')-venv"
if [ -n "$need" ]; then
  echo "  installing:$need"
  sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $need > /dev/null
fi
echo "  git $(git --version | cut -d' ' -f3), cmake $(cmake --version | head -1 | cut -d' ' -f3), tmux $(tmux -V | cut -d' ' -f2), $("$PYTHON" --version)"

# ---------------------------------------------------------------------------------------------------------------
step "4/9 Python venv ($VENV) and model downloads"
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
PY="$VENV/bin/python"
if ! "$PY" -c "import huggingface_hub" 2>/dev/null; then
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q "$HUB_PKG" || "$PY" -m pip install -q huggingface_hub
fi
# downloads in the background while torch installs and llama.cpp builds
"$PY" - "$GGUF_REPO" "$GGUF_FILE" "$GGUF_REV" "$EMBED_MODEL" > "$LOG/download.log" 2>&1 <<'EOF' &
import sys
from huggingface_hub import hf_hub_download, snapshot_download
repo, file, rev, embed = sys.argv[1:5]
print("gguf", hf_hub_download(repo, file, revision=rev), flush=True)
print("embed", snapshot_download(embed), flush=True)
print("done", flush=True)
EOF
DL_PID=$!
echo "  downloading $GGUF_FILE and $EMBED_MODEL (pid $DL_PID, log demo/logs/download.log)"
if ! "$PY" -c "import torch" 2>/dev/null; then
  idx=(); [ -n "${TORCH_CPU:-}" ] && idx=(--index-url https://download.pytorch.org/whl/cpu)
  echo "  installing $TORCH_PKG${TORCH_CPU:+ (CPU only)} (a few minutes: the CUDA wheels are ~3 GB)"
  "$PY" -m pip install -q "${idx[@]}" "$TORCH_PKG" \
    || { echo "  $TORCH_PKG did not install; trying the latest torch"; "$PY" -m pip install -q "${idx[@]}" torch; }
fi
if ! "$PY" -c "import sentence_transformers, transformers, numpy" 2>/dev/null; then
  echo "  installing $PIP_PKGS"
  # shellcheck disable=SC2086
  "$PY" -m pip install -q $PIP_PKGS \
    || { echo "  the pinned versions did not install; trying the latest"; \
         "$PY" -m pip install -q sentence-transformers transformers numpy; }
fi
"$PY" -c "import torch, sentence_transformers, transformers; print('  torch', torch.__version__, '(CUDA available:', str(torch.cuda.is_available()) + ')', 'sentence-transformers', sentence_transformers.__version__, 'transformers', transformers.__version__)"

# ---------------------------------------------------------------------------------------------------------------
step "5/9 llama.cpp ($LLAMA_DIR)"
LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"
STAMP="$LLAMA_DIR/build/.demo_build"                  # what the binary was built from: ref and architecture
if [ -x "$LLAMA_BIN" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$LLAMA_REF sm_$ARCH" ]; then
  echo "  already built ($(cat "$STAMP"))"
else
  [ -d "$LLAMA_DIR/.git" ] || { mkdir -p "$LLAMA_DIR" && git -C "$LLAMA_DIR" init -q && \
                                 git -C "$LLAMA_DIR" remote add origin https://github.com/ggml-org/llama.cpp.git; }
  if ! git -C "$LLAMA_DIR" fetch -q --depth 1 origin "$LLAMA_REF"; then
    echo "  could not fetch $LLAMA_REF; building master instead"
    LLAMA_REF=master; git -C "$LLAMA_DIR" fetch -q --depth 1 origin master
  fi
  git -C "$LLAMA_DIR" checkout -q --force FETCH_HEAD
  echo "  llama.cpp $(git -C "$LLAMA_DIR" log -1 --format='%h %cd' --date=short), CUDA sm_$ARCH; building llama-server (5-15 min)"
  cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="$ARCH" \
        -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release > "$LOG/llama_build.log" 2>&1 \
    || { tail -20 "$LOG/llama_build.log"; die "cmake failed (demo/logs/llama_build.log)"; }
  cmake --build "$LLAMA_DIR/build" --config Release -j "$(nproc)" --target llama-server >> "$LOG/llama_build.log" 2>&1 \
    || { grep -E "error" "$LOG/llama_build.log" | tail -20; die "the llama.cpp build failed (demo/logs/llama_build.log)"; }
  echo "$LLAMA_REF sm_$ARCH" > "$STAMP"
fi
"$LLAMA_BIN" --version 2>&1 | grep -m1 -i version | sed 's/^/  /' || true

# ---------------------------------------------------------------------------------------------------------------
step "6/9 downloads and the demo config"
if kill -0 "$DL_PID" 2>/dev/null; then echo "  waiting for the downloads..."; fi
wait "$DL_PID" || { cat "$LOG/download.log"; die "a download failed (demo/logs/download.log)"; }
GGUF_PATH="$(sed -n 's/^gguf //p' "$LOG/download.log")"
[ -f "$GGUF_PATH" ] || die "no model file after the download: $GGUF_PATH"
echo "  $GGUF_PATH ($(du -hL "$GGUF_PATH" | cut -f1))"
echo "  $(sed -n 's/^embed //p' "$LOG/download.log")"
"$PY" "$DEMO/demo_tool.py" config "$CONFIG" --gpu-mem-mib "$GPU_MEM" --binary "$LLAMA_BIN" --model-path "$GGUF_PATH"
MODEL_PORT="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['port'])" "$CONFIG")"

# ---------------------------------------------------------------------------------------------------------------
step "7/9 videos"
"$PY" "$DEMO/demo_tool.py" media --course "$COURSE"
echo "  to play the files instead of YouTube, copy them from the PC (5.5 GB; from the repository root there):"
echo "    rsync -a --info=progress2 pipeline/input/$COURSE/media/ <instance>:$(sed "s|^$HOME|~|" <<< "$PIPE")/input/$COURSE/media/"

# ---------------------------------------------------------------------------------------------------------------
step "8/9 servers (tmux sessions gemma and viewer)"
# the commands run in tmux get their environment explicitly (a tmux server started earlier has an older one)
RUN_ENV="$(printf '%q ' env "PATH=$VENV/bin:$PATH" HF_HUB_OFFLINE=1 "QA_CONFIG=$CONFIG")"
Q() { printf '%q' "$1"; }
if curl -sf "http://127.0.0.1:$MODEL_PORT/health" >/dev/null; then
  echo "  the model server already answers on port $MODEL_PORT"
elif tmux has-session -t gemma 2>/dev/null; then
  echo "  tmux session gemma is running: waiting for its server (still loading?)"
else
  tmux new -d -s gemma -c "$PIPE" "$RUN_ENV python -m scripts.llm.serve $(Q "$CONFIG") 2>&1 | tee -a $(Q "$LOG/gemma.log")"
  echo "  started (log demo/logs/gemma.log, server log $(sed -n 's/.*"server_log": "\(.*\)".*/\1/p' "$CONFIG"))"
fi
"$PY" "$DEMO/demo_tool.py" wait-model "$CONFIG" --timeout 900 || die "the model server did not start: tmux attach -t gemma"

listening() { ss -ltnH "sport = :$1" 2>/dev/null | grep -q .; }
tmux kill-session -t viewer 2>/dev/null || true          # restarted on every run: it picks up new code
for _ in $(seq 20); do listening "$VIEWER_PORT" || break; sleep 0.5; done
listening "$VIEWER_PORT" && die "port $VIEWER_PORT is taken by another program (ss -ltnp | grep :$VIEWER_PORT): stop it, or set VIEWER_PORT"
tmux new -d -s viewer -c "$PIPE" \
  "$RUN_ENV python viewer/serve.py $(Q "$COURSE") --host $(Q "$VIEWER_HOST") --port $(Q "$VIEWER_PORT") --warm 2>&1 | tee -a $(Q "$LOG/viewer.log")"
VURL="http://127.0.0.1:$VIEWER_PORT"
for _ in $(seq 60); do curl -sf "$VURL/api/course" >/dev/null && break; sleep 1; done
curl -sf "$VURL/api/course" >/dev/null || { tail -20 "$LOG/viewer.log"; die "the viewer did not start: tmux attach -t viewer"; }
echo "  viewer up at $VURL (log demo/logs/viewer.log)"

# ---------------------------------------------------------------------------------------------------------------
step "9/9 warm-up: two questions through the viewer (the first warms the model and the embedder)"
echo "  (the first question also loads the query embedder in the viewer: ~10-20 s more than the next ones)"
"$PY" "$DEMO/demo_tool.py" ask "$VURL" "What is extended reality?" --min-citations 1 \
  || echo "  the warm-up question failed: see demo/logs/viewer.log and bash pipeline/demo/check_demo.sh"
"$PY" "$DEMO/demo_tool.py" ask "$VURL" "What is an HMD?" --min-citations 1 \
  || echo "  the second question failed: see demo/logs/viewer.log"

# ---------------------------------------------------------------------------------------------------------------
TOKEN=$(curl -s -m 2 -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
PUBLIC=$(curl -s -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
[[ "$PUBLIC" =~ ^[0-9.]+$ ]] || PUBLIC="<instance-address>"
echo
printf '\033[1;32mReady in %d min.\033[0m\n' $(( ($(date +%s) - T0 + 59) / 60 ))
if [ "$VIEWER_HOST" = "0.0.0.0" ]; then
  echo "  Open http://$PUBLIC:$VIEWER_PORT/  (the security group must allow TCP $VIEWER_PORT from your address)"
else
  echo "  On your PC, forward the port (leave it running):"
  echo "    ssh -N -L $VIEWER_PORT:127.0.0.1:$VIEWER_PORT $(whoami)@$PUBLIC"
  echo "  (with your key: ssh -i <key.pem> ...; if $VIEWER_PORT is taken on the PC, use -L 8766:127.0.0.1:$VIEWER_PORT and open :8766)"
  echo "  then open http://localhost:$VIEWER_PORT/"
fi
echo "  Check everything:  bash $(sed "s|^$HOME|~|" <<< "$DEMO")/check_demo.sh"
echo "  Sessions:          tmux attach -t gemma | tmux attach -t viewer   (Ctrl-b d to leave)"
