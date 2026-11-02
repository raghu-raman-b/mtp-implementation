#!/usr/bin/env bash
# Full LIR v2 run: both courses at once on one vLLM server, a live dashboard, and a stats report at the end.
#
#   bash run_v2.sh                          # VR + Deep Learning, every lecture, new run folder runs/v2-<date>-<time>
#   bash run_v2.sh --name full-1            # choose the run folder name
#   bash run_v2.sh --only 1-3               # some lectures only (same numbers for both courses)
#   bash run_v2.sh --courses vr             # one course (vr, dl, or vr,dl)
#   bash run_v2.sh --resume full-1          # continue a stopped run: answers already in its cache are not resent
#
# Everything a run writes stays in runs/<name>/, so earlier runs, v1 (lir/, output/) and lir-v2/ are untouched:
#   runs/<name>/report.md, charts/        run stats and outputs, with graphs (run_report.py)
#   runs/<name>/<course>/lir/             the LIR v2 (course.json, Lxx.json, activities/, decisions.jsonl, ...)
#   runs/<name>/<course>/build/           answer cache, step outputs, calls.jsonl (every request), report.md
#   runs/<name>/server.csv                GPU and vLLM metrics every 5 s
#   runs/<name>/meta.json, lir2_config.toml, *.log
#
# It opens a tmux session "lir2" (dashboard first). Ctrl-b d detaches; the run keeps going. tmux attach -t lir2.
#
# Settings for the most throughput (lir2_config.toml, tuned on this GPU, see README "Engines"): one Qwen 3.8 27B FP8
# server for all three roles, 128 sequences at once, prefix caching, MTP drafts. Both courses get all 128 request
# slots, so vLLM always has a queue: when one course is in a step with few requests (the registry goes lecture by
# lecture), the other fills the GPU.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
PY="$HERE/.venv/bin/python"
SESSION=lir2

NAME="v2-$(date +%Y%m%d-%H%M)"; ONLY=""; COURSES="vr,dl"; RESUME=""; ATTACH=1; DRY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --courses) COURSES="$2"; shift 2 ;;
    --resume) NAME="$2"; RESUME=1; shift 2 ;;
    --no-attach) ATTACH=""; shift ;;
    --dry-run) DRY=1; shift ;;          # write runs/<name>/control.sh and stop (nothing is started)
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "unknown option $1 (see --help)"; exit 1 ;;
  esac
done

declare -A DATASET=([vr]="../dataset/virtual_and_augmented_reality" [dl]="../dataset/mit_6_7960_deep_learning")
declare -A COURSE_ID=([vr]="nptel-virtual-and-augmented-reality" [dl]="mit-6-7960-deep-learning")
IFS=, read -ra KEYS <<< "$COURSES"
for k in "${KEYS[@]}"; do [ -n "${DATASET[$k]:-}" ] || { echo "unknown course '$k' (vr, dl)"; exit 1; }; done

RUN="$HERE/runs/$NAME"
# ---------------------------------------------------------------------------------------------- checks
[ -x "$PY" ] || { echo "no pipeline venv: run  bash setup_ec2.sh  first"; exit 1; }
[ -x "$HOME/vllm-venv/bin/vllm" ] || { echo "no vLLM: run  bash setup_ec2.sh  first"; exit 1; }
command -v tmux >/dev/null || { echo "tmux is not installed (sudo apt-get install tmux)"; exit 1; }
if [ -z "$DRY" ] && tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "a run is already open in tmux session '$SESSION':  tmux attach -t $SESSION   (or tmux kill-session -t $SESSION)"
  exit 1
