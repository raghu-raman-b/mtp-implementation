#!/usr/bin/env bash
# Full LIR v2.1 run: one or more model setups one after another, each course in turn, a live dashboard, and a stats
# report per setup at the end.
#
#   bash run_v2.sh --setups small,large --courses vr     # today's run: VR on Gemma E4B + 12B, then on Qwen 27B
#   bash run_v2.sh                                       # large setup, VR then Deep Learning
#   bash run_v2.sh --name full-1 --only 1-3              # choose the run folder name; some lectures only
#   bash run_v2.sh --resume full-1 --setups small,large  # continue a stopped run: cached answers are not resent
#
# Setups: small = lir2_config_small.toml (Gemma 4 E4B writes, Gemma 4 12B verifies and judges, two vLLM servers),
#         large = lir2_config.toml (Qwen 3.8 27B for everything, one vLLM server). Same pipeline, so the outputs
#         can be compared. Courses run one at a time (the whole GPU for one course).
#
# Everything a run writes stays in runs/<name>/<setup>/, so earlier runs, v1 (lir/, output/) and lir-v2/ are untouched:
#   runs/<name>/<setup>/report.md, charts/    run stats and outputs, with graphs (run_report.py)
#   runs/<name>/<setup>/<course>/lir/         the LIR (course.json, Lxx.json, activities/, decisions.jsonl, ...)
#   runs/<name>/<setup>/<course>/build/       answer cache, step outputs, calls.jsonl (every request), report.md
#   runs/<name>/<setup>/server.csv            GPU and vLLM metrics every 5 s
#   runs/<name>/<setup>/meta.json, config.toml, *.log
#
# It opens a tmux session "lir2" (a dashboard per setup, a control window, a window per course and per server log).
# Ctrl-b d detaches; the run keeps going. tmux attach -t lir2 comes back.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
PY="$HERE/.venv/bin/python"
SESSION=lir2

NAME="v2-$(date +%Y%m%d-%H%M)"; ONLY=""; COURSES="vr,dl"; SETUPS="large"; RESUME=""; ATTACH=1; DRY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --courses) COURSES="$2"; shift 2 ;;
    --setups) SETUPS="$2"; shift 2 ;;
    --resume) NAME="$2"; RESUME=1; shift 2 ;;
    --no-attach) ATTACH=""; shift ;;
    --dry-run) DRY=1; shift ;;          # write runs/<name>/control.sh and stop (nothing is started)
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "unknown option $1 (see --help)"; exit 1 ;;
  esac
done

declare -A DATASET=([vr]="../dataset/virtual_and_augmented_reality" [dl]="../dataset/mit_6_7960_deep_learning")
declare -A COURSE_ID=([vr]="nptel-virtual-and-augmented-reality" [dl]="mit-6-7960-deep-learning")
declare -A CONFIG=([small]="lir2_config_small.toml" [large]="lir2_config.toml")
IFS=, read -ra KEYS <<< "$COURSES"
IFS=, read -ra SETS <<< "$SETUPS"
for k in "${KEYS[@]}"; do [ -n "${DATASET[$k]:-}" ] || { echo "unknown course '$k' (vr, dl)"; exit 1; }; done
for s in "${SETS[@]}"; do [ -n "${CONFIG[$s]:-}" ] || { echo "unknown setup '$s' (small, large)"; exit 1; }; done

BASE="$HERE/runs/$NAME"
# ---------------------------------------------------------------------------------------------- checks
[ -x "$PY" ] || { echo "no pipeline venv: run  bash setup_ec2.sh  first"; exit 1; }
[ -x "$HOME/vllm-venv/bin/vllm" ] || { echo "no vLLM: run  bash setup_ec2.sh  first"; exit 1; }
[ -n "$DRY" ] || command -v tmux >/dev/null || { echo "tmux is not installed (sudo apt-get install tmux)"; exit 1; }
if [ -z "$DRY" ] && tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "a run is already open in tmux session '$SESSION':  tmux attach -t $SESSION   (or tmux kill-session -t $SESSION)"
  exit 1
fi
if [ -n "$RESUME" ]; then
  [ -d "$BASE" ] || { echo "no run folder $BASE to resume"; exit 1; }
else
  [ -e "$BASE" ] && { echo "$BASE already exists: pick another --name, or --resume $NAME"; exit 1; }
fi
mkdir -p "$BASE"
other_gpu="$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader | grep -v vllm || true)"
[ -z "$other_gpu" ] || echo "! other processes on the GPU (they take memory from vLLM): $other_gpu"

