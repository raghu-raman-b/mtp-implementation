# Baseline comparison: state at the stop (WIP, 2026-11-18)

Stopped on request mid-run. Nothing here is final; every number below is PARTIAL.
Our system under test: `pipeline/qa` as shipped at commit c0a0c8d (worktree HEAD db10844), not changed.
Model for all systems: Gemma 4 12B QAT (unsloth Q4_K_XL) on the shared llama-server, port 8092 (config
`pipeline/configs/gemma4_12b_llamacpp.json`), temperature 1.0, top_p 0.95, top_k 64. The server was never restarted.

## What is built

| system | exactly | files |
|---|---|---|
| ours | `qa.answer_stream` (the viewer's streamed route): tool loop over the knowledge layer, thinking in round 0 only | `run_systems.py run_ours` |
| plain | one call, no course data: system prompt with the course title + "2-5 sentences", the question; thinking off | `run_systems.py run_plain` |
| rag | 738 transcript chunks (~373 tokens, 60-token overlap, whole sentences, one lecture each; human subtitles from `stage_0a_preprocess`, sentence times from stage 0a cues / stage 1b estimates), embedded with Qwen3-Embedding-0.6B on CPU (no instruction; query with an instruction); top 8 chunks labelled lecture, title, start time; prompt = our answer rules adapted (cite "(lecture N, m:ss)", say not covered, COVERED line) + the same lecture list our prompt has; one call, thinking off | `chunks.py`, `rag.py`, `rag/chunks.json` |
| graphrag | light GraphRAG, NOT finished: entity/relation extraction with GraphRAG's tuple prompt (adapted entity types, no gleaning) over 476 text units of ~600 tokens; then (not yet run) merge by name, Louvain communities, one community report per community of 3+, entity/report embeddings; query = GraphRAG-style local search with no text units (entities, relationships, community reports, each with lecture/time provenance) | `graphrag_build.py`, `run_systems.py run_graphrag` |

Time estimate that decided GraphRAG vs "graph-only (our concept graph)": a 6-unit probe gave 924 output tokens per
unit, 57 min for all 476 units with 3 parallel requests on an idle GPU (it ran slower, 25-40 s per call, while the CPU
was busy embedding); plus ~10-20 min for community reports. It fits the 2 h budget, so the light GraphRAG was chosen.

Long context: all 63 transcripts are 244,971 Gemma tokens (207,093 words; largest lecture 6,327), 1.87x the server's
131,072-token context (`transcript_tokens.json`). They do not fit.

## What has run

- `runs/ours.jsonl`, `runs/plain.jsonl`, `runs/rag.jsonl`: all 53 questions each (GPU otherwise idle from this agent;
  the shared server may have served the other agent at times).
- graphrag: extraction 176 / 476 text units done (`graphrag/extractions.jsonl`); graph, reports, embeddings and the
  graphrag answers NOT run.
- Questions: `questions.jsonl`, 53 (definition 7, explanation 7, comparison 7, list 4, formula 5, where 5,
  prerequisite 4, structure 5, not_covered 9), all 12 DEMO_PLAN questions + optional ones, all 17 bench.py B-questions
  (B12 replaced by "before lecture 17"), gold answers with fact / sentence IDs (`make_questions.py`).

## What is judged (PARTIAL)

`judgments_partial.jsonl` (from `judgments_partial.py`): questions D01-L03 (24 of 53: definitions, explanations,
comparisons, lists), systems ours / plain / rag. Judge packets for all 53 x 3 are in `judge/packet_*.txt`
(`render_for_judge.py`, citation windows from `citations.py`).

Partial findings on those 24 covered questions only (no not-covered, where, prerequisite, structure or formula
question judged yet, which is where the systems should differ most):
- correct (mean of 1 / 0.5 / 0): ours 1.00, rag 0.96, plain 0.79. RAG and ours tie on most of these; RAG's one miss is
  a false "not covered" on "What is vection?" (retrieval missed lectures 11 and 26).
- hallucinations: ours 1 (D04: reversed "presence is limited by immersion"), rag 0, plain 5 (wrong partial gait / gait
  negation, invented contextual-inquiry stages, low/medium/high "fidelities", invented Majuli reasons, IR emitters).
- citations valid: ours 108/110, rag 118/121 (RAG cites chunk starts, so its times are up to ~2 min before the claim;
  ours cites the fact's first sentence).
- cost over all 53 (from the runs, not judged): median latency ours 6.5 s, rag 3.85 s, plain 1.56 s; first token ours
  3.22 s, rag 1.53 s, plain 0.08 s; median context tokens ours 4,804 (2.19 model calls per answer), rag 4,027, plain 98.

## What is left

1. Finish the GraphRAG extraction (300 units, ~45-60 min with the GPU free), then build graph, reports, embeddings.
2. Run graphrag on the 53 questions.
3. Re-render packets (now with graphrag) and judge the remaining 29 questions for all four systems and the first 24
   for graphrag; copy the partial judgments into `judgments.jsonl` (same fields) and add the rest.
4. `summarize.py` -> `summary.json` + tables; write `README.md` (setup, rerun, tables per category and overall, 6-10
   side-by-side examples, limitations); final commit.

## Resume commands (from the worktree root)

```
cd baseline-tests
python3 graphrag_build.py extract        # resumable; run it with run_in_background, not "&" (an "&" job died with the shell)
python3 graphrag_build.py graph          # merge + Louvain + community reports + embeddings
python3 run_systems.py graphrag          # resumable per question
python3 render_for_judge.py              # judge/packet_*.txt with all four systems
python3 judgments_partial.py             # rewrites judgments_partial.jsonl (24 x 3 judged)
# judge the rest into judgments.jsonl, then:
python3 summarize.py
```
`rag/embeddings.json` and `rag/embed_cache.jsonl` are not committed (20 MB, rebuilt by `python3 rag.py build`,
27 min on the CPU). Do not use `pkill -f` with a pattern that also matches your own shell's command line.
