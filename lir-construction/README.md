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
`api_spend.json`; prices per model go under `[api.prices."<model>"]`. Every field is explained in
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
