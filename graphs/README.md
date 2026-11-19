# Paper-ready figures

Regenerate: `graphs/.venv/bin/python graphs/make_graphs.py [function ...]` (venv: `python3 -m venv graphs/.venv && graphs/.venv/bin/pip install matplotlib SciencePlots numpy`). Reads existing result files only. Each figure is saved as PDF and PNG (300 dpi); single column 3.5 in, double column 7 in. Style: SciencePlots `science` + `no-latex`, Okabe-Ito colours.

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
- `blind_ratings` — Blind Sonnet ratings (correct, grounded, good distractors, serves goals) per kind and system. Source: same file (sonnet). Proposed (same model) has no concept-map or recall items.
- `concept_map_and_recall` — Concept-map edge correctness and recall grounding and wrong lecture links. Source: same file (sonnet).
- `layer_only_counts` — Counts of activities and items only the knowledge layer supports, whole course, log scale. Source: same file (layer_only).

## qa/
- `latency_by_variant` — Answer-time distribution across the QA latency-optimisation variants (local and vLLM). Source: `analysis/qa/bench_*.jsonl`.
- `coverage_calibration` — Best-fact similarity of in-course, partly taught and out-of-course queries with the chosen cut-off. Source: `analysis/qa/calibration.json`.

## failures/
- `inventory_overview` — Failure kinds by stage and handling (a), and the most frequent kinds by share of affected units (b). Source: `analysis/failures/inventory.json`.

## baseline_qa/
- `correctness_by_category` — Correctness per question category for eight systems (heatmap). Source: `baseline-tests/summary.json`.
- `correctness_latency_hallucinations` — Overall correctness against median and p90 latency (a), false claims and answers with a false claim (b). Source: `baseline-tests/summary.json`.
- `context_and_citation_validity` — Median context tokens and citation validity per system. Source: `baseline-tests/summary.json`.
- `latency_distribution` — Per-answer latency distribution per system (log scale). Source: `baseline-tests/runs/<system>.jsonl` (run 1).
- `judge_agreement` — Two-judge mean correctness per system and agreement statistics. Source: `baseline-tests/judge_agreement.json`.

## Skipped
- Fact extraction (2a): no numeric analysis report beyond the judge test above (covered).
- Concepts and registry: `analysis/concepts` holds one trial README with a single set of counts, and `analysis/registry/embed_compare.py` has no result files in the repo; the concept and fact failure counts are in `failures/inventory_overview`.
- Part titles: no numeric results found.
