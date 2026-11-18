# Baseline comparison tables

Run 1 of every system, 53 questions. correct: mean of 1 / 0.5 / 0 (Sonnet judge). halluc: false claims counted (answers with one). cit valid: by code (see summarize.py). nc handled: not-covered questions answered as not covered without invented content. ctx: median context tokens. calls: mean model calls. latency / first token in seconds.

## Overall

| system | correct | halluc (answers) | cit valid | nc handled | ctx | calls | latency med | latency p90 | first token |
|---|---|---|---|---|---|---|---|---|---|
| ours | 0.868 | 2 (2) | 160/194 | 8/9 | 4804 | 2.208 | 5.03 | 7.75 | 2.87 |
| plain | 0.255 | 43 (29) | 0/0 | 1/9 | 98 | 1.0 | 1.56 | 1.87 | 0.08 |
| rag | 0.858 | 1 (1) | 197/214 | 9/9 | 4027 | 1.0 | 3.85 | 5.47 | 1.53 |
| rag_think | 0.858 | 1 (1) | 195/216 | 9/9 | 4025 | 1.0 | 24.36 | 48.78 | 22.58 |
| graphrag_text | 0.821 | 0 (0) | 174/248 | 8/9 | 8276 | 1.0 | 5.51 | 7.16 | 3.0 |
| graphrag_notext | 0.717 | 3 (3) | 163/277 | 8/9 | 3529 | 1.0 | 3.53 | 5.05 | 1.36 |
| abl_facts | 0.802 | 0 (0) | 152/176 | 8/9 | 3593 | 2.094 | 5.41 | 7.19 | 3.45 |
| abl_graph | 0.887 | 3 (3) | 172/222 | 7/9 | 4392 | 2.245 | 5.48 | 7.74 | 2.89 |

## Correct per category

| category (n) | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph |
|---|---|---|---|---|---|---|---|---|
| definition (7) | 1.0 | 0.571 | 0.786 | 0.714 | 0.786 | 0.643 | 0.929 | 1.0 |
| explanation (7) | 0.929 | 0.5 | 1.0 | 0.929 | 1.0 | 0.857 | 0.786 | 0.857 |
| comparison (7) | 0.929 | 0.429 | 1.0 | 1.0 | 1.0 | 0.786 | 1.0 | 1.0 |
| list (4) | 0.875 | 0.125 | 1.0 | 1.0 | 0.875 | 0.875 | 1.0 | 0.875 |
| formula (5) | 0.9 | 0.3 | 0.7 | 0.9 | 0.8 | 0.5 | 0.8 | 0.9 |
| where (5) | 1.0 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| prerequisite (4) | 0.5 | 0.0 | 0.125 | 0.125 | 0.0 | 0.0 | 0.0 | 0.75 |
| structure (5) | 0.6 | 0.0 | 0.9 | 0.9 | 0.7 | 0.6 | 0.4 | 0.6 |
| not_covered (9) | 0.889 | 0.111 | 0.944 | 0.944 | 0.889 | 0.889 | 0.944 | 0.889 |

## Hallucinations per category (count)

| category | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph |
|---|---|---|---|---|---|---|---|---|
| definition | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| explanation | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| comparison | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| list | 0 | 13 | 0 | 0 | 0 | 1 | 0 | 0 |
| formula | 0 | 2 | 1 | 1 | 0 | 1 | 0 | 0 |
| where | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| prerequisite | 0 | 4 | 0 | 0 | 0 | 1 | 0 | 1 |
| structure | 1 | 8 | 0 | 0 | 0 | 0 | 0 | 2 |
| not_covered | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |

## Citation validity per category (valid/total)

