#!/usr/bin/env bash
# The demo's GPU instance does one thing: serve the model (and the query embedder). The viewer, the question box's
# tool loop and the videos run on the presenter's laptop (Windows), which reaches these two servers through an SSH
# port forward. No port is opened on the instance; both servers listen on 127.0.0.1 only.
#
#   bash pipeline/demo/ec2_model_server.sh --engine llamacpp     # Gemma 4 12B QAT GGUF on llama-server (default)
#   bash pipeline/demo/ec2_model_server.sh --engine vllm         # Gemma 4 12B (BF16, google/gemma-4-12B-it) on vLLM
#   bash pipeline/demo/ec2_model_server.sh                        # asks which engine (in a terminal)
#   bash pipeline/demo/ec2_model_server.sh --status               # what runs, and the tunnel command
#   bash pipeline/demo/ec2_model_server.sh --stop                 # stops both servers (tmux sessions model, embed)
#   --no-embed      do not serve the embedder (the laptop then embeds on its CPU: setup_windows.ps1 -LocalEmbed)
#
# Safe to rerun: what is installed, built or downloaded is reused, a server that already answers is kept. The
# engine is chosen at every start; switching engines stops the other one first (one GPU).
#
# Environment (all optional):
#   HF_TOKEN=...          Hugging Face token (vLLM's google/gemma-4-12B-it is gated); else pipeline/.hf_token
#   NO_NVME=1             keep the model cache on the root volume (survives a stop; loads slower)
#   LLAMA_REF=master      build another llama.cpp (default: the commit the local PC runs)
#   VLLM_PKG='vllm==X'    the vLLM to install in ~/vllm-venv (default: vllm>=0.23, the first with Gemma 4)
#   TORCH_CPU=1           CPU-only torch for the embedder (3 GB less to fetch; a query then takes ~0.1-0.3 s more)
#   PYTHON=python3.12     the Python for the venvs (3.11 or newer)
#   FORCE=1               start vLLM on a GPU under 40 GB anyway (the BF16 weights alone are 24 GB)
#   Reuse instead of install (also how a workstation stands in for the instance in a test):
#   LLAMA_BIN=/path/llama-server  MODEL_PATH=/path/model.gguf  EMBED_PYTHON=/path/python (has sentence-transformers)
#   CONFIG=/path/config.json  EMBED_PORT=8097  EMBED_DEVICE=cpu|cuda  TOOLBOX=name  SKIP_APT=1
#
# What it does:
#   1. GPU check; the Hugging Face cache on the local NVMe when there is one; the token
#   2. system packages (only the missing ones): tmux, curl, python3-venv; for llama.cpp also git, cmake, build tools
#   3. ~/demo-venv (huggingface_hub; torch and sentence-transformers for the embedder, the versions the facts were
#      embedded with); the downloads start in the background: the model and Qwen/Qwen3-Embedding-0.6B
#   4. the engine: llama.cpp's llama-server built for this GPU (~/llama.cpp), or vLLM in ~/vllm-venv
#   5. the config (configs/gemma4_12b_demo.json or configs/gemma4_12b_vllm_demo.json) set for this instance
#   6. tmux "model": the model server on 127.0.0.1:8096 (scripts/llm/serve.py, from the config: the same flags the
#      laptop's qa expects); tmux "embed": demo/embed_server.py on 127.0.0.1:8097
#   7. warm-up: a short request and one with the qa tools and thinking (the first request's costs are paid here)
#   8. prints the SSH tunnel command and the laptop's command
#
# The instance needs only pipeline/demo, pipeline/configs, pipeline/scripts/llm (+ scripts/__init__.py) and
# pipeline/prompts/qa_tools.json; `python -m demo push` (from the laptop) copies exactly those. See demo/README.md.
set -euo pipefail