# ---------------------------------------------------------------------------------------------- run records
for s in "${SETS[@]}"; do
  RUN="$BASE/$s"
  mkdir -p "$RUN"
  rm -f "$RUN/DONE" "$RUN/STOP_SAMPLER" "$RUN"/*/exit_code
  for k in "${KEYS[@]}"; do mkdir -p "$RUN/${COURSE_ID[$k]}"; done
  cp "${CONFIG[$s]}" "$RUN/config.toml"
  "$PY" - "$RUN" "$NAME/$s" "$ONLY" "$COURSES" "${RESUME:-}" "${CONFIG[$s]}" <<'EOF'
import json, subprocess, sys, time
from pathlib import Path
run, name, only, courses, resume, config = sys.argv[1:7]
p = Path(run) / "meta.json"
meta = json.loads(p.read_text()) if p.exists() else {}
sh = lambda *c: subprocess.run(c, capture_output=True, text=True).stdout.strip()
meta.update({"name": name, "only": only or "all", "courses": courses.split(","), "config": config,
             "git_commit": sh("git", "rev-parse", "--short", "HEAD"), "git_dirty": bool(sh("git", "status", "--porcelain")),
             "gpu": sh("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"),
             "vllm": sh(str(Path.home() / "vllm-venv/bin/python"), "-c", "import vllm; print(vllm.__version__)"),
             "host": sh("hostname"), "finished": None})
if resume:
    meta.setdefault("resumed", []).append(time.time())
p.write_text(json.dumps(meta, indent=1))
EOF
done

# ---------------------------------------------------------------------------------------------- control script
# Runs in the tmux "control" window, setup by setup: sampler -> servers -> courses one at a time -> stop -> report.
CTL="$BASE/control.sh"
{
  echo "#!/usr/bin/env bash"
  echo "set -u -o pipefail; cd '$HERE'"
  echo "HERE='$HERE'; BASE='$BASE'; PY='$PY'"
  cat <<'EOF'
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$BASE/control.log"; }
stamp() { "$PY" - "$1" "$2" <<'PY'
import json, sys, time
from pathlib import Path
p = Path(sys.argv[1]) / "meta.json"; m = json.loads(p.read_text())
if sys.argv[2] == "started": m["started"] = m.get("started") or time.time()
else: m["finished"] = time.time()
p.write_text(json.dumps(m, indent=1))
PY
}
EOF
  first=1
  for s in "${SETS[@]}"; do
    RUN="$BASE/$s"; CFG="${CONFIG[$s]}"
    echo "setup_$s() {"
    echo "RUN='$RUN'; CFG='$CFG'"
    echo "log '== setup $s ($CFG)'; stamp \"\$RUN\" started"
    echo "\"\$PY\" run_monitor.py sample \"\$RUN\" >> \"\$RUN/sampler.log\" 2>&1 & SAMPLER=\$!"
    if [ -z "$first" ]; then
      echo "tmux new-window -d -t lir2 -n dash-$s \"'\$PY' run_monitor.py dash '\$RUN'; exec bash\""
    fi
    first=""
    cat <<'EOF'
log "starting the vLLM server(s) for $CFG (the first start compiles kernels: a few minutes)"
if ! "$PY" serve_lir2.py --config "$CFG" 2>&1 | tee -a "$RUN/server_start.log"; then
  log "server failed to start: see logs/*_server.log"; touch "$RUN/STOP_SAMPLER"; return 1
fi
EOF
    echo "tmux new-window -d -t lir2 -n log-$s \"tail -n 200 -F '$HERE/logs/generator_server.log' '$HERE/logs/verifier_server.log'\""
    for k in "${KEYS[@]}"; do
      cid="${COURSE_ID[$k]}"
      args="--lecture ${DATASET[$k]} --config $CFG --keep-server --run-dir '$RUN/$cid'"
      [ -n "$ONLY" ] && args="$args --only $ONLY"
      echo "log 'starting $s / $cid'"
      echo "tmux new-window -d -t lir2 -n $s-$k \"cd '$HERE' && '$PY' generate_lir2.py $args 2>'$RUN/$cid/stderr.log'; echo \\\$? > '$RUN/$cid/exit_code'; echo; echo '$s / $k finished (exit '\\\$(cat '$RUN/$cid/exit_code')'). This window stays open.'; [ \\\$(cat '$RUN/$cid/exit_code') = 0 ] || tail -n 40 '$RUN/$cid/stderr.log'; exec bash\""
      echo "while [ ! -f '$RUN/$cid/exit_code' ]; do sleep 10; done"
      echo "log \"$s / $cid finished, exit \$(cat '$RUN/$cid/exit_code')\""
    done
    cat <<'EOF'
log "stopping the vLLM server(s)"
"$PY" serve_lir2.py --config "$CFG" --stop >> "$BASE/control.log" 2>&1
sleep 6; touch "$RUN/STOP_SAMPLER"; wait "$SAMPLER" 2>/dev/null
stamp "$RUN" finished
log "writing the report for $RUN"
"$PY" run_report.py "$RUN" 2>&1 | tee -a "$BASE/control.log"
touch "$RUN/DONE"
}
EOF
  done
  for s in "${SETS[@]}"; do echo "setup_$s || log 'setup $s failed; going on'"; done
  echo "log 'all done: $BASE'"
} > "$CTL"
chmod +x "$CTL"
if [ -n "$DRY" ]; then echo "dry run: $CTL written, nothing started"; exit 0; fi

# ---------------------------------------------------------------------------------------------- tmux
FIRST_RUN="$BASE/${SETS[0]}"
tmux new-session -d -s "$SESSION" -n "dash-${SETS[0]}" -x "$(tput cols 2>/dev/null || echo 200)" \
  -y "$(tput lines 2>/dev/null || echo 50)" "'$PY' run_monitor.py dash '$FIRST_RUN'; exec bash"
tmux set-option -t "$SESSION" -g mouse on >/dev/null
tmux set-option -t "$SESSION" -g history-limit 50000 >/dev/null
tmux set-option -t "$SESSION" status-style "bg=colour235,fg=colour245" >/dev/null           # dark status bar
tmux set-option -t "$SESSION" window-status-current-style "bg=colour238,fg=colour252" >/dev/null
tmux new-window -d -t "$SESSION:1" -n control "bash '$CTL'; exec bash"
echo "Run $NAME started in tmux session '$SESSION' (setups: ${SETS[*]}; courses: ${KEYS[*]}, one at a time)."
echo "Files: $BASE"
if [ -n "$ATTACH" ] && [ -t 1 ]; then
  exec tmux attach -t "$SESSION"
else
  echo "Attach with:  tmux attach -t $SESSION"
fi
