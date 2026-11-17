# The learner demo on a cloud GPU instance

Two ways to run it:

- **A. Model on the instance, everything else on the laptop (demo day, Windows laptop).** The GPU instance only
  serves the model (llama.cpp or vLLM, chosen at start) and the query embedder; the viewer, the question box's tool
  loop and the videos run on the laptop, which reaches the instance through an SSH tunnel. Scripts:
  `demo/ec2_model_server.sh` (instance), `demo/setup_windows.ps1` and `demo/run_demo.ps1` (laptop), both calling
  `python -m demo` (`demo/launcher.py`, the same on Windows, Linux and macOS). Section A below.
- **B. Everything on the instance** (the viewer too; the laptop only opens a browser through the forward):
  `demo/setup_demo.sh`, checked by `demo/check_demo.sh`. Section B below, unchanged.

## A. Model on the instance, viewer on the laptop

```
 laptop (Windows)                                         GPU instance (no open port but SSH)
 browser -> viewer/serve.py :8765  (videos, layers)
            qa tool loop (tools, citations) --ssh -L 8096--> llama-server or vLLM :8096  (Gemma 4 12B)
            fact search ---------------------ssh -L 8097--> demo/embed_server.py :8097 (Qwen3-Embedding-0.6B)
```

| Piece | Where | Why there |
|---|---|---|
| Gemma 4 12B: llama.cpp (`unsloth/gemma-4-12B-it-qat-GGUF` Q4, 7.5 GB, the PC's exact file and flags) or vLLM (`google/gemma-4-12B-it` BF16, needs 40 GB+ GPU and the HF token) | instance, tmux `model`, 127.0.0.1:8096 | the GPU |
| Query embedder Qwen3-Embedding-0.6B (sentence-transformers, as the layer was embedded) | instance, tmux `embed`, 127.0.0.1:8097 | the laptop then needs no torch and no 1.2 GB model, and the first question does not wait 10-20 s for it to load. Vectors checked equal: cosine >= 0.999 against `fact_embeddings.json` (`python -m demo check`) |
| viewer, qa (tools, citations, the layer), videos | laptop | the videos (5.5 GB) and every page load stay local; only the model's requests cross the network |

Speed (measured through a simulated 250 ms tunnel, `analysis/demo/remote_setup.md`): the page shows progress at
once (a `round` event, then `thinking`, `call`, `step` with a display line), and the answer streams as it is
written. Over the tunnel each new TCP connection costs a round trip (a new SSH channel), so qa keeps its connections
to both servers open and warm (`scripts/llm/http_pool.py`); on llama.cpp all rounds of a question go to one server
slot, so each round reuses the KV cache of the one before (`cache_prompt`, `id_slot`); vLLM caches prefixes itself.
At start the instance script sends two warm-up requests, and the viewer's warm-up sends the real system prompt and
tools once (so the first question finds them cached) and reaches the embedder.

### A1. The instance (once per start; about 20 min the first time, 2-3 min after)

Start it as in B1 below (Deep Learning Base OSS Nvidia Driver AMI, Ubuntu 24.04; security group: SSH only). Any
NVIDIA GPU with 16 GB or more runs llama.cpp; vLLM serves the BF16 checkpoint and needs 40 GB or more (an L40S, an
A100, the RTX PRO 6000) and a Hugging Face token with access to `google/gemma-4-12B-it`.

**From the laptop (Windows PowerShell, in the repository folder)**: copies the ~150 kB the instance needs (the
scripts, the configs, `scripts/llm`, `prompts/qa_tools.json`, and `pipeline/.hf_token` if you have one) and runs the
setup there in tmux, showing its output:

```powershell
powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1 -Push -Engine llamacpp   # or -Engine vllm
```

(Linux/macOS: `cd pipeline && python -m demo push --instance ubuntu@<ip> --key ~/demo.pem --engine llamacpp`.)

**Or on the instance itself** (the repository cloned or copied as in B2, or the bundle above):

```bash
bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --engine llamacpp     # or --engine vllm; no flag: it asks
bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --status              # what answers, and the tunnel command
bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --stop                # both servers
```

It installs only what the engine needs (llama.cpp: build tools and the llama-server build for this GPU; vLLM: a
`~/vllm-venv` with vLLM), plus `~/demo-venv` for the downloads and the embedder (torch, sentence-transformers),
downloads the model and the embedder to the local NVMe, starts the two servers in tmux, waits for both, warms the
model up and prints the tunnel command. Rerunning reuses everything; switching engine stops the other one first.
Options are at the top of the script (`--no-embed`, `TORCH_CPU=1`, `LLAMA_REF=master`, `VLLM_PKG=...`).

### A2. The laptop (once)

1. Python 3.12: `winget install -e --id Python.Python.3.12` (or python.org; tick "Add to PATH"). Open a new terminal.
2. The repository: `git clone --depth 1 --filter=blob:none --sparse https://github.com/raghu-raman-b/mtp-implementation.git`,
   then `cd mtp-implementation; git sparse-checkout set pipeline` (about 330 MB; or copy the folder over).
3. The videos: copy `pipeline/input/nptel_vr/media/` (L01.mp4 ..., 5.5 GB) to the laptop, anywhere. Without them,
   lectures play from YouTube (the laptop then needs internet for the videos).
4. Setup (a venv in `%USERPROFILE%\mtp-demo-venv` with numpy only; the settings go to `pipeline\demo\local.json`):

```powershell
powershell -ExecutionPolicy Bypass -File pipeline\demo\setup_windows.ps1 -Instance ubuntu@<ip> -Key C:\keys\demo.pem -Media D:\demo\media
```

   It narrows the key's permissions to you (Windows OpenSSH refuses a key others can read) and checks Python, numpy,
   ssh, the key, the videos and the course layer. `-LocalEmbed` installs the embedder on the laptop instead (torch CPU
   and sentence-transformers, ~1 GB) for an instance started with `--no-embed`.

### A3. Demo day

```powershell
powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1
```

It opens the tunnel (`ssh -N -L 8096:127.0.0.1:8096 -L 8097:127.0.0.1:8097 ubuntu@<ip>`, reopened when it drops),
waits for the model server (it may still be loading), finds the engine from the served model name, starts the viewer
(`viewer/serve.py --warm`, with `QA_CONFIG` = that engine's demo config pointed at the tunnel, `QA_EMBED_URL` = the
embedder's tunnel), waits until qa is warm, and opens the browser at http://127.0.0.1:8765/. Ctrl+C stops the viewer
and the tunnel. In a second window:

```powershell
powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1 -Check    # PASS/FAIL lines, ALL PASS at the end
powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1 -Bench    # the DEMO_PLAN questions, timed
```

To open the tunnel by hand instead (any terminal; leave it running), then start with `python -m demo run --no-tunnel`:

```
ssh -N -o ServerAliveInterval=15 -o ExitOnForwardFailure=yes -i C:\keys\demo.pem -L 8096:127.0.0.1:8096 -L 8097:127.0.0.1:8097 ubuntu@<ip>
```

### A4. When something fails

- **"UNPROTECTED PRIVATE KEY FILE"**: rerun setup_windows.ps1 with `-Key` (it fixes the permissions), or
  `icacls key.pem /inheritance:r /grant:r "%USERNAME%:R"`.
- **"running scripts is disabled on this system"**: start the scripts with `powershell -ExecutionPolicy Bypass -File ...`
  as above (nothing is changed system-wide).
- **The launcher waits for the model server**: on the instance, `bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --status`,
  `tmux attach -t model`. A port 8096 already used on the laptop: `run_demo.ps1` stops; `python -m demo run --model-port 18096`.
- **"no embedder"**: the instance was started with `--no-embed` or `tmux attach -t embed` shows an error. Either
  start it again without `--no-embed`, or `setup_windows.ps1 -LocalEmbed` and `run_demo.ps1 -LocalEmbed`.
- **Answers fail or hang**: the viewer's output in the run_demo window; `run_demo.ps1 -Check`.
- The instance's engine changed (llama.cpp <-> vLLM): just restart `run_demo.ps1`; it reads the engine from the server.

### A5. Files

| File | What |
|---|---|
| `demo/ec2_model_server.sh` | the instance: `--engine llamacpp|vllm`, `--status`, `--stop` |
| `demo/embed_server.py` | the query embedder over HTTP (OpenAI `/v1/embeddings`, base64 float32), 127.0.0.1:8097 |
| `demo/launcher.py` (`python -m demo`) | the laptop: `setup`, `run`, `check`, `bench`, `push`, `tunnel` |
| `demo/setup_windows.ps1`, `demo/run_demo.ps1` | Windows wrappers of the launcher (venv, settings, start) |
| `demo/requirements-local.txt` (numpy), `demo/requirements-local-embed.txt` | the laptop's packages |
| `demo/local.json` | the laptop's settings (instance, key, videos; gitignored) |
| `scripts/llm/http_pool.py` | kept-open connections to the model server and the embedder |
| `schemas/qa_stream.md` | the events of `/api/ask_stream` (what the chat screen shows while the model works) |

## B. Everything on the instance

The viewer (`viewer/serve.py`) and its question box (`qa/`, Gemma 4 12B on llama.cpp, the query embedder on the CPU)
run on one GPU instance. You reach the viewer from your laptop through an SSH port forward. One script sets it all up:
`demo/setup_demo.sh`. Another checks it: `demo/check_demo.sh`.

What runs on the instance:

| Piece | Where | tmux session |
|---|---|---|
| Gemma 4 12B QAT (`unsloth/gemma-4-12B-it-qat-GGUF`, `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`) on `llama-server`, port 8096 | `configs/gemma4_12b_demo.json` | `gemma` |
| The viewer on 127.0.0.1:8765, with `QA_CONFIG=configs/gemma4_12b_demo.json`, warming `qa` at start | `viewer/serve.py --warm` | `viewer` |
| Query embedder Qwen3-Embedding-0.6B (CPU, inside the viewer process) | `~/demo-venv` | (none) |

**Why llama.cpp and not vLLM:** the local PC answers with this exact GGUF on llama.cpp. On the instance, the same
file, chat template, sampling and thinking budget (the demo config copies them from `configs/gemma4_12b_llamacpp.json`)
make the answers behave the same. vLLM would need another checkpoint of the model, and for one learner at a time it is
not faster. llama.cpp is also built at the commit the PC runs (`LLAMA_REF=master` builds the latest instead).

**Videos:** the videos (5.5 GB) are not in git. When a lecture's file is missing, the viewer plays that lecture from
YouTube instead, using the `youtube_id` in `titles.tsv`. Segment clicks, transcript clicks and citation links still
jump to the right moment. If the files are copied over (step 3), they are used instead.

### B. Steps

Expected times are for a g6.xlarge or g5.xlarge (4 vCPUs, one 24 GB GPU) with the Deep Learning AMI. They are
estimates until the first real run.

### B1. Start the instance (3 min)

- AMI: *Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 24.04)*. It has the NVIDIA driver, the CUDA toolkit
  (`nvcc`) and Python 3.12. `qa` needs Python 3.11 or newer, and the Ubuntu 22.04 AMI's `python3` is 3.10. On that AMI,
  install python3.12 and run the setup with `PYTHON=python3.12`.
- Type: any NVIDIA GPU with 16 GB or more works. The PC runs this on 12 GB. A g6.xlarge (L4) or g5.xlarge (A10G) is
  enough. A type with 8 vCPUs or more builds llama.cpp twice as fast. Both have a local NVMe, which the setup uses
  for the model cache.
- Root volume: 100 GB. Security group: SSH (22) only.
- On the PC, add the instance to `~/.ssh/config` as `demo` (HostName = its public IP, User ubuntu, IdentityFile =
  your key). The commands below use that name.

You can also use the pipeline's EC2 (`mtp`), but only with its vLLM server stopped: vLLM takes 93% of the GPU.

### B2. Copy the code and the course outputs (1-2 min, about 170 MB)

All the outputs the demo needs are in git: `output/nptel_vr/knowledge`, `activities`, and the stage folders. Choose
one of these.

**A. rsync from the PC** (from the repository root):

```bash
ssh demo mkdir -p mtp-implementation
rsync -a --exclude __pycache__ --exclude 'input/*/media' --exclude 'output/logs' --exclude 'output/*/qa' \
      --exclude 'demo/logs' --exclude '.hf_token' pipeline demo:mtp-implementation/
[ -f pipeline/.hf_token ] && rsync -a pipeline/.hf_token demo:mtp-implementation/pipeline/
```

**B. git clone on the instance.** The repository may be private: use a GitHub token with read access to its
contents. The full history is about 19 GB, so clone only the last commit and only `pipeline/`:

```bash
ssh demo
read -rs GH_TOKEN                     # paste the token (not saved in the shell history); public repo: skip it
git clone --depth 1 --filter=blob:none --sparse \
    "https://${GH_TOKEN:+$GH_TOKEN@}github.com/raghu-raman-b/mtp-implementation.git"
cd mtp-implementation && git sparse-checkout set pipeline
git remote set-url origin https://github.com/raghu-raman-b/mtp-implementation.git   # the token leaves .git/config
```

(Add `--branch <name>` to clone a branch that is not merged into main yet.) The models are public, so no Hugging Face
token is needed. If you have one, copy `pipeline/.hf_token` as in A.

### 3. Optional: the videos (5.5 GB; about 8 min at 100 Mbit/s upload)

Without the videos, lectures play from YouTube, so the laptop needs internet access. To use the files instead, run
this from the repository root on the PC. It can run while step 4 runs:

```bash
rsync -a --info=progress2 pipeline/input/nptel_vr/media/ demo:mtp-implementation/pipeline/input/nptel_vr/media/
```

The viewer finds them on the next page load, with no restart.

### 4. Run the setup (about 20 min the first time, 2 min on a rerun)

Run it in tmux so that a dropped SSH connection does not stop it:

```bash
ssh demo "tmux new -d -s setup 'bash ~/mtp-implementation/pipeline/demo/setup_demo.sh 2>&1 | tee ~/setup_demo.log'"
ssh demo tail -f setup_demo.log            # Ctrl-C stops watching; the setup keeps running
```

| Step | Time |
|---|---|
| 1-3 GPU check, model cache on the NVMe, token, system packages | 1 min |
| 4 venv: torch (CUDA wheels, ~3 GB) and sentence-transformers. The model downloads (7.5 + 1.2 GB) start in the background | 3-5 min |
| 5 llama.cpp `llama-server` built for this GPU (the CUDA architecture comes from `nvidia-smi`) | 5-15 min |
| 6 wait for the downloads; set the demo config for this instance (binary, model file, slots by GPU memory) | 0-3 min |
| 7 videos: how many are here (the rest play from YouTube), and the rsync line | instant |
| 8 tmux `gemma` (model load) and `viewer` | 1 min |
| 9 two questions through the viewer (warm-up and test), printed with their citations and time | 1-2 min |

At the end it prints the SSH forward command and the URL. It is safe to rerun: what is done is skipped, a model that
is still loading is waited for, and the viewer is restarted (so it picks up new code). Options are listed at the top
of the script, e.g. `VIEWER_HOST=0.0.0.0` (open the port in the security group instead of forwarding it),
`TORCH_CPU=1` (CPU-only torch: about 3 GB less to download; the embedder runs on the CPU anyway), `LLAMA_REF=master`.

### 5. Forward the port and open the browser

On the PC (leave it running):

```bash
ssh -N -L 8765:127.0.0.1:8765 demo
```

Then open http://localhost:8765/. If a local viewer already uses 8765, run `-L 8766:127.0.0.1:8765` and open :8766.

### 6. Check (1 min)

```bash
ssh demo bash mtp-implementation/pipeline/demo/check_demo.sh
```

It prints one PASS/FAIL/SKIP line per item:

- the GPU, the venv packages, the llama-server binary, the model file and the embedder in the cache
- the tmux sessions
- the model server healthy and serving `gemma-4-12b-qat`
- the viewer's page, script, course, lecture and knowledge routes
- a Range request on lecture 4's video. This is SKIP when the file is not there and YouTube plays it.
- every lecture having a video (a file or YouTube)
- one question ("What is an HMD?") answered with citations, with its time

It ends with ALL PASS or the number failed. Run it again right before the demo.

### 7. Run the demo

Follow `continue/DEMO_PLAN.md`, the walk and the questions in order. Its "Before you start" changes on the instance:

- There is no activity run to stop: the GPU belongs to the demo.
- The viewer is already running. The setup asked "What is extended reality?", so the model and the embedder are warm.
- Keep developer mode off, the light theme, and full screen, as in the plan.
- Lectures without a video file play from YouTube. The first play may show YouTube's own controls. Citations still
  jump to the cited moment.

The setup prints the time of its two questions. Later answers take about as long as the second one. Long questions with
many parts are slower, because thinking is capped at 8192 tokens, the same as on the PC.

### 8. Stop

```bash
ssh demo "tmux kill-session -t viewer; tmux kill-session -t gemma"        # stops the servers (and llama-server)
```

Then stop the instance in the console (or `aws ec2 stop-instances --instance-ids <id>`). A stop wipes the local NVMe,
which holds the model cache. After a start, run step 4 again: about 5 min, since only the downloads repeat. The venv
and the llama.cpp build stay on the root volume. Terminate the instance when the demo is over, so the volume is not
billed.

The questions asked during the demo are logged on the instance in
`pipeline/output/nptel_vr/qa/answers.jsonl`. To keep them, copy them into the gitignored `ec2_sync/`:
`rsync -a demo:mtp-implementation/pipeline/output/nptel_vr/qa/ ec2_sync/demo_qa/`.

## When something fails

- **`nvcc not found`**: the AMI has no CUDA toolkit. Use the Deep Learning *Base OSS Nvidia Driver* AMI.
- **The llama.cpp build fails** (e.g. a newer CUDA than the pinned commit knows): `LLAMA_REF=master bash ...setup_demo.sh`.
  The log is `pipeline/demo/logs/llama_build.log`.
- **The model server does not start**: `tmux attach -t gemma`, and the server log `pipeline/demo/logs/llm_server_8096.log`.
- **Answers fail**: the viewer log `pipeline/demo/logs/viewer.log` (`tmux attach -t viewer`). Then run `check_demo.sh`.
- **"port 8765 is taken"**: another program listens there. Stop it, or use `VIEWER_PORT=8770 bash ...setup_demo.sh`.

## Files

| File | What |
|---|---|
| `demo/setup_demo.sh` | the setup (steps 1-9 above) |
| `demo/check_demo.sh` | the end-to-end check |
| `demo/demo_tool.py` | helpers for both (config, wait for the model, media count, ask, HTTP checks); standard library only |
| `configs/gemma4_12b_demo.json` | the demo config: the local Gemma config without the toolbox, with the instance's binary and model file, attach-only for `qa` (`launch: false`; `scripts/llm/serve.py` starts the server in tmux) |
| `demo/logs/` | the setup's logs (gitignored) |

`qa` takes its config from `$QA_CONFIG`, which the viewer session sets. Without it, `qa` uses the local
`configs/gemma4_12b_llamacpp.json`, as before.
