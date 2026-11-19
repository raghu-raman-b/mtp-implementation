# Paper-ready figures

Regenerate, from the repository root: `pipeline/results/.venv/bin/python pipeline/results/make_graphs.py [function ...]` (venv, gitignored: `python3 -m venv pipeline/results/.venv && pipeline/results/.venv/bin/pip install matplotlib SciencePlots numpy`). Reads existing result files only. Each figure is saved as PDF and PNG (300 dpi); single column 3.5 in, double column 7 in. Style: SciencePlots `science` + `no-latex`, Okabe-Ito colours.

## segmentation/
- `vs_human_lecture1` — WindowDiff against the human annotator on lecture 1 for the LLM segmenter, TextTiling, TopicTiling, TSVLT and trivial baselines (orange: LLM, blue: classical, grey: baseline). Source: `event-segmentation/compare/REPORT.md` (table), `lec1__P01__both.json`.
- `design_runs_profile` — Median duration, too-short and too-long segment counts across design runs 1 to 4 and the verified run. Source: `analysis/segmentation/data/history_runs.csv`.
- `run_to_run_f1` — Boundary F1 between seeds per lecture, before and after verification. Source: `analysis/segmentation/data/run_to_run_lectures.csv`.

## preprocessing/
- `sentence_split_vs_pysbd` — Share of sentence boundaries found by both splitters, only the proposed one, or only pySBD, per course. Source: `analysis/preprocessing/data/pysbd_comparison.csv`.
- `boundary_time_error_cdf` — Cumulative distribution of boundary-time errors for three timing methods, per course. Source: `analysis/preprocessing/data/boundary_time_errors.csv`.

## fact_judge/ (includes fact-extraction judge test)
- `seeded_errors_by_property` — Share of deliberately broken facts the judge catches, per property and run. Source: `analysis/fact_judge/compare.json`.
- `gold_reference` — Real failures caught and false alarms on good facts against the hand-labelled reference, three runs. Source: `analysis/fact_judge/compare.json`.
- `judge_material_by_seed` — Facts failed on lecture 1 by judge input (cited evidence vs whole segment) and seed. Source: `analysis/fact_extraction/data/judge_test/report.md`.

## activities/
- `trial_failed_criteria` — Activity-judge failed criteria in the three-lecture pipeline trial. Source: `analysis/activities/trial_v3_lectures_1_4_16/checks.json`.

## activities_study/
- `pipeline_judge_pass_rate` — Pipeline-judge pass rate per activity kind for the four systems. Source: `baseline-tests/activities_study/out/summary.json` (gemma_judge).
- `blind_ratings` — Blind Sonnet ratings (correct, grounded, good distractors, serves goals) per kind and system. Source: same file (sonnet). The "Proposed, same model" system has no concept-map or recall items.
- `concept_map_and_recall` — Concept-map edge correctness and recall grounding and wrong lecture links. Source: same file (sonnet).
- `layer_only_counts` — Counts of activities and items only the knowledge layer supports, whole course, log scale. Source: same file (layer_only).

## qa/
- `latency_by_variant` — Answer-time distribution across the QA latency-optimisation variants (local and vLLM). Source: `analysis/qa/bench_*.jsonl`.
- `coverage_calibration` — Best-fact similarity of in-course, partly taught and out-of-course queries with the chosen cut-off. Source: `analysis/qa/calibration.json`.

## failures/
- `inventory_overview` — Failure kinds by stage and handling (a), and the most frequent kinds by share of affected units (b). Source: `analysis/failures/inventory.json`.

## baseline_qa/
System versions: "Proposed (knowledge layer)" is the optimised system with reasoning in the tool round (`ours_v2`); "Proposed (no reasoning)" is the optimised system without it (`ours_v2_nothink`). Run 1 (65 questions) of every system. The two ablations and the judge-agreement figure were produced with the earlier, pre-optimisation version of the proposed system (`ours`); the ablation labels are unchanged and the agreement figure labels that system "Proposed (earlier)".
- `correctness_by_category` — Correctness per question category for nine systems (heatmap). Source: `baseline-tests/summary.json` (`per_category`). Questions per category: definition 7, explanation 7, comparison 7, list 4, formula 5, where taught 5, prerequisite 4, structure 5, not covered 9, multi-hop 12.
- `correctness_latency_hallucinations` — Overall correctness against median answer time, bar to the 90th percentile (a); false claims and answers with a false claim over 65 questions (b). Source: `baseline-tests/summary.json`.
- `context_and_citation_validity` — Median context tokens and share of citations pointing to a real supporting passage (checked by code). Source: `baseline-tests/summary.json`.
- `latency_distribution` — Per-answer time per system, log scale, box = quartiles, whiskers = 5th to 95th percentile. Source: `baseline-tests/runs/<system>.jsonl`.
- `judge_agreement` — Two-judge (Opus, Sonnet) mean correctness per system and agreement statistics over 257 answers. Source: `baseline-tests/judge_agreement.json`.

## qa_optimisation/
Before/after of the QA optimisation, run 1 (65 questions): "Proposed (earlier)" = `ours`, "Proposed (optimised, reasoning)" = `ours_v2`, "Proposed (optimised, no reasoning)" = `ours_v2_nothink`; RAG (`rag`) and RAG + reasoning (`rag_think`) as references.
- `latency` — Median and 90th-percentile answer time (a) and time to first token (b), log scale, labels give median / p90 in seconds. Source: `baseline-tests/runs/*.jsonl` (same p90 rule as `summarize.py`).
- `accuracy_by_category` — Correctness overall and per question category, earlier against both optimised modes. Source: `baseline-tests/summary.json` (`before_after`).
- `calls_per_question` — Model calls, tool calls and `check_concept` calls per question; RAG has one model call and no tools. Source: `baseline-tests/summary.json` (`before_after`, `overall`).
- `false_claims` — Answers containing a false claim out of 65, before and after, with RAG for reference. Source: `baseline-tests/summary.json`.

## Skipped
- Fact extraction (2a): no numeric analysis report beyond the judge test above (covered).
- Concepts and registry: `analysis/concepts` holds one trial README with a single set of counts, and `analysis/registry/embed_compare.py` has no result files in the repo; the concept and fact failure counts are in `failures/inventory_overview`.
- Part titles: no numeric results found.