DEMO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPE="$(dirname "$DEMO")"
ENGINE=""; EMBED=1; ACTION=start
while [ $# -gt 0 ]; do
  case "$1" in
    --engine) ENGINE="${2:-}"; shift 2 ;;
    --engine=*) ENGINE="${1#*=}"; shift ;;
    --no-embed) EMBED=0; shift ;;
    --stop) ACTION=stop; shift ;;
    --status) ACTION=status; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-$HOME/demo-venv}"
VLLM_VENV="${VLLM_VENV:-$HOME/vllm-venv}"
VLLM_PKG="${VLLM_PKG:-vllm>=0.23}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
LLAMA_REF="${LLAMA_REF:-69eb250670f471586fcec69caacd3c014aefb185}"   # the local PC's llama.cpp (build 2026-09-15)
GGUF_REPO="${GGUF_REPO:-unsloth/gemma-4-12B-it-qat-GGUF}"
GGUF_FILE="${GGUF_FILE:-gemma-4-12B-it-qat-UD-Q4_K_XL.gguf}"
GGUF_REV="${GGUF_REV:-980b060c40a8539ac159e0501a3e0f66a6365af3}"     # the revision configs/gemma4_12b_llamacpp.json uses
EMBED_MODEL="${EMBED_MODEL:-Qwen/Qwen3-Embedding-0.6B}"             # the layer's (knowledge/index.json "embedding")
EMBED_PORT="${EMBED_PORT:-8097}"
TORCH_PKG="${TORCH_PKG:-torch==2.14.1}"            # the versions the facts were embedded with
EMBED_PKGS="${EMBED_PKGS:-sentence-transformers==6.1.0 transformers==5.15.0 numpy}"
HUB_PKG="${HUB_PKG:-huggingface_hub==1.33.0}"
NVME="${NVME:-/opt/dlami/nvme}"
LOG="$DEMO/logs"; mkdir -p "$LOG"
export PATH="/usr/local/cuda/bin:$PATH"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mSTOP: %s\033[0m\n' "$*" >&2; exit 1; }
healthy() { curl -sf -m 3 "http://127.0.0.1:$1/health" >/dev/null 2>&1; }
cfg_get() { "$PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ''))" "$1" "$2"; }

tunnel_hint() {
  local mport="$1" user public token
  user="$(whoami)"
  token=$(curl -s -m 2 -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
  public=$(curl -s -m 2 -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
  [[ "$public" =~ ^[0-9.]+$ ]] || public="<instance-address>"
  echo "  On the laptop, the tunnel (the launcher opens it for you; to open it by hand, leave this running):"
  echo "    ssh -N -o ServerAliveInterval=15 -o ExitOnForwardFailure=yes -i <key.pem> \\"
  echo "        -L $mport:127.0.0.1:$mport$( [ "$EMBED" = 1 ] && printf ' -L %s:127.0.0.1:%s' "$EMBED_PORT" "$EMBED_PORT") $user@$public"
  echo "  Windows (PowerShell, from the repository folder):"
  echo "    powershell -ExecutionPolicy Bypass -File pipeline\\demo\\run_demo.ps1 -Instance $user@$public -Key C:\\path\\to\\key.pem"
  echo "  Linux / macOS:  cd pipeline && python -m demo run --instance $user@$public --key ~/key.pem"
}

if [ "$ACTION" = stop ]; then
  for s in model embed; do tmux kill-session -t "$s" 2>/dev/null && echo "  stopped tmux session $s" || true; done
  exit 0
fi
if [ "$ACTION" = status ]; then
  for p in "$([ -n "${CONFIG:-}" ] && cfg_get "$CONFIG" port || echo 8096)" "$EMBED_PORT"; do
    if healthy "$p"; then echo "  port $p: answers ($(curl -s -m 3 "http://127.0.0.1:$p/v1/models" | head -c 200))"
    else echo "  port $p: nothing answers"; fi
  done
  tmux ls 2>/dev/null | sed 's/^/  tmux /' || true
  tunnel_hint "$([ -n "${CONFIG:-}" ] && cfg_get "$CONFIG" port || echo 8096)"
  exit 0
fi

# ---------------------------------------------------------------------------------------------------------------
if [ -z "$ENGINE" ]; then
  if [ -t 0 ]; then
    read -rp "Which model server? [1] llama.cpp (Gemma 4 12B QAT GGUF, default)  [2] vLLM (Gemma 4 12B BF16): " pick
    case "${pick:-1}" in 2|vllm) ENGINE=vllm ;; *) ENGINE=llamacpp ;; esac
  else
    die "give --engine llamacpp or --engine vllm (no terminal to ask in)"
  fi
fi
case "$ENGINE" in llamacpp|llama.cpp|llama) ENGINE=llamacpp ;; vllm) ;; *) die "--engine must be llamacpp or vllm" ;; esac
if [ "$ENGINE" = vllm ]; then CONFIG="${CONFIG:-$PIPE/configs/gemma4_12b_vllm_demo.json}"
else CONFIG="${CONFIG:-$PIPE/configs/gemma4_12b_demo.json}"; fi
[ -f "$CONFIG" ] || die "no config $CONFIG: copy pipeline/configs from the repository (python -m demo push does)"
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
  || die "$PYTHON is $("$PYTHON" --version 2>&1); 3.11 or newer is needed: the Ubuntu 24.04 AMI, or PYTHON=python3.12"
