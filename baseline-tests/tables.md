# Baseline comparison tables

Run 1 of every system, 65 questions. correct: mean of 1 / 0.5 / 0 (Sonnet judge). halluc: false claims counted (answers with one). cit valid: by code (see summarize.py). nc handled: not-covered questions answered as not covered without invented content. ctx: median context tokens. calls: mean model calls. latency / first token in seconds.

## Overall

| system | correct | halluc (answers) | cit valid | nc handled | ctx | calls | latency med | latency p90 | first token |
|---|---|---|---|---|---|---|---|---|---|
| ours | 0.8 | 5 (5) | 195/244 | 8/9 | 4892 | 2.277 | 5.66 | 8.41 | 2.99 |
| plain | 0.254 | 61 (40) | 0/0 | 1/9 | 100 | 1.0 | 1.59 | 1.94 | 0.08 |
| rag | 0.815 | 3 (3) | 255/279 | 9/9 | 4033 | 1.0 | 4.24 | 5.54 | 1.53 |
| rag_think | 0.808 | 1 (1) | 250/278 | 9/9 | 4031 | 1.0 | 25.37 | 48.74 | 24.07 |
| graphrag_text | 0.777 | 1 (1) | 224/328 | 8/9 | 8291 | 1.0 | 5.62 | 8.07 | 3.03 |
| graphrag_notext | 0.662 | 8 (8) | 197/337 | 8/9 | 3624 | 1.0 | 3.65 | 6.19 | 1.37 |
| abl_facts | 0.762 | 0 (0) | 196/227 | 8/9 | 3593 | 2.092 | 5.52 | 7.67 | 3.59 |
| abl_graph | 0.785 | 9 (9) | 205/272 | 7/9 | 5211 | 2.554 | 5.74 | 8.4 | 2.98 |
| ours_v2 | 0.854 | 1 (1) | 221/265 | 7/9 | 5759 | 2.154 | 5.59 | 8.41 | 3.03 |
| ours_v2_nothink | 0.831 | 0 (0) | 247/286 | 7/9 | 5158 | 2.062 | 3.9 | 5.83 | 1.34 |

## Correct per category

| category (n) | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph | ours_v2 | ours_v2_nothink |
|---|---|---|---|---|---|---|---|---|---|---|
| definition (7) | 1.0 | 0.571 | 0.786 | 0.714 | 0.786 | 0.643 | 0.929 | 1.0 | 1.0 | 1.0 |
| explanation (7) | 0.929 | 0.5 | 1.0 | 0.929 | 1.0 | 0.857 | 0.786 | 0.857 | 0.714 | 0.857 |
| comparison (7) | 0.929 | 0.429 | 1.0 | 1.0 | 1.0 | 0.786 | 1.0 | 1.0 | 1.0 | 0.929 |
| list (4) | 0.875 | 0.125 | 1.0 | 1.0 | 0.875 | 0.875 | 1.0 | 0.875 | 1.0 | 0.875 |
| formula (5) | 0.9 | 0.3 | 0.7 | 0.9 | 0.8 | 0.5 | 0.8 | 0.9 | 1.0 | 0.9 |
| where (5) | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| prerequisite (4) | 0.5 | 0.0 | 0.125 | 0.125 | 0.0 | 0.0 | 0.0 | 0.75 | 0.5 | 0.625 |
| structure (5) | 0.6 | 0.0 | 0.9 | 0.9 | 0.7 | 0.6 | 0.4 | 0.6 | 0.9 | 0.9 |
| not_covered (9) | 0.889 | 0.111 | 0.944 | 0.944 | 0.889 | 0.889 | 0.944 | 0.889 | 0.833 | 0.833 |
| multihop (12) | 0.5 | 0.25 | 0.625 | 0.583 | 0.583 | 0.417 | 0.583 | 0.333 | 0.708 | 0.583 |

## Hallucinations per category (count)

| category | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph | ours_v2 | ours_v2_nothink |
|---|---|---|---|---|---|---|---|---|---|---|
| definition | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| explanation | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| comparison | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| list | 0 | 13 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| formula | 0 | 2 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| where | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| prerequisite | 0 | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| structure | 1 | 8 | 0 | 0 | 0 | 0 | 0 | 2 | 1 | 0 |
| not_covered | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| multihop | 3 | 18 | 2 | 0 | 1 | 5 | 0 | 6 | 0 | 0 |