| category | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph |
|---|---|---|---|---|---|---|---|---|
| definition | 38/41 | 0/0 | 26/26 | 27/27 | 30/46 | 26/42 | 27/30 | 39/44 |
| explanation | 16/20 | 0/0 | 27/33 | 25/31 | 21/37 | 13/39 | 18/19 | 22/29 |
| comparison | 36/36 | 0/0 | 40/41 | 36/37 | 38/48 | 34/49 | 30/32 | 35/39 |
| list | 18/18 | 0/0 | 27/27 | 22/24 | 21/29 | 22/34 | 21/21 | 22/27 |
| formula | 11/14 | 0/0 | 24/26 | 19/20 | 21/21 | 17/19 | 12/14 | 9/12 |
| where | 9/12 | 0/0 | 8/9 | 17/17 | 4/9 | 7/21 | 15/19 | 7/12 |
| prerequisite | 13/19 | 0/0 | 10/11 | 7/14 | 15/23 | 5/9 | 0/0 | 15/21 |
| structure | 7/17 | 0/0 | 16/20 | 21/25 | 9/11 | 20/34 | 1/12 | 9/18 |
| not_covered | 12/17 | 0/0 | 19/21 | 21/21 | 15/24 | 19/30 | 28/29 | 14/20 |

## Latency median / first token median per category (s)

| category | ours | plain | rag | rag_think | graphrag_text | graphrag_notext | abl_facts | abl_graph |
|---|---|---|---|---|---|---|---|---|
| definition | 4.12 / 2.15 | 1.35 / 0.08 | 3.52 / 1.59 | 26.21 / 24.4 | 5.22 / 2.97 | 3.71 / 1.36 | 5.77 / 3.01 | 4.12 / 2.19 |
| explanation | 5.28 / 3.33 | 1.46 / 0.08 | 4.21 / 1.55 | 24.36 / 22.58 | 5.74 / 3.27 | 3.5 / 1.48 | 5.41 / 3.62 | 6.25 / 3.05 |
| comparison | 6.52 / 3.5 | 1.56 / 0.08 | 4.94 / 1.58 | 20.7 / 17.3 | 6.18 / 3.03 | 4.33 / 1.43 | 5.52 / 3.4 | 6.56 / 3.53 |
| list | 6.22 / 3.17 | 1.63 / 0.08 | 3.53 / 1.48 | 18.78 / 16.49 | 5.63 / 3.13 | 4.12 / 1.42 | 5.35 / 3.17 | 6.67 / 3.79 |
| formula | 5.24 / 3.56 | 1.67 / 0.09 | 4.69 / 1.61 | 27.85 / 24.57 | 5.65 / 3.25 | 3.65 / 1.39 | 6.23 / 3.69 | 6.45 / 3.24 |
| where | 3.52 / 2.18 | 0.85 / 0.08 | 3.11 / 1.35 | 22.6 / 20.66 | 3.96 / 3.0 | 3.14 / 1.33 | 4.9 / 2.94 | 3.53 / 2.27 |
| prerequisite | 5.81 / 2.03 | 1.7 / 0.08 | 2.49 / 0.88 | 42.16 / 40.5 | 6.2 / 2.95 | 3.67 / 1.26 | 4.2 / 3.9 | 5.61 / 2.1 |
| structure | 5.51 / 2.72 | 1.04 / 0.08 | 3.78 / 1.36 | 39.39 / 36.37 | 4.83 / 2.97 | 3.27 / 1.27 | 4.66 / 3.44 | 5.62 / 3.58 |
| not_covered | 3.89 / 2.35 | 1.82 / 0.08 | 3.07 / 1.5 | 21.54 / 19.58 | 4.52 / 2.96 | 2.91 / 1.34 | 6.17 / 4.35 | 3.76 / 2.4 |

## Repeats (3 runs): correct, mean ± range (min-max) across runs

| category | ours | rag | rag_think |
|---|---|---|---|
| not_covered | 0.889 (0.889-0.889, 3 runs) | 0.944 (0.944-0.944, 3 runs) | 0.944 (0.944-0.944, 3 runs) |
| where | 1.0 (1.0-1.0, 3 runs) | 1.0 (1.0-1.0, 3 runs) | 1.0 (1.0-1.0, 3 runs) |
| prerequisite | 0.5 (0.5-0.5, 3 runs) | 0.042 (0.0-0.125, 3 runs) | 0.125 (0.125-0.125, 3 runs) |
| structure | 0.6 (0.6-0.6, 3 runs) | 0.9 (0.9-0.9, 3 runs) | 0.9 (0.9-0.9, 3 runs) |
| formula | 0.9 (0.9-0.9, 3 runs) | 0.7 (0.7-0.7, 3 runs) | 0.9 (0.9-0.9, 3 runs) |