MODEL_PORT="$(cfg_get "$CONFIG" port)"
SERVED="$(cfg_get "$CONFIG" model)"
T0=$(date +%s)
echo "Engine: $ENGINE ($(basename "$CONFIG"), model $SERVED on 127.0.0.1:$MODEL_PORT); embedder: $([ "$EMBED" = 1 ] && echo "$EMBED_MODEL on 127.0.0.1:$EMBED_PORT" || echo "none (the laptop embeds)")"

# ---------------------------------------------------------------------------------------------------------------
step "1/8 GPU, model cache, token"
command -v nvidia-smi >/dev/null || die "nvidia-smi not found: this needs a GPU instance with the NVIDIA driver"
nvidia-smi --query-gpu=name,memory.total,memory.used,compute_cap --format=csv,noheader || die "nvidia-smi sees no GPU"
ARCH="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d '. ')"
GPU_MEM="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')"
if [ "$ENGINE" = vllm ] && [ "$GPU_MEM" -lt 40000 ] && [ -z "${FORCE:-}" ]; then
  die "vLLM serves the BF16 checkpoint (24 GB of weights): this GPU has ${GPU_MEM} MiB. Use --engine llamacpp, a GPU with 40 GB or more, or FORCE=1"
fi
HF_DIR="$HOME/.cache/huggingface"
if [ -z "${NO_NVME:-}" ] && mountpoint -q "$NVME" 2>/dev/null && [ -w "$NVME" ]; then
  if [ "$(readlink -f "$HF_DIR")" != "$NVME/huggingface" ]; then
    mkdir -p "$NVME/huggingface"
    if [ -d "$HF_DIR" ] && [ ! -L "$HF_DIR" ]; then cp -a "$HF_DIR/." "$NVME/huggingface/" && rm -rf "$HF_DIR"; fi
    rm -f "$HF_DIR"; mkdir -p "$(dirname "$HF_DIR")"; ln -s "$NVME/huggingface" "$HF_DIR"
  fi
  mkdir -p "$NVME/huggingface"
  echo "  model cache: $HF_DIR -> $NVME/huggingface (local NVMe)"
else
  mkdir -p "$HF_DIR"; echo "  model cache: $HF_DIR"
fi
if [ -z "${HF_TOKEN:-}" ] && [ -f "$PIPE/.hf_token" ]; then HF_TOKEN="$(tr -d '[:space:]' < "$PIPE/.hf_token")"; fi
if [ -n "${HF_TOKEN:-}" ]; then
  export HF_TOKEN; (umask 077; printf '%s' "$HF_TOKEN" > "$HF_DIR/token"); echo "  Hugging Face token: set"
