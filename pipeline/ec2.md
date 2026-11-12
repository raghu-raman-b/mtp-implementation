# Model servers on the EC2

The pipeline, its outputs and the LLM caches stay on the local PC. The EC2 only serves the models:

| Model | Config | Port | Used for |
|---|---|---|---|
| Qwen 3.8 27B FP8 | `configs/qwen38_27b_vllm.json` | 8094 | writing: 2a, 2b rewrite, 2c, definitions, goals |
| Sage-A1.5 FP8 | `configs/sage_a15_vllm.json` | 8095 | judging: 2b judge |

The same config file is used on both sides. On the EC2 `scripts/llm/serve.py` starts the server from it; on the local
PC the stages attach to it through an SSH port forward. So the model name, sampling and thinking settings the
requests use always match the server, and the request hashes (and with them the caches) do not depend on where the
model runs.

The commands below run from the repository root on the local PC. The SSH host is `mtp` (in `~/.ssh/config`).

## Once per instance (and after every stop and start)

Copy the server side (the setup script, the LLM package, the configs, and the Hugging Face token if there is one),
then run the setup in tmux, so a dropped SSH connection does not stop it:

```bash
rsync -a --exclude __pycache__ -R pipeline/./setup_ec2.sh pipeline/./scripts/__init__.py pipeline/./scripts/llm \
      pipeline/./configs mtp:pipeline/
[ -f pipeline/.hf_token ] && rsync -a pipeline/.hf_token mtp:pipeline/
ssh mtp "mkdir -p pipeline/output/logs && tmux new -d -s setup 'bash ~/pipeline/setup_ec2.sh 2>&1 | tee ~/pipeline/output/logs/setup.log'"
ssh mtp tail -f pipeline/output/logs/setup.log          # Ctrl-C leaves the setup running
```

The setup installs vLLM, downloads both models and the embedding model, and ends with a smoke test (one request to
Qwen; `SMOKE=sage` for the judge). The model cache is on the instance's NVMe, which a stop wipes: after a start, run
the setup again (the downloads take most of its time).

Copy again whenever a config or `scripts/llm/` changes (the first `rsync` line).

## Start a server

One server at a time: each config gives vLLM 92% of the GPU. The server runs in a tmux session named after it:

```bash
ssh mtp "tmux new -d -s qwen 'cd ~/pipeline && python3 -m scripts.llm.serve configs/qwen38_27b_vllm.json'"
ssh mtp tail -f pipeline/output/logs/llm_server_8094.log   # ready when "Application startup complete" appears
```

Qwen loads in about 1 minute once its weights are in the page cache (5 minutes cold), Sage in about 5 (measured on
2026-11-12, RTX PRO 6000 Blackwell, 95 GB).

## Forward the ports

```bash
ssh -f -N -L 8094:127.0.0.1:8094 -L 8095:127.0.0.1:8095 mtp
ss -ltn | grep -E ":(8094|8095) "           # both listening
curl -s localhost:8095/v1/models            # answers once the server is up
```

Both ports are forwarded at once; only the one with a running server answers. The `mtp` entry in `~/.ssh/config`
also forwards port 8000: when another SSH session already holds it, ssh warns and still opens 8094 and 8095 (so no
`ExitOnForwardFailure`). Do not add `-o ClearAllForwardings=yes` here: it clears the `-L` forwards as well. Stop the
forward with `pkill -f "ssh -f -N -L 8094"`.

## Swap models

Stop the running server (Ctrl-C in its tmux session stops vLLM and frees the GPU), then start the other:

```bash
ssh mtp "tmux send-keys -t qwen C-c"
ssh mtp "while tmux has-session -t qwen 2>/dev/null; do sleep 2; done; nvidia-smi --query-gpu=memory.used --format=csv"
ssh mtp "tmux new -d -s sage 'cd ~/pipeline && python3 -m scripts.llm.serve configs/sage_a15_vllm.json'"
```

`tmux kill-session -t qwen` works as well (`serve.py` stops vLLM on the hang-up signal).

## Run a stage from the local PC

The two configs attach only (`"launch": false`): a stage never starts a model here. When no server answers, it waits
up to `attach_wait_s` (30 min) and says so every minute; when the port serves another model, it stops at once
(otherwise that model's answers would be cached under this config's hash).

```bash
cd pipeline
python3 scripts/s2a_fact_extraction.py nptel_vr --llm configs/qwen38_27b_vllm.json --only 1,4,16
python3 scripts/s2b_verify_facts.py nptel_vr --llm configs/qwen38_27b_vllm.json --judge configs/sage_a15_vllm.json --only 1,4,16
```

2b judges with Sage first, then rewrites with Qwen: start Sage, and when the log says
`waiting for qwen3.8-27b-fp8`, swap to Qwen (above). Answers already in a cache are never sent, so a rerun only calls
the model for what is missing. The plumbing of all this is tested without a model by `python3 tests/fake_run.py`
(fake servers on the same ports: stop the forward first).

## Run the stages on the EC2 (the queue)

Since 2026-11-12 the long runs go through a queue on the EC2, so they go on when the local session stops. The whole
pipeline folder is copied over (code, prompts, configs, course inputs without the videos, outputs and caches):

```bash
rsync -a --exclude __pycache__ --exclude 'input/*/media' --exclude 'output/logs' --exclude '.hf_token' pipeline/ mtp:pipeline/
ssh mtp "cd pipeline && tmux new -d -s queue 'bash ~/pipeline/ec2_queue.sh'"     # once; it keeps running
ssh mtp "echo 'qwen python3 -u scripts/s2c_concepts.py nptel_vr --llm configs/qwen38_27b_vllm.json --only 1,4,16' >> pipeline/queue/jobs.txt"
ssh mtp tail -f pipeline/queue/queue.log
```

`ec2_queue.sh` runs `queue/jobs.txt` line by line (`<qwen|sage|none> <command>`), starting the server each job needs
and stopping the other; done jobs go to `queue/done.txt`, logs to `queue/logs/<line>.log`. A failed job stops the queue
until `touch queue/resume` (skip it) or `touch queue/retry`. Copy the code again before queueing a job that needs a
change (the first `rsync` line; it never touches the EC2's logs).

The local tmux session `mtp` has a window `sync` that copies the EC2's `output/` and `queue/` into `ec2_sync/` (in the
repository, gitignored) every 5 minutes, so nothing is lost if the instance goes. Results are merged into
`pipeline/output/` and committed from there.

## Server logs

The server logs stay on the EC2 (`~/pipeline/output/logs/llm_server_<port>.log`). Copy them back into their own folder,
so they never overwrite the local logs of earlier runs:

```bash
mkdir -p pipeline/output/logs/ec2 && rsync -a "mtp:pipeline/output/logs/" pipeline/output/logs/ec2/
```
