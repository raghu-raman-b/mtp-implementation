# Baseline comparison: method

Our question answering (`pipeline/qa`) compared with plain, RAG and light-GraphRAG baselines and two tool ablations,
on one course (NPTEL "Foundation for Virtual and Augmented Reality Systems", 63 lectures). Results: `tables.md`,
`summary.json`, `examples.jsonl`, `demo_questions.json`; raw answers `runs/`; judgments `judgments.jsonl`.

## Model and sampling (all systems)

- Gemma 4 12B QAT (unsloth `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`) on one llama-server (llama.cpp), config
  `pipeline/configs/gemma4_12b_llamacpp.json`: port 8092, context 131,072, 6 slots, KV cache q8_0,
  `--reasoning-budget 8192` (think_budget, fixed per server).
- Sampling: temperature 1.0, top_p 0.95, top_k 64 (the qa config's), for every call of every system.
- Thinking: ours and the ablations think in round 0 only (qa's setting); rag_think thinks in its one call (same server
  budget, 8192 tokens; max_tokens 12,288 as the qa config); plain, rag, graphrag_text, graphrag_notext: thinking off,
  max_tokens 2,048.
- Run on a local RTX 5070 (12 GB), one question at a time per system.

## Systems

| system | construction |
|---|---|
| ours | `qa.answer_stream(question, course="nptel_vr")` from `pipeline/qa` at the merged main of this branch (connecting concepts give facts only). Tool loop over the knowledge layer, up to 5 tool rounds then a forced answer; tools `check_concept`, `fact_lookup`, `lecture_dependencies`, `lecture_overview`, `course_goals` (`pipeline/prompts/qa_tools.json`); system prompt `pipeline/prompts/qa_system.txt` with the lecture list; tool_choice auto; citations are qa's fact/segment citations. Context tokens = qa's summed input tokens over its calls; model calls = qa's rounds. Earlier results with qa at c0a0c8d: `runs/ours_c0a0c8d.jsonl` (reference only, not judged here). |
| plain | One call, no course data. System prompt: teaching assistant for the course, 2-5 sentences or a short list (`PLAIN_SYSTEM` in `run_systems.py`); user = course title + question. |
| rag | Transcript chunks: whole sentences of one lecture, target 400 estimated tokens (1.18 tokens per word), 60-token overlap, 738 chunks (`chunks.py`, `rag/chunks.json`), from the human-written subtitles (pipeline stage 0a) with sentence start times. Embeddings: Qwen3-Embedding-0.6B on CPU, chunks without instruction, query with the instruction "Given a learner's question about a lecture course, retrieve the transcript passages that answer it"; cosine similarity, top 8 chunks (`rag.py`). Each chunk labelled lecture, title, start time. Prompt `RAG_SYSTEM` in `run_systems.py`: our answer rules adapted (use only the excerpts, cite "(lecture N, m:ss)" after each claim, say when not covered, answer the covered part, 2-5 sentences, a final COVERED line) + the course's lecture list. One call. |
| rag_think | rag with thinking on (see above); same retrieval and prompt. |
| graphrag_notext | Light GraphRAG index (`graphrag_build.py`, after Microsoft GraphRAG 0.x standard indexing): text units of 600 estimated tokens / 60 overlap within one lecture (476 units); entity + relationship extraction per unit with GraphRAG's tuple-format prompt, entity types adapted (concept, technology, device, method, phenomenon, person, organization, metric), no gleaning, max_tokens 4,096, thinking off, 3 then 6 parallel requests; entities merged by upper-cased name (up to 4 distinct descriptions kept, no LLM summarisation), relationships merged by pair with summed weights; communities: Louvain (networkx, seed 7, weighted), communities over 40 entities re-split with resolution 2.0, communities of 3+ entities kept; one GraphRAG-style community report per community (title, summary, findings JSON; prompt `REPORT_PROMPT`, max_tokens 2,048); entity ("name: description") and report ("title: summary") embeddings with Qwen3-Embedding-0.6B. Query (`graph_context` in `run_systems.py`): local search without text units: top 12 entities by embedding similarity (query instruction "... retrieve the knowledge graph entities that answer it"), up to 24 relationships touching them (both ends selected first, then weight), up to 4 community reports (the 2 communities holding most selected entities, then by report similarity); every item labelled with the lectures/times of its text units. Prompt `GRAPH_SYSTEM` (same rules as rag). One call. Index size: GRAPHRAG_SIZE. |
| graphrag_text | graphrag_notext's context plus the source text units of the selected entities, ranked as GraphRAG local search ranks them (rank of the first selected entity from the unit, then the number of selected relationships from it), added until they reach 6,000 tokens (characters / 4) = 50% of GraphRAG's default 12,000-token local context (text_unit_prop 0.5); each unit labelled lecture, title, start time (`graph_text_context`). Prompt `GRAPH_TEXT_SYSTEM`. One call. |
| abl_facts | ours with only `fact_lookup` offered to the model. |
| abl_graph | ours with only `check_concept`, `lecture_dependencies`, `lecture_overview`, `course_goals` offered (no `fact_lookup`). |

Ablations (`ABLATIONS`, `restrict_tools` in `run_systems.py`): `qa.answer.tool_specs` is replaced by the filtered
list and `qa.answer.run_tool` answers a call to a removed tool with qa's own "There is no tool ..." result. The system
prompt, tool descriptions of the kept tools, rounds and all other qa behaviour are unchanged; `pipeline/qa` itself is
not modified.

## Questions

`questions.jsonl` (built by `make_questions.py`): 53 questions with gold answers and gold sources (fact / sentence IDs
with lecture and time). Categories: definition 7, explanation 7, comparison 7, list 4, formula 5, where 5,
prerequisite 4, structure 5, not_covered 9 (expect "no": the course does not teach it). Includes the DEMO_PLAN
questions and the bench.py B-questions.

## Runs

- Run 1: every system on all 53 questions (`runs/<system>.jsonl`).
- Repeats: runs 2 and 3 for ours, rag, rag_think on the categories not_covered, where, prerequisite, structure,
  formula (28 questions; `runs/<system>_r2.jsonl`, `_r3.jsonl`). Same settings; only sampling differs.
- plain and rag run 1 are the earlier runs (unchanged systems); all other run-1 files are new.
- Timings per answer: wall seconds, time to first answer token (ours: first streamed draft), retrieval seconds,
  context (input) tokens, output tokens, model calls.

## Judging

- Judge: Claude Opus (Opus 5.5), reading compact packets (`render_for_judge.py` -> `judge/todo_*.txt`): question,
  category, expected coverage, gold answer, and each pending (system, run) answer labelled with the system name.
- One line per (question, system, run) in `judgments.jsonl`: `correct` 1 / 0.5 / 0 (1: answers the question with the
  gold's main points and nothing wrong; 0.5: partly right or incomplete; 0: wrong, empty, or a false "not covered"; on
  not_covered questions 1 = says the course does not cover it), `hallucinations` (number of false claims,
  contradictions of the course, or outside content presented as taught), `not_covered_handled` (not_covered questions
  only: said not covered and did not invent course content; null otherwise), `note` (12 words at most). Criteria as in
  `judgments_partial.py` (the partial pass). The 24 x (plain, rag) judgments of questions D01-L03 from that pass are
  copied (those runs did not change); everything else is judged in this pass.
- Citation validity by code (`summarize.py`, `citations.written_citations`, same rule for every system): each
  "(lecture N, m:ss)" in an answer is valid when the lecture exists and at least 50% of the content words of the
  sentence it closes occur in that lecture's transcript from 30 s before to 240 s after the cited time.

## Rerun

From `baseline-tests/` (the llama-server on port 8092 is started by qa on first use, or by `python -m qa "hi"` in
`pipeline/`; stop it with `python -m qa --stop`):

```
python3 rag.py build                      # chunks + embeddings (27 min on CPU; rag/embeddings.json not committed)
python3 graphrag_build.py extract         # resumable extraction -> graphrag/extractions.jsonl
python3 graphrag_build.py graph           # merge, Louvain, community reports, embeddings -> graphrag/
python3 run_systems.py ours plain rag rag_think graphrag_text graphrag_notext abl_facts abl_graph
for r in 2 3; do python3 run_systems.py ours rag rag_think --run $r \
    --categories not_covered where prerequisite structure formula; done
python3 render_for_judge.py               # judge/todo_*.txt: answers not yet in judgments.jsonl
# judge them into judgments.jsonl (fields above), then
python3 summarize.py                      # summary.json, tables.md, examples.jsonl, demo_questions.json
```

`examples.jsonl`: the 10 questions with the largest spread (population std, then range) of run-1 correctness across
systems, with every system's answer. `demo_questions.json`: per category, questions where ours scored correct = 1 in
every judged run and the best baseline (plain, rag, rag_think, graphrag_text, graphrag_notext; mean over its runs)
scored lower; ablation scores listed alongside.
