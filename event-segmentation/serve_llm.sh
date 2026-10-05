#!/usr/bin/env bash
# Serve Gemma 4 E4B-it (GGUF) with llama.cpp on an OpenAI-compatible endpoint.
# llama-server is linked against CUDA 13, whose runtime lives in the venv's pip packages.
set -euo pipefail

VENV=/home/prex_san/Documents/mtp-implementation
export LD_LIBRARY_PATH="$VENV/lib/python3.14/site-packages/nvidia/cu13/lib:${LD_LIBRARY_PATH:-}"

exec "$HOME/Documents/llama.cpp/build/bin/llama-server" \
    -hf "${LLM_HF:-unsloth/gemma-4-E4B-it-GGUF:UD-Q8_K_XL}" \
    --no-mmproj \
    -ngl 99 \
    -c "${LLM_CTX:-32768}" \
    --host 127.0.0.1 --port "${LLM_PORT:-8080}" \
    --jinja \
    --reasoning on --reasoning-format deepseek \
    "$@"