## Citation validity per category (valid/total)

| category | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph | ours_v2 | ours_v2_nothink |
|---|---|---|---|---|---|---|---|---|---|---|
| definition | 38/41 | 0/0 | 26/26 | 27/27 | 30/46 | 26/42 | 27/30 | 39/44 | 41/45 | 39/44 |
| explanation | 16/20 | 0/0 | 27/33 | 25/31 | 21/37 | 13/39 | 18/19 | 22/29 | 18/23 | 21/24 |
| comparison | 36/36 | 0/0 | 40/41 | 36/37 | 38/48 | 34/49 | 30/32 | 35/39 | 39/39 | 36/37 |
| list | 18/18 | 0/0 | 27/27 | 22/24 | 21/29 | 22/34 | 21/21 | 22/27 | 22/23 | 18/20 |
| formula | 11/14 | 0/0 | 24/26 | 19/20 | 21/21 | 17/19 | 12/14 | 9/12 | 10/14 | 16/18 |
| where | 9/12 | 0/0 | 8/9 | 17/17 | 4/9 | 7/21 | 15/19 | 7/12 | 8/11 | 10/14 |
| prerequisite | 13/19 | 0/0 | 10/11 | 7/14 | 15/23 | 5/9 | 0/0 | 15/21 | 15/20 | 19/23 |
| structure | 7/17 | 0/0 | 16/20 | 21/25 | 9/11 | 20/34 | 1/12 | 9/18 | 14/22 | 17/25 |
| not_covered | 12/17 | 0/0 | 19/21 | 21/21 | 15/24 | 19/30 | 28/29 | 14/20 | 15/16 | 18/20 |
| multihop | 35/50 | 0/0 | 58/65 | 55/62 | 50/80 | 34/60 | 44/51 | 33/50 | 39/52 | 53/61 |

## Latency median / first token median per category (s)

| category | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph | ours_v2 | ours_v2_nothink |
|---|---|---|---|---|---|---|---|---|---|---|
| definition | 4.12 / 2.15 | 1.35 / 0.08 | 3.52 / 1.59 | 26.21 / 24.4 | 5.22 / 2.97 | 3.71 / 1.36 | 5.77 / 3.01 | 4.12 / 2.19 | 4.74 / 2.1 | 3.03 / 1.12 |
| explanation | 5.28 / 3.33 | 1.46 / 0.08 | 4.21 / 1.55 | 24.36 / 22.58 | 5.74 / 3.27 | 3.5 / 1.48 | 5.41 / 3.62 | 6.25 / 3.05 | 6.18 / 4.2 | 3.45 / 1.79 |
| comparison | 6.52 / 3.5 | 1.56 / 0.08 | 4.94 / 1.58 | 20.7 / 17.3 | 6.18 / 3.03 | 4.33 / 1.43 | 5.52 / 3.4 | 6.56 / 3.53 | 5.71 / 2.84 | 4.27 / 1.44 |
| list | 6.22 / 3.17 | 1.63 / 0.08 | 3.53 / 1.48 | 18.78 / 16.49 | 5.63 / 3.13 | 4.12 / 1.42 | 5.35 / 3.17 | 6.67 / 3.79 | 6.68 / 3.09 | 4.16 / 1.25 |
| formula | 5.24 / 3.56 | 1.67 / 0.09 | 4.69 / 1.61 | 27.85 / 24.57 | 5.65 / 3.25 | 3.65 / 1.39 | 6.23 / 3.69 | 6.45 / 3.24 | 6.67 / 3.36 | 4.94 / 2.05 |
| where | 3.52 / 2.18 | 0.85 / 0.08 | 3.11 / 1.35 | 22.6 / 20.66 | 3.96 / 3.0 | 3.14 / 1.33 | 4.9 / 2.94 | 3.53 / 2.27 | 3.47 / 2.17 | 2.23 / 0.79 |
| prerequisite | 5.81 / 2.03 | 1.7 / 0.08 | 2.49 / 0.88 | 42.16 / 40.5 | 6.2 / 2.95 | 3.67 / 1.26 | 4.2 / 3.9 | 5.61 / 2.1 | 5.21 / 2.0 | 4.3 / 0.8 |
| structure | 5.51 / 2.72 | 1.04 / 0.08 | 3.78 / 1.36 | 39.39 / 36.37 | 4.83 / 2.97 | 3.27 / 1.27 | 4.66 / 3.44 | 5.62 / 3.58 | 4.96 / 2.48 | 3.46 / 1.14 |
| not_covered | 3.89 / 2.35 | 1.82 / 0.08 | 3.07 / 1.5 | 21.54 / 19.58 | 4.52 / 2.96 | 2.91 / 1.34 | 6.17 / 4.35 | 3.76 / 2.4 | 3.98 / 2.95 | 2.44 / 0.81 |
| multihop | 8.0 / 4.82 | 1.77 / 0.09 | 4.81 / 1.56 | 28.94 / 26.25 | 6.31 / 3.45 | 4.38 / 1.42 | 7.08 / 4.32 | 7.93 / 5.12 | 8.29 / 5.25 | 4.82 / 1.91 |