fi
if [ -n "$RESUME" ]; then
  [ -d "$RUN" ] || { echo "no run folder $RUN to resume"; exit 1; }
  rm -f "$RUN/DONE" "$RUN/STOP_SAMPLER" "$RUN"/*/exit_code
else
  [ -e "$RUN" ] && { echo "$RUN already exists: pick another --name, or --resume $NAME"; exit 1; }
  mkdir -p "$RUN"
fi
for k in "${KEYS[@]}"; do mkdir -p "$RUN/${COURSE_ID[$k]}"; done
other_gpu="$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader | grep -v vllm || true)"
[ -z "$other_gpu" ] || echo "! other processes on the GPU (they take memory from vLLM): $other_gpu"

# ---------------------------------------------------------------------------------------------- run record
cp lir2_config.toml "$RUN/lir2_config.toml"
"$PY" - "$RUN" "$NAME" "$ONLY" "$COURSES" "${RESUME:-}" <<'EOF'
import json, subprocess, sys, time
from pathlib import Path
run, name, only, courses, resume = sys.argv[1:6]
p = Path(run) / "meta.json"
meta = json.loads(p.read_text()) if p.exists() else {}
sh = lambda *c: subprocess.run(c, capture_output=True, text=True).stdout.strip()
meta.setdefault("started", time.time())
meta.update({"name": name, "only": only or "all", "courses": courses.split(","),
             "git_commit": sh("git", "rev-parse", "--short", "HEAD"), "git_dirty": bool(sh("git", "status", "--porcelain")),
             "gpu": sh("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"),
             "vllm": sh(str(Path.home() / "vllm-venv/bin/python"), "-c", "import vllm; print(vllm.__version__)"),
             "host": sh("hostname"), "finished": None})
if resume:
    meta.setdefault("resumed", []).append(time.time())
p.write_text(json.dumps(meta, indent=1))
EOF

# ---------------------------------------------------------------------------------------------- control script
# Runs in the tmux "control" window: sampler -> server -> courses (each in its own window) -> stop -> report.
CTL="$RUN/control.sh"
{
  echo "#!/usr/bin/env bash"
  echo "set -u -o pipefail; cd '$HERE'"
  echo "HERE='$HERE'; RUN='$RUN'; PY='$PY'"
  cat <<'EOF'
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$RUN/control.log"; }
"$PY" run_monitor.py sample "$RUN" >> "$RUN/sampler.log" 2>&1 &
SAMPLER=$!
log "sampler started (pid $SAMPLER): GPU + vLLM metrics every 5 s -> server.csv"
log "starting the vLLM server (first start compiles kernels: a few minutes)"
if ! "$PY" serve_lir2.py 2>&1 | tee -a "$RUN/server_start.log"; then
  log "server failed to start: see logs/generator_server.log"; touch "$RUN/STOP_SAMPLER"; exit 1
fi
tmux new-window -d -t lir2:9 -n server "tail -n 200 -F '$HERE/logs/generator_server.log'"
EOF
  for k in "${KEYS[@]}"; do
    cid="${COURSE_ID[$k]}"
    args="--lecture ${DATASET[$k]} --slots 0-127 --run-dir '$RUN/$cid'"
    [ -n "$ONLY" ] && args="$args --only $ONLY"
    echo "log 'starting $cid'"
    echo "tmux new-window -d -t lir2 -n $k \"cd '$HERE' && '$PY' generate_lir2.py $args 2>'$RUN/$cid/stderr.log'; echo \\\$? > '$RUN/$cid/exit_code'; echo; echo '$k finished (exit '\\\$(cat '$RUN/$cid/exit_code')'). This window stays open.'; [ \\\$(cat '$RUN/$cid/exit_code') = 0 ] || tail -n 40 '$RUN/$cid/stderr.log'; exec bash\""
  done
  cat <<EOF
log "waiting for: ${KEYS[*]}"
for cid in $(for k in "${KEYS[@]}"; do printf '%s ' "${COURSE_ID[$k]}"; done); do
  while [ ! -f "\$RUN/\$cid/exit_code" ]; do sleep 10; done
  log "\$cid finished, exit \$(cat "\$RUN/\$cid/exit_code")"
done
EOF
  cat <<'EOF'
log "stopping the vLLM server"
"$PY" serve_lir2.py --stop >> "$RUN/control.log" 2>&1
sleep 6; touch "$RUN/STOP_SAMPLER"; wait "$SAMPLER" 2>/dev/null
"$PY" - "$RUN" <<'PY'
import json, sys, time
from pathlib import Path
p = Path(sys.argv[1]) / "meta.json"; m = json.loads(p.read_text()); m["finished"] = time.time()
p.write_text(json.dumps(m, indent=1))
PY
log "writing the report"
"$PY" run_report.py "$RUN" 2>&1 | tee -a "$RUN/control.log"
touch "$RUN/DONE"
log "done: $RUN/report.md"
EOF
} > "$CTL"
chmod +x "$CTL"
if [ -n "$DRY" ]; then echo "dry run: $CTL written, nothing started"; exit 0; fi

# ---------------------------------------------------------------------------------------------- tmux
tmux new-session -d -s "$SESSION" -n dashboard -x "$(tput cols 2>/dev/null || echo 200)" -y "$(tput lines 2>/dev/null || echo 50)" \
  "'$PY' run_monitor.py dash '$RUN'; exec bash"
tmux set-option -t "$SESSION" -g mouse on >/dev/null
tmux set-option -t "$SESSION" -g history-limit 50000 >/dev/null
tmux set-option -t "$SESSION" status-style "bg=colour235,fg=colour245" >/dev/null           # dark status bar
tmux set-option -t "$SESSION" window-status-current-style "bg=colour238,fg=colour252" >/dev/null
tmux new-window -d -t "$SESSION:1" -n control "bash '$CTL'; exec bash"
echo "Run $NAME started in tmux session '$SESSION' (windows: dashboard, control, ${KEYS[*]}, server)."
echo "Files: $RUN"
if [ -n "$ATTACH" ] && [ -t 1 ]; then
  exec tmux attach -t "$SESSION"
else
  echo "Attach with:  tmux attach -t $SESSION"
fi