elif [ "$ENGINE" = vllm ] && [ ! -f "$HF_DIR/token" ]; then
  echo "  WARNING: no Hugging Face token: google/gemma-4-12B-it is gated; the download fails unless it is cached"
fi

# ---------------------------------------------------------------------------------------------------------------
step "2/8 system packages"
need=""
if [ -z "${SKIP_APT:-}" ] && command -v dpkg >/dev/null; then
  pkgs="tmux curl"
  [ "$ENGINE" = llamacpp ] && [ -z "${LLAMA_BIN:-}" ] && pkgs="$pkgs git cmake build-essential"
  for pkg in $pkgs; do dpkg -s "$pkg" >/dev/null 2>&1 || need="$need $pkg"; done
  "$PYTHON" -c "import ensurepip, venv" 2>/dev/null || need="$need python$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')-venv"
  if [ -n "$need" ]; then
    echo "  installing:$need"
    sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $need > /dev/null
  fi
fi
command -v tmux >/dev/null || die "tmux is missing"
echo "  ok ($("$PYTHON" --version), tmux $(tmux -V | cut -d' ' -f2))"

# ---------------------------------------------------------------------------------------------------------------
step "3/8 venv ($VENV) and downloads"
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
PY="$VENV/bin/python"
"$PY" -c "import huggingface_hub" 2>/dev/null || { "$PY" -m pip install -q --upgrade pip; "$PY" -m pip install -q "$HUB_PKG" || "$PY" -m pip install -q huggingface_hub; }
DL_MODEL=""
if [ "$ENGINE" = llamacpp ] && [ -z "${MODEL_PATH:-}" ]; then DL_MODEL="gguf"; fi
if [ "$ENGINE" = vllm ]; then DL_MODEL="snapshot"; fi
VLLM_MODEL="$(cfg_get "$CONFIG" model_path)"
"$PY" - "$DL_MODEL" "$GGUF_REPO" "$GGUF_FILE" "$GGUF_REV" "$VLLM_MODEL" "$([ "$EMBED" = 1 ] && echo "$EMBED_MODEL")" \
    > "$LOG/download.log" 2>&1 <<'EOF' &
import sys
from huggingface_hub import hf_hub_download, snapshot_download
kind, repo, file, rev, vllm_model, embed = sys.argv[1:7]
if kind == "gguf":
    print("gguf", hf_hub_download(repo, file, revision=rev), flush=True)
elif kind == "snapshot":
    print("model", snapshot_download(vllm_model, allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt",
                                                                 "*.jinja", "tokenizer*"]), flush=True)
if embed:
    print("embed", snapshot_download(embed), flush=True)