## Repeats (3 runs): correct, mean ± range (min-max) across runs

| category | ours | rag | rag_think | ours_v2 | ours_v2_nothink |
|---|---|---|---|---|---|
| not_covered | 0.889 (0.889-0.889, 3 runs) | 0.944 (0.944-0.944, 3 runs) | 0.944 (0.944-0.944, 3 runs) | 0.833 (0.833-0.833, 3 runs) | 0.815 (0.778-0.833, 3 runs) |
| where | 1.0 (1.0-1.0, 3 runs) | 1.0 (1.0-1.0, 3 runs) | 1.0 (1.0-1.0, 3 runs) | 1.0 (1.0-1.0, 3 runs) | 1.0 (1.0-1.0, 3 runs) |
| prerequisite | 0.5 (0.5-0.5, 3 runs) | 0.042 (0.0-0.125, 3 runs) | 0.125 (0.125-0.125, 3 runs) | 0.5 (0.5-0.5, 3 runs) | 0.583 (0.5-0.625, 3 runs) |
| structure | 0.6 (0.6-0.6, 3 runs) | 0.9 (0.9-0.9, 3 runs) | 0.9 (0.9-0.9, 3 runs) | 0.9 (0.9-0.9, 3 runs) | 0.9 (0.9-0.9, 3 runs) |
| formula | 0.9 (0.9-0.9, 3 runs) | 0.7 (0.7-0.7, 3 runs) | 0.9 (0.9-0.9, 3 runs) | 1.0 (1.0-1.0, 3 runs) | 0.9 (0.9-0.9, 3 runs) |

## Before / after the QA optimisation (run 1): ours (old run) vs ours_v2 (think) vs ours_v2_nothink

correct: mean 1 / 0.5 / 0 (n judged); latency median / p90 and first token median in seconds; ctx: median context tokens; calls: mean model calls; tools/q: tool calls per question; check_concept/q: check_concept calls per question.

### Correct per category

| category (n) | ours | ours_v2 | ours_v2_nothink |
|---|---|---|---|
| definition (7) | 1.0 (7) | 1.0 (7) | 1.0 (7) |
| explanation (7) | 0.929 (7) | 0.714 (7) | 0.857 (7) |
| comparison (7) | 0.929 (7) | 1.0 (7) | 0.929 (7) |
| list (4) | 0.875 (4) | 1.0 (4) | 0.875 (4) |
| formula (5) | 0.9 (5) | 1.0 (5) | 0.9 (5) |
| where (5) | 1.0 (5) | 1.0 (5) | 1.0 (5) |
| prerequisite (4) | 0.5 (4) | 0.5 (4) | 0.625 (4) |
| structure (5) | 0.6 (5) | 0.9 (5) | 0.9 (5) |
| not_covered (9) | 0.889 (9) | 0.833 (9) | 0.833 (9) |
| multihop (12) | 0.5 (12) | 0.708 (12) | 0.583 (12) |
| overall (65) | 0.8 (65) | 0.854 (65) | 0.831 (65) |

### Run-side numbers

