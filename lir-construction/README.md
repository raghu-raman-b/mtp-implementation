# LIR construction

Turns a course's subtitle files into the Lecture Intermediate Representation described in
*Lecture planner: LIR and pipeline architecture*: one `course.json` plus one `Lxx.json` per lecture.

```bash
python3 generate_lir.py --lecture ../dataset/mit_6_7960_deep_learning            # every lecture
python3 generate_lir.py --lecture ../dataset/virtual_and_augmented_reality --only 1-3
```

`--lecture` is a course folder from `dataset/` (`subs/`, `transcripts/`, `titles.tsv`). Lectures are processed in
course order, because the course knowledge state of lecture k depends on lectures 1 to k-1. The script switches to
the project venv by itself, and starts and stops the model server in the `llm-engine` toolbox.

| Option | |
|---|---|
| `--only 1-3` / `--only 1,4,7` | lecture numbers to process (default: all) |
| `--config FILE` | model choices and API budget (default `lir_config.toml`) |
| `--lir-only` / `--videos-only` | build only the LIR, or only download the videos |
| `--no-judge` | skip the layer-3 judge |
| `--fresh` | ignore cached LLM answers |
| `--keep-server` | leave the local generator running for the next run |

## LIR v2.1 (in progress)

v2 rebuilds the LIR on stricter rules: every item cites sentences by address (`L05/S0412`), code checks only sources
and structure, the judge checks every item (one rewrite, then dropped), and every decision is logged with its reason.
It has two layers: the knowledge (parts, key points, key terms, a concept registry with canonical definitions, facets,
links, goals, lecture map) and the activities built on it (recall, quiz, summary, concept map, open questions, spaced
review). v2.1 merges the calls (one per part, window, registry group or lecture), caps thinking per step and runs each
part and lecture as soon as its inputs are ready. The full design, the outputs and the status of each step are in
`pipeline2/TASKS.md`.

```bash
python3 generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --only 1-10
python3 generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --config lir2_config_small.toml
python3 tests/smoke_pipeline2.py      # plumbing check with a fake model: no GPU, under a minute
```

Output: `lir-v2/<course>/` (`course.json`, `Lxx.json`, `activities/Lxx.json`, `decisions.jsonl`, `embeddings.json`;
schema in `lir2_schema.py`); build files and `report.md` (time per step, calls, judge pass rates, drops) in
`output/<course>/v2/`. The generator writes; the verifier runs the registry and the links; the judge checks every item
and rewrites failures once. Two setups run the same pipeline:

| Setup | Config | Writes | Verifies and judges |
|---|---|---|---|
| large | `lir2_config.toml` | Qwen 3.8 27B FP8 | the same server |
| small | `lir2_config_small.toml` | Gemma 4 E4B | Gemma 4 12B (a second vLLM server on the same GPU) |

Thinking is capped per step (`[think]`: 8k for writing steps, 4k for judges), ended by vLLM with a closing phrase so
the answer is never cut. Requests go to the server in priority order: the critical path first (parts, key points, key
terms, registry, facets), the rest fills the GPU around it.

Engines (`engine` per role): `vllm` (a Hugging Face repo), `llamacpp` (an `org/repo:file.gguf`), `openai` (an API
model name). On the RTX PRO 6000 (96 GB), Qwen 27B with thinking on and a JSON schema, total output tokens per second:

| Requests at once | llama.cpp, Q8 GGUF | vLLM, FP8 |
|--:|--:|--:|
| 1 | 45 | 45 |
| 32 | 338 | 752 |
| 64 | | ~1,400 |
| 128 | | 1,353 per wave, ~1,750 steady |

### On EC2 (or any big NVIDIA GPU)

```bash
git clone https://github.com/raghu-raman-b/mtp-implementation.git && cd mtp-implementation/lir-construction
bash setup_ec2.sh                 # 15-20 min on a fresh instance; HF_TOKEN=... for faster downloads
```

