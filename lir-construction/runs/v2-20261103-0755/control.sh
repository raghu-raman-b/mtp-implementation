#!/usr/bin/env bash
set -u -o pipefail; cd '/home/ubuntu/mtp-implementation/lir-construction'
HERE='/home/ubuntu/mtp-implementation/lir-construction'; BASE='/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755'; PY='/home/ubuntu/mtp-implementation/lir-construction/.venv/bin/python'
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
setup_small() {
RUN='/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small'; CFG='lir2_config_small.toml'
log '== setup small (lir2_config_small.toml)'; stamp "$RUN" started
"$PY" run_monitor.py sample "$RUN" >> "$RUN/sampler.log" 2>&1 & SAMPLER=$!
log "starting the vLLM server(s) for $CFG (the first start compiles kernels: a few minutes)"
if ! "$PY" serve_lir2.py --config "$CFG" 2>&1 | tee -a "$RUN/server_start.log"; then
  log "server failed to start: see logs/*_server.log"; touch "$RUN/STOP_SAMPLER"; return 1
fi
tmux new-window -d -t lir2 -n log-small "tail -n 200 -F '/home/ubuntu/mtp-implementation/lir-construction/logs/generator_server.log' '/home/ubuntu/mtp-implementation/lir-construction/logs/verifier_server.log'"
log 'starting small / nptel-virtual-and-augmented-reality'
tmux new-window -d -t lir2 -n small-vr "cd '/home/ubuntu/mtp-implementation/lir-construction' && '/home/ubuntu/mtp-implementation/lir-construction/.venv/bin/python' generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --config lir2_config_small.toml --keep-server --run-dir '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality' 2>'/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/stderr.log'; echo \$? > '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/exit_code'; echo; echo 'small / vr finished (exit '\$(cat '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/exit_code')'). This window stays open.'; [ \$(cat '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/exit_code') = 0 ] || tail -n 40 '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/stderr.log'; exec bash"
while [ ! -f '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/exit_code' ]; do sleep 10; done
log "small / nptel-virtual-and-augmented-reality finished, exit $(cat '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/small/nptel-virtual-and-augmented-reality/exit_code')"
log "stopping the vLLM server(s)"
"$PY" serve_lir2.py --config "$CFG" --stop >> "$BASE/control.log" 2>&1
sleep 6; touch "$RUN/STOP_SAMPLER"; wait "$SAMPLER" 2>/dev/null
stamp "$RUN" finished
log "writing the report for $RUN"
"$PY" run_report.py "$RUN" 2>&1 | tee -a "$BASE/control.log"
touch "$RUN/DONE"
}
setup_large() {
RUN='/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large'; CFG='lir2_config.toml'
log '== setup large (lir2_config.toml)'; stamp "$RUN" started
"$PY" run_monitor.py sample "$RUN" >> "$RUN/sampler.log" 2>&1 & SAMPLER=$!
tmux new-window -d -t lir2 -n dash-large "'$PY' run_monitor.py dash '$RUN'; exec bash"
log "starting the vLLM server(s) for $CFG (the first start compiles kernels: a few minutes)"
if ! "$PY" serve_lir2.py --config "$CFG" 2>&1 | tee -a "$RUN/server_start.log"; then
  log "server failed to start: see logs/*_server.log"; touch "$RUN/STOP_SAMPLER"; return 1
fi
tmux new-window -d -t lir2 -n log-large "tail -n 200 -F '/home/ubuntu/mtp-implementation/lir-construction/logs/generator_server.log' '/home/ubuntu/mtp-implementation/lir-construction/logs/verifier_server.log'"
log 'starting large / nptel-virtual-and-augmented-reality'
tmux new-window -d -t lir2 -n large-vr "cd '/home/ubuntu/mtp-implementation/lir-construction' && '/home/ubuntu/mtp-implementation/lir-construction/.venv/bin/python' generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --config lir2_config.toml --keep-server --run-dir '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality' 2>'/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/stderr.log'; echo \$? > '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/exit_code'; echo; echo 'large / vr finished (exit '\$(cat '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/exit_code')'). This window stays open.'; [ \$(cat '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/exit_code') = 0 ] || tail -n 40 '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/stderr.log'; exec bash"
while [ ! -f '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/exit_code' ]; do sleep 10; done
log "large / nptel-virtual-and-augmented-reality finished, exit $(cat '/home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755/large/nptel-virtual-and-augmented-reality/exit_code')"
log "stopping the vLLM server(s)"
"$PY" serve_lir2.py --config "$CFG" --stop >> "$BASE/control.log" 2>&1
sleep 6; touch "$RUN/STOP_SAMPLER"; wait "$SAMPLER" 2>/dev/null
stamp "$RUN" finished
log "writing the report for $RUN"
"$PY" run_report.py "$RUN" 2>&1 | tee -a "$BASE/control.log"
touch "$RUN/DONE"
}
setup_small || log 'setup small failed; going on'
setup_large || log 'setup large failed; going on'
log 'all done: /home/ubuntu/mtp-implementation/lir-construction/runs/v2-20261103-0755'