| group | system | answers | latency med / p90 | first token | calls | ctx | tools/q | check_concept/q |
|---|---|---|---|---|---|---|---|---|
| overall | ours | 65 | 5.66 / 8.41 | 2.99 | 2.277 | 4892 | 1.35 | 0.91 |
| overall | ours_v2 | 65 | 5.59 / 8.41 | 3.03 | 2.154 | 5759 | 1.17 | 0.85 |
| overall | ours_v2_nothink | 65 | 3.9 / 5.83 | 1.34 | 2.062 | 5158 | 1.06 | 0.58 |
| definition | ours | 7 | 4.12 / 6.22 | 2.15 | 2.0 | 5167 | 1.0 | 1.0 |
| definition | ours_v2 | 7 | 4.74 / 7.15 | 2.1 | 2.0 | 5635 | 1.0 | 1.0 |
| definition | ours_v2_nothink | 7 | 3.03 / 6.28 | 1.12 | 2.0 | 5637 | 1.0 | 1.0 |
| explanation | ours | 7 | 5.28 / 6.96 | 3.33 | 2.286 | 5855 | 1.29 | 1.0 |
| explanation | ours_v2 | 7 | 6.18 / 7.53 | 4.2 | 2.143 | 6323 | 1.14 | 1.0 |
| explanation | ours_v2_nothink | 7 | 3.45 / 4.41 | 1.79 | 2.0 | 5171 | 1.0 | 0.57 |
| comparison | ours | 7 | 6.52 / 9.06 | 3.5 | 2.571 | 9133 | 2.14 | 2.14 |
| comparison | ours_v2 | 7 | 5.71 / 7.62 | 2.84 | 2.0 | 6493 | 1.0 | 1.0 |
| comparison | ours_v2_nothink | 7 | 4.27 / 5.2 | 1.44 | 2.0 | 6495 | 1.0 | 1.0 |
| list | ours | 4 | 6.22 / 10.48 | 3.17 | 2.75 | 5201.0 | 1.75 | 0.75 |
| list | ours_v2 | 4 | 6.68 / 11.92 | 3.09 | 2.75 | 6294.0 | 1.75 | 1.0 |
| list | ours_v2_nothink | 4 | 4.16 / 5.89 | 1.25 | 2.25 | 5671.0 | 1.25 | 0.75 |
| formula | ours | 5 | 5.24 / 8.09 | 3.56 | 2.0 | 5196 | 1.0 | 0.8 |
| formula | ours_v2 | 5 | 6.67 / 7.16 | 3.36 | 2.0 | 6700 | 1.0 | 1.0 |
| formula | ours_v2_nothink | 5 | 4.94 / 5.22 | 2.05 | 2.0 | 5158 | 1.0 | 0.2 |
| where | ours | 5 | 3.52 / 4.14 | 2.18 | 2.0 | 4646 | 1.0 | 1.0 |
| where | ours_v2 | 5 | 3.47 / 4.14 | 2.17 | 2.0 | 5114 | 1.0 | 1.0 |
| where | ours_v2_nothink | 5 | 2.23 / 3.24 | 0.79 | 2.0 | 5116 | 1.0 | 1.0 |
| prerequisite | ours | 4 | 5.81 / 7.21 | 2.03 | 2.0 | 4793.5 | 1.0 | 0.0 |
| prerequisite | ours_v2 | 4 | 5.21 / 6.19 | 2.0 | 2.0 | 5261.5 | 1.0 | 0.0 |
| prerequisite | ours_v2_nothink | 4 | 4.3 / 5.65 | 0.8 | 2.0 | 5263.5 | 1.0 | 0.0 |
| structure | ours | 5 | 5.51 / 6.35 | 2.72 | 2.2 | 4892 | 1.2 | 0.4 |
| structure | ours_v2 | 5 | 4.96 / 5.85 | 2.48 | 2.0 | 6315 | 1.0 | 0.4 |
| structure | ours_v2_nothink | 5 | 3.46 / 3.94 | 1.14 | 2.0 | 6317 | 1.0 | 0.4 |
| not_covered | ours | 9 | 3.89 / 4.56 | 2.35 | 2.111 | 4343 | 1.11 | 0.89 |
| not_covered | ours_v2 | 9 | 3.98 / 5.76 | 2.95 | 2.0 | 4811 | 1.0 | 0.89 |
| not_covered | ours_v2_nothink | 9 | 2.44 / 4.55 | 0.81 | 2.0 | 4797 | 1.0 | 0.56 |
| multihop | ours | 12 | 8.0 / 10.13 | 4.82 | 2.583 | 8255.0 | 1.67 | 0.67 |
| multihop | ours_v2 | 12 | 8.29 / 9.55 | 5.25 | 2.5 | 8648.0 | 1.58 | 0.83 |
| multihop | ours_v2_nothink | 12 | 4.82 / 6.2 | 1.91 | 2.25 | 5155.5 | 1.25 | 0.33 |