`setup_ec2.sh` installs ffmpeg, ninja and tmux, the pipeline venv (`.venv`, torch for CUDA 13), vLLM 0.32.0 in
`~/vllm-venv`, downloads Qwen 3.8 27B FP8, Gemma 4 E4B and 12B and the embedding model, and runs the smoke test. It is
safe to rerun. `LLAMA=1` also builds llama.cpp and downloads the Q8 GGUF. Stopping (not terminating) the instance
keeps all of it; an AMI of a set-up instance starts ready.

A run, with a live dashboard and a stats report per setup:

```bash
bash run_v2.sh --setups small,large --courses vr   # VR on the small setup, then on the large one
bash run_v2.sh                                     # large setup, VR then Deep Learning; --only 1-3, --name, --resume
```

Setups run one after another, and the courses of a setup one at a time (the whole GPU for one course). It opens a tmux
session `lir2` (Ctrl-b d detaches, `tmux attach -t lir2` comes back) with a dashboard per setup (GPU, vLLM throughput,
KV cache, progress), a window per course, the server logs and a control window. Each run gets its own folder, so
nothing earlier is overwritten:

```
runs/<name>/<setup>/report.md, charts/     time, requests and tokens per type, GPU and server stats, what was
                                           built; rerun python3 run_report.py runs/<name>/<setup> at any time
runs/<name>/<setup>/<course>/lir/          the LIR
runs/<name>/<setup>/<course>/build/        answer cache, step outputs, calls.jsonl (every request), report.md
runs/<name>/<setup>/server.csv             GPU and vLLM metrics every 5 s (run_monitor.py)
```

By hand: `python3 serve_lir2.py --config <config>` starts the server(s), `generate_lir2.py ... --config <config>
--keep-server` runs a course against them, `python3 serve_lir2.py --config <config> --stop` stops them.

