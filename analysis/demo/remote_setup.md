# Demo: model on the instance, viewer on the laptop (2026-11-17)

Branch `worktree-agent-a2f27effc18ce835b`. How to run it: `pipeline/demo/README.md`, section A. Event schema of the
answer stream: `pipeline/schemas/qa_stream.md`.

## The split

| Instance (GPU; only SSH open) | Laptop (Windows; or Linux/macOS) |
|---|---|
| model server on 127.0.0.1:8096: llama.cpp (Gemma 4 12B QAT GGUF, the PC's file and flags) or vLLM (`google/gemma-4-12B-it` BF16), chosen at start: `ec2_model_server.sh --engine llamacpp\|vllm` (or it asks) | `viewer/serve.py` (pages, layers, videos), qa's tool loop (tools, citations), started by `python -m demo run` (`run_demo.ps1`) |
| query embedder on 127.0.0.1:8097: `demo/embed_server.py` (Qwen3-Embedding-0.6B, sentence-transformers, as the layer was embedded) | `QA_CONFIG` = the engine's demo config with `url` = the tunnel; `QA_EMBED_URL` = the embedder's tunnel |
| tmux `model`, `embed`; warm-up requests at start | packages: numpy only (no torch, no 1.2 GB model) |

Connection: `ssh -N -L 8096:127.0.0.1:8096 -L 8097:127.0.0.1:8097 user@host` (the launcher opens it, with
ServerAliveInterval 15, ExitOnForwardFailure, and reopens it when it drops). The engine is read from the served
model name (`gemma-4-12b-qat` = llama.cpp, `gemma-4-12b` = vLLM), so the laptop needs no engine setting.

**Embedder on the instance: kept**, because the vectors are the same. Remote (embed_server) vectors of 24-51 fact
texts against `knowledge/fact_embeddings.json`: min cosine **0.99971-0.99977** (mean 0.99985; the server ran on
the PC's CPU, the layer was embedded elsewhere); a query embedded remotely and locally on the same device: cosine
1.0000000. `python -m demo check` repeats this on every run (threshold 0.999). With `--no-embed` on the instance and
`-LocalEmbed` on the laptop, the laptop embeds on its CPU instead.

## What changed for speed (and what each is worth through a 250 ms tunnel)

1. **The first sign of progress at once.** The stream now starts with a `round` event (t = 0.002 s), then `thinking`
   (every 0.5 s while the model thinks), `call` (before a tool runs), `step` (with a display line and details),
   `answer_start`, drafts, `done` (with timing). Before, nothing came until the first tool had run (2.5-5 s).
2. **Kept-open, pre-tested connections** (`scripts/llm/http_pool.py`). Over SSH every new TCP connection is a new
   channel: one round trip before the request leaves. Measured on the PC's llama-server: **it closes the connection
   after every streamed answer** (keep-alive only for plain ones; idle timeout 5 s), so plain keep-alive cannot
   help between rounds. The pool learns this, and its keep-warm thread opens and pings a spare connection as soon as
   a request takes one (in parallel with the model's answer). First byte of a 1-token streamed request through the
   simulated tunnel (median of 5-10):

   | | first round of a question (after 8 s idle) | later rounds (0.5 s after the previous) |
   |---|---|---|
   | before: a new connection per request (urllib) | 589 ms | 585 ms |
   | after: pool + keep-warm spare | **338 ms** | **316 ms** |

   One round trip saved per round: 2-3 rounds per question, 0.5-0.8 s per answer at 250 ms RTT. Same for the
   embedder's connection (one call per fact search). vLLM keeps connections after streams; its demo config now sets
   `VLLM_HTTP_TIMEOUT_KEEP_ALIVE=300`.
3. **One llama.cpp slot per question** (`id_slot`, the lowest slot idle in the last `/slots` answer) and
   `cache_prompt`. Measured on an untouched slot: round 0 of consecutive questions reuses 1891 of ~1905 prompt tokens
   (the system prompt and tools); round 1 reuses the 1889-token prefix and computes only the tool results. Round 1
   cannot reuse round 0's user message because thinking is switched off after round 0, which re-renders the turn
   after the system prompt; that costs about 25 tokens, so it is left as is (checked: 1915 tokens reused when the
   switch is not flipped, against 1889). Without pinning, a round sometimes landed on an empty slot and recomputed
   all of its 3,981 tokens (seen once this morning: 1.4 s on the PC). On the shared PC server, the other agent's qa
   requests (the same system prompt) were routed to slot 0 by prefix similarity and evicted it, so round 0 of the
   bench recomputed the prompt (`cache_n` 0): not an issue on a dedicated instance. `QA_PIN_SLOTS=0` turns pinning
   off.
4. **Warm-up.** Instance: two requests at start (a short one; one with the qa tools and thinking), 0.1-0.2 s and
   1.3-1.6 s. Laptop: `qa.warm()` loads the layer, reaches the embedder and the model through the tunnel, and sends
   the system prompt and tools once on the slot the first question will use. The launcher opens the browser only
   when `/api/qa_status` says ready: **warm in 5.5-7 s** (layer 0.5, embedder 1.1-1.7, model attach 1.0, prompt
   prefix 1.9-2.9 s), against 10 s before (the local embedder's load; 8.8 s for the model alone on the PC's CPU, and
   20-23 s for the first question without `--warm` in the DEMO_PLAN).
5. **Small things.** TCP_NODELAY on the viewer's answer stream (Windows delays small writes up to 200 ms otherwise)
   and on the pool's sockets; base64 float32 vectors from the embedder (5.5 kB per text instead of ~20 kB of JSON).

## End to end: the DEMO_PLAN questions through `/api/ask_stream`

Setup: the PC's RTX 5070 as the instance (Gemma 4 12B QAT on llama.cpp, the already-running server on port 8092)
and the embed server on the PC's CPU (the GPU was full). Each was reached through `analysis/viewer/tools/tunnel.py`
(250 ms RTT, 10 Mbit/s, one round trip per new connection, as an SSH channel). **Before** = the code at db10844
(a copy), its viewer with a local CPU embedder. **After** = this branch, started by `python -m demo run`. Each
question went to before, then to after (`python -m demo bench --url A --url B`), so both ran under the same load.

**Noise:** another agent was using the same model server throughout. Decode ran at 26-39 ms per token instead of
18, with its long requests in other slots. Its qa requests also took slot 0 (point 3), and both setups' CPU
embedders shared one CPU. Temperature is 1.0, so thinking length and answer length vary from run to run. Read the
per-question rows as noisy; the medians and the micro-measurements above are the solid part.

Seconds from sending the question (median over the questions; "start" = `answer_start`, new):

| run | setup | first event | first step | start | first words | done |
|---|---|---|---|---|---|---|
| A: 2 x 12 questions, heavier load (pool without the spare fix) | before | 4.99 | 4.91 | - | 8.13 | 14.45 |
| | after | **0.00** | 5.08 | 7.22 | **7.24** | **12.97** |
| B: 12 questions, lighter load (final code) | before | 2.50 | 2.50 | - | 4.20 | 8.08 |
| | after | **0.00** | 2.63 | 3.63 | **3.67** | 8.32 |

What it says: the learner now sees progress at once instead of after 2.5-5 s. The first words come 0.5-0.9 s
earlier (median). The time to the first step and to the end is set by the model (round-0 thinking, answer length
at 26-39 ms per token here). Under this shared load the 0.5-0.8 s the connections save per answer is within the
run-to-run spread. The step lines the chat screen gets, from run B: `Looked up "immersion": definition found, 21
facts from lectures 2, 6, 8, 9, 25 and 38`, `"Wizard of Oz" is not a concept of the course; the closest facts are in
lectures 42 and 59`, `Checked what lecture 9 builds on: revise lectures 4, 2 and 7`, `Searched the course for "Who won
the 2022 FIFA World Cup?": nothing close`.

`python -m demo check` against the after setup: ALL PASS (model through the tunnel 505 ms per health check, the
embedder's vectors min cosine 0.99977, "What is an HMD?" first event 0.00 s, first step 2.46 s, first words 4.19 s,
done 7.64 s, 4 citations).

## Not tested here (no instance, no Windows, no vLLM on the PC)

- vLLM: the config and request bodies only, against the fake OpenAI server (tests/fake_qa.py "vllm"); the instance
  script's vLLM branch (venv install, BF16 download, 40 GB check) has not run.
- `ec2_model_server.sh` ran on the PC as a stand-in: it found the running server, started the embedder in tmux,
  warmed up, printed the commands, and a rerun reused everything. Not run: apt, the llama.cpp build, the downloads,
  starting a model server (the PC's GPU was shared, so none was started).
- The PowerShell scripts were not run (no PowerShell here). They are ASCII only and carry little logic; the
  logic is in `python -m demo`, which was run on Linux: setup, run (tunnel restart, port fallback, warm wait, clean
  stop on a kill), check, bench, and push's bundle (LF line endings, the files the instance needs:
  tests/demo_remote.py).
- The embedder on the instance's GPU: run `python -m demo check` there (cosine >= 0.999 expected, as on the CPU).

## Checklist for the user

### On a real instance (from the laptop or the PC)

1. Start the instance (README B1). From the repository folder on Windows:
   `powershell -ExecutionPolicy Bypass -File pipeline\demo\setup_windows.ps1 -Instance ubuntu@<ip> -Key <key.pem> -Media <videos folder>`
   then `powershell -ExecutionPolicy Bypass -File pipeline\demo\run_demo.ps1 -Push -Engine llamacpp`.
   Expect the output to end with "== 8/8 ready", the two warm-up lines with HTTP 200, and a tool call
   `['check_concept']` on the second.
2. On the instance: `bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --status`: ports 8096 and 8097 answer.
   Rerun it: everything "kept"/"already", under a minute.
3. vLLM (on a 40 GB+ GPU, with the HF token in `pipeline/.hf_token`): `run_demo.ps1 -Push -Engine vllm`. Expect it to
   stop the llama.cpp server, install vLLM, download the BF16 model, and reach "ready" (first time 15-30 min). Then
   check that tool calls come back as tool calls: the second warm-up line shows `tool calls ['check_concept']`. If it
   shows characters instead, add `--chat-template` as in analysis/qa/STATE.md.

### On the Windows laptop

4. `run_demo.ps1`: the tunnel line, "model server: llamacpp" (or vllm), "embedder: ... on the instance (cuda)",
   "question answering warm in N s" (expect under 10 s), "Ready", and the browser opens at http://127.0.0.1:8765/.
5. In a second window, `run_demo.ps1 -Check`: ALL PASS. Note the line "embedder vectors equal the layer's": the min
   cosine with the GPU embedder must be >= 0.999.
6. `run_demo.ps1 -Bench`: the 12 DEMO_PLAN questions. On a dedicated instance expect first event ~0 s, first words
   2-4 s, done 4-10 s, all with citations except FIFA. To keep the numbers, use
   `python -m demo bench --warmup --out bench.jsonl` from `pipeline\` with the venv's python.
   `server_timing.rounds[0].cache_n` should be ~1890 from the second question on (the prompt prefix reused).
7. In the page: ask "What is an HMD?". Play a lecture with a local video (seek works) and one without (YouTube).
   Ctrl+C in the run window: the viewer and ssh both stop. Disconnect the network for a minute (ssh gives up after
   45 s without an answer), reconnect: the run window shows "opening it again" and the next question works.
8. Afterwards: `ec2_model_server.sh --stop` on the instance (or just stop the instance).

## Files

`pipeline/demo/ec2_model_server.sh`, `embed_server.py`, `launcher.py` (`python -m demo`), `setup_windows.ps1`,
`run_demo.ps1`, `requirements-local*.txt`, `README.md` (section A); `pipeline/scripts/llm/http_pool.py`;
`pipeline/qa/answer.py` (events, slots, warm), `qa/tools.py` (labels, details), `scripts/embed.py` (url);
`pipeline/viewer/serve.py` (`/api/qa_status`, TCP_NODELAY, done passthrough, UTF-8);
`pipeline/schemas/qa_stream.md`; tests: `tests/demo_remote.py` (new), `tests/fake_qa.py` (events), `tests/viewer_smoke.py`.