print("done", flush=True)
EOF
DL_PID=$!
echo "  downloading in the background (pid $DL_PID, demo/logs/download.log)"
EMBED_PY="${EMBED_PYTHON:-$PY}"
if [ "$EMBED" = 1 ] && [ -z "${EMBED_PYTHON:-}" ]; then
  if ! "$PY" -c "import torch" 2>/dev/null; then
    idx=(); [ -n "${TORCH_CPU:-}" ] && idx=(--index-url https://download.pytorch.org/whl/cpu)
    echo "  installing $TORCH_PKG${TORCH_CPU:+ (CPU only)} for the embedder"
    "$PY" -m pip install -q "${idx[@]}" "$TORCH_PKG" || "$PY" -m pip install -q "${idx[@]}" torch
  fi
  # shellcheck disable=SC2086
  "$PY" -c "import sentence_transformers, transformers, numpy" 2>/dev/null \
    || "$PY" -m pip install -q $EMBED_PKGS || "$PY" -m pip install -q sentence-transformers transformers numpy
fi
[ "$EMBED" = 1 ] && "$EMBED_PY" -c "import torch, sentence_transformers; print('  embedder: torch', torch.__version__, '(CUDA', str(torch.cuda.is_available()) + '), sentence-transformers', sentence_transformers.__version__)"

# ---------------------------------------------------------------------------------------------------------------
step "4/8 the engine: $ENGINE"
if [ "$ENGINE" = llamacpp ]; then
  if [ -n "${LLAMA_BIN:-}" ]; then
    echo "  using $LLAMA_BIN"
  else
    LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"
    STAMP="$LLAMA_DIR/build/.demo_build"
    if [ -x "$LLAMA_BIN" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$LLAMA_REF sm_$ARCH" ]; then
      echo "  already built ($(cat "$STAMP"))"
    else
      command -v nvcc >/dev/null || die "nvcc not found: use the Deep Learning Base OSS Nvidia Driver AMI (CUDA toolkit)"
      [ -d "$LLAMA_DIR/.git" ] || { mkdir -p "$LLAMA_DIR" && git -C "$LLAMA_DIR" init -q && \
                                     git -C "$LLAMA_DIR" remote add origin https://github.com/ggml-org/llama.cpp.git; }
      git -C "$LLAMA_DIR" fetch -q --depth 1 origin "$LLAMA_REF" \
        || { echo "  could not fetch $LLAMA_REF; building master"; LLAMA_REF=master; git -C "$LLAMA_DIR" fetch -q --depth 1 origin master; }
      git -C "$LLAMA_DIR" checkout -q --force FETCH_HEAD
      echo "  building llama-server for sm_$ARCH (5-15 min; log demo/logs/llama_build.log)"
      cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="$ARCH" \
            -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release > "$LOG/llama_build.log" 2>&1 \
        || { tail -20 "$LOG/llama_build.log"; die "cmake failed"; }
      cmake --build "$LLAMA_DIR/build" --config Release -j "$(nproc)" --target llama-server >> "$LOG/llama_build.log" 2>&1 \
        || { grep -E "error" "$LOG/llama_build.log" | tail -20; die "the llama.cpp build failed"; }
      echo "$LLAMA_REF sm_$ARCH" > "$STAMP"
    fi
  fi
  BIN="$LLAMA_BIN"
else
  [ -x "$VLLM_VENV/bin/python" ] || "$PYTHON" -m venv "$VLLM_VENV"
  if ! "$VLLM_VENV/bin/python" -c "import vllm" 2>/dev/null; then
    echo "  installing $VLLM_PKG in $VLLM_VENV (5-10 min: it brings its own torch)"
    "$VLLM_VENV/bin/python" -m pip install -q --upgrade pip
    "$VLLM_VENV/bin/python" -m pip install -q "$VLLM_PKG" || die "vLLM did not install (see the pip output above)"
  fi
  echo "  vLLM $("$VLLM_VENV/bin/python" -c 'import vllm; print(vllm.__version__)' 2>/dev/null)"
  BIN="$VLLM_VENV/bin/vllm"
fi

# ---------------------------------------------------------------------------------------------------------------
step "5/8 downloads and the config"
kill -0 "$DL_PID" 2>/dev/null && echo "  waiting for the downloads..."
wait "$DL_PID" || { cat "$LOG/download.log"; die "a download failed (demo/logs/download.log)"; }
sed -n 's/^\(gguf\|model\|embed\) /  \1: /p' "$LOG/download.log"
args=(--gpu-mem-mib "$GPU_MEM" --binary "$BIN")
if [ "$ENGINE" = llamacpp ]; then
  GGUF_PATH="${MODEL_PATH:-$(sed -n 's/^gguf //p' "$LOG/download.log")}"
  [ -f "$GGUF_PATH" ] || die "no model file: $GGUF_PATH"
  args+=(--model-path "$GGUF_PATH")
fi
[ -n "${TOOLBOX:-}" ] && args+=(--toolbox "$TOOLBOX")
"$PYTHON" "$DEMO/demo_tool.py" config "$CONFIG" "${args[@]}"

# ---------------------------------------------------------------------------------------------------------------
step "6/8 the servers (tmux sessions model and embed)"
RUN_ENV="$(printf '%q ' env "PATH=$VENV/bin:$PATH" HF_HUB_OFFLINE=1)"
Q() { printf '%q' "$1"; }
OTHER_PORT_USER=""
if healthy "$MODEL_PORT"; then
  served_now="$(curl -s -m 5 "http://127.0.0.1:$MODEL_PORT/v1/models" | "$PYTHON" -c 'import json,sys; print(" ".join(m["id"] for m in json.load(sys.stdin).get("data", [])))' 2>/dev/null || true)"
  if [ " $served_now " = " $SERVED " ] || [[ " $served_now " == *" $SERVED "* ]]; then
    echo "  the model server already answers on port $MODEL_PORT ($served_now): kept"
  else
    echo "  port $MODEL_PORT serves '$served_now', not $SERVED (the other engine?): stopping it"
    tmux kill-session -t model 2>/dev/null || true
    tmux kill-session -t gemma 2>/dev/null || true          # setup_demo.sh's session
    for _ in $(seq 60); do healthy "$MODEL_PORT" || break; sleep 1; done
    healthy "$MODEL_PORT" && die "port $MODEL_PORT is still served by another program: stop it (ss -ltnp | grep :$MODEL_PORT)"
    OTHER_PORT_USER=stopped
  fi
fi
if ! healthy "$MODEL_PORT"; then
  if tmux has-session -t model 2>/dev/null && [ -z "$OTHER_PORT_USER" ]; then
    echo "  tmux session model is running: waiting for its server (still loading?)"
  else
    tmux kill-session -t model 2>/dev/null || true
    tmux new -d -s model -c "$PIPE" "$RUN_ENV $(Q "$PY") -m scripts.llm.serve $(Q "$CONFIG") 2>&1 | tee -a $(Q "$LOG/model.log")"
    echo "  started $ENGINE (log demo/logs/model.log; server log $(cfg_get "$CONFIG" server_log))"
  fi
fi
"$PYTHON" "$DEMO/demo_tool.py" wait-model "$CONFIG" --timeout "$([ "$ENGINE" = vllm ] && echo 2400 || echo 900)" \
  || die "the model server did not start: tmux attach -t model"

if [ "$EMBED" = 1 ]; then
  if healthy "$EMBED_PORT"; then
    echo "  the embedding server already answers on port $EMBED_PORT: kept"
  else
    tmux kill-session -t embed 2>/dev/null || true
    dev=(); [ -n "${EMBED_DEVICE:-}" ] && dev=(--device "$EMBED_DEVICE")
    tmux new -d -s embed -c "$PIPE" "$RUN_ENV $(Q "$EMBED_PY") demo/embed_server.py --model $(Q "$EMBED_MODEL") --port $(Q "$EMBED_PORT") ${dev[*]:-} 2>&1 | tee -a $(Q "$LOG/embed.log")"
    echo "  started the embedding server (log demo/logs/embed.log)"
  fi
  "$PYTHON" "$DEMO/demo_tool.py" wait-url "http://127.0.0.1:$EMBED_PORT/health" --timeout 600 --log "$LOG/embed.log" \
    || die "the embedding server did not start: tmux attach -t embed"
fi

# ---------------------------------------------------------------------------------------------------------------
step "7/8 warm-up"
"$PYTHON" "$DEMO/demo_tool.py" warm-model "$CONFIG" || echo "  WARNING: a warm-up request failed: tmux attach -t model"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | sed 's/^/  GPU memory: /'

# ---------------------------------------------------------------------------------------------------------------
step "8/8 ready in $(( ($(date +%s) - T0 + 59) / 60 )) min"
tunnel_hint "$MODEL_PORT"
echo "  Here:  bash $(sed "s|^$HOME|~|" <<< "$DEMO")/ec2_model_server.sh --status | --stop;  tmux attach -t model | embed"