The answer cache (`output/<course>/v2/cache/`, or the run's `build/cache/`) makes a rerun only recompute what changed;
commit it or copy it back to keep the answers. Captions for lectures without subtitles (VR L04, L05) are kept in
`output/<course>/v2/subs/`, because YouTube often refuses cloud machines.

## Running on another PC

The LIR, the viewer and the LLM answer cache are in the repo; the videos are not (9 GB for the two courses, over GitHub's file limit).

```bash
git clone https://github.com/raghu-raman-b/mtp-implementation.git && cd mtp-implementation/lir-construction
pip install -r requirements-viewer.txt          # numpy (+ optional sentence-transformers, nltk)
python3 serve.py                                 # http://localhost:8000; segments play from YouTube
```

In the viewer, each segment plays as its own clip with the viewer's controls; captions are off by default and
clicking a caption highlights that sentence. **Dev mode** (top bar, or open `http://localhost:8000/?dev=1`) shows the
answers, each item's intent and source sentences, its origin record and the judge's verdict. The server only serves
`viewer/`, `lir/`, `media/` and `docs/`.

For local videos (offline playback), download them once; no GPU needed:

```bash
pip install -r requirements.txt
python3 generate_lir.py --lecture ../dataset/virtual_and_augmented_reality --videos-only
```

Rebuilding the LIR on that PC (for example after editing a stage) replays every answer from `output/<course>/cache/`,
so it needs neither a GPU nor API money unless a prompt or model changes. A full rebuild from scratch needs
llama.cpp's `llama-server` (set its path in `pipeline/llm.py`, `LLAMA_SERVER`) or an API generator in `lir_config.toml`.

## Choosing the models: `lir_config.toml`

Each role (`[generator]`, `[judge]`) names a model. A Hugging Face GGUF reference `org/repo:file.gguf` runs locally on
llama.cpp; a plain OpenAI model name such as `gpt-6-luna` runs on the API with the key from `.env` (`OPEN_AI_API`).
Current setup: Gemma 4 E4B Q8 generates locally; `gpt-6-luna` judges on the API. To judge locally instead:

```toml
[judge]
model = "unsloth/gemma-4-12B-it-qat-GGUF:gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
slots = 8
kv_tokens = 32768
```

API spending is checked before every call against `[api] budget_usd` (total across runs) and recorded in
`api_spend.json`. If the budget runs out mid-run, the judge calls that were not sent go to `[judge_fallback]` (a local
model, now Gemma 4 12B) instead of leaving items unjudged; prices per model go under `[api.prices."<model>"]`. Every field is explained in
`docs/pipeline.html` → Configuration.

## Output

```
output/<course_id>/
  course.json            concept registry, edges, course goals, concept embeddings
  L01.json ...           one LIR file per lecture (schema: lir_schema.py)
  timing_report.md       time per lecture and per stage, tokens, retries, flags (also timing.json)
  state/state_Lxx.json   course knowledge state after lecture k (state[k])
  stages/                each stage's intermediate output, for debugging
  cache/                 every LLM answer keyed by input hash; a rerun only recomputes what changed
```

## Model and engine

Generator: Gemma 4 E4B-it, Q8 GGUF (`unsloth/gemma-4-E4B-it-GGUF:UD-Q8_K_XL`), on llama.cpp's `llama-server` with 32 slots,
continuous batching, one unified f16 KV pool, thinking on for every call, temperature 0, and every answer constrained
to a JSON schema. The client caps the tokens in flight so the shared pool cannot overflow.

Each stage sends all its prompts, for all lectures, at once. Segment-level prompts are ordered role line →
segment transcript → task, so the calls on one segment share a cached prefix.

vLLM (FP8 weights) is wired in as `--engine vllm`, but it does not fit this card. Gemma's E4B carries 3.5B
parameters of embedding tables that vLLM keeps in bf16 (about 7 GB), so the model alone needs about 11 GB of the
12 GB. The Q8 GGUF stores those tables in 8 bits and fits with room for the KV cache (9.7 GB in use at 32 slots).

## Stages

| # | Stage | LLM calls | Notes |
|---|---|---|---|
| 1 | Segment | 1 per lecture | the standalone-segments prompt from `event-segmentation/compare/REPORT.md` (WD 0.09), unchanged; code sorts boundaries, merges segments under 2 min, flags those over 12 min; lectures over 28k prompt tokens use overlapping windows |
| 2 | Annotate | 2 per segment | sub-goal, content type, 2-5 key points; key terms with definitions and used concepts |
| 3 | Goal hierarchy | 1 per lecture + 1 per course | contiguous objectives ("You'll be able to ..."), lecture goal, course goals |
| 4 | Course state | yes/no checks + 1 per lecture | canonicalize terms (name/alias → embedding bands → LLM yes/no), typed edges, `state[k]` snapshots; LLM calls batched for the whole course, registry built by code in lecture order |
| 5 | Generate | ~2 per segment + ~5 per lecture | primer recall, quiz (code picks targets, item types, answer positions), summary, open questions (code picks types from the rule table); concept map built by code |
| 6 | Validate | inside every stage | schema-constrained decoding; code checks; failed items retried twice with the errors appended; then optional items are dropped and required ones flagged |
| 7 | Assemble | none | lecture and course JSON, leakage check, schema validation, key-point embeddings for the runtime scorer |

Leakage rule: lecture k reads only `state[k]` and its own annotations; the primer reads `state[k-1]`.
Stage 7 checks that no lecture refers to a concept introduced later and that recall items point only backwards.

## Files

| File | |
|---|---|
| `generate_lir.py` | entry point |
| `lir_schema.py` | Pydantic LIR v0; every output file is validated against it |
| `pipeline/transcript.py` | course discovery; SRT → cleaned sentences (drops `[SQUEAKING]`-style tags, speaker labels, the OCW notice) |
| `pipeline/llm.py` | server launcher and batching client (disk cache, retries with feedback, token budget, cost log) |
| `pipeline/prompts.py` | every prompt, with ID and version (recorded in origin) |
| `pipeline/validate.py` | layer-2 checks |
| `pipeline/s1_segment.py` ... `s7_assemble.py` | the stages |
| `pipeline/report.py` | the timing report |

## Not built yet

- Layer-3 LLM judge (the doc puts it last).
- The runtime answer scorer. The LIR already stores what it needs: key points with keywords and embeddings,
  concept embeddings, and uncalibrated defaults for m and τ under `scoring`.
- Interleaved quiz items from earlier lectures.
