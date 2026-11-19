# Run-side numbers (no correctness)

Latency and first token in seconds; context tokens median; model calls mean. Per run file.

## Overall

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 65 | 0 | 5.66 | 8.41 | 2.99 | 4892 | 2.277 |
| ours r2 | 40 | 0 | 5.17 | 7.68 | 3.0 | 4793.5 | 2.275 |
| ours r3 | 40 | 0 | 5.12 | 7.56 | 3.1 | 4793.5 | 2.275 |
| plain r1 | 65 | 0 | 1.59 | 1.94 | 0.08 | 100 | 1.0 |
| rag r1 | 65 | 0 | 4.24 | 5.54 | 1.53 | 4033 | 1.0 |
| rag r2 | 40 | 0 | 4.17 | 5.14 | 1.37 | 3842.5 | 1.0 |
| rag r3 | 40 | 0 | 4.13 | 5.16 | 1.38 | 3842.5 | 1.0 |
| rag_think r1 | 65 | 0 | 25.37 | 48.74 | 24.07 | 4031 | 1.0 |
| rag_think r2 | 40 | 0 | 28.38 | 48.59 | 25.34 | 3840.5 | 1.0 |
| rag_think r3 | 40 | 0 | 28.05 | 48.56 | 25.4 | 3840.5 | 1.0 |
| graphrag_text r1 | 65 | 0 | 5.62 | 8.07 | 3.03 | 8291 | 1.0 |
| graphrag_notext r1 | 65 | 0 | 3.65 | 6.19 | 1.37 | 3624 | 1.0 |
| abl_facts r1 | 65 | 0 | 5.52 | 7.67 | 3.59 | 3593 | 2.092 |
| abl_graph r1 | 65 | 0 | 5.74 | 8.4 | 2.98 | 5211 | 2.554 |

## definition

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 7 | 0 | 4.12 | 6.22 | 2.15 | 5167 | 2.0 |
| plain r1 | 7 | 0 | 1.35 | 1.7 | 0.08 | 93 | 1.0 |
| rag r1 | 7 | 0 | 3.52 | 4.39 | 1.59 | 4059 | 1.0 |
| rag_think r1 | 7 | 0 | 26.21 | 33.0 | 24.4 | 4057 | 1.0 |
| graphrag_text r1 | 7 | 0 | 5.22 | 7.16 | 2.97 | 8134 | 1.0 |
| graphrag_notext r1 | 7 | 0 | 3.71 | 5.05 | 1.36 | 3493 | 1.0 |
| abl_facts r1 | 7 | 0 | 5.77 | 7.2 | 3.01 | 3543 | 2.0 |
| abl_graph r1 | 7 | 0 | 4.12 | 6.7 | 2.19 | 4695 | 2.0 |

## explanation

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 7 | 0 | 5.28 | 6.96 | 3.33 | 5855 | 2.286 |
| plain r1 | 7 | 0 | 1.46 | 1.84 | 0.08 | 99 | 1.0 |
| rag r1 | 7 | 0 | 4.21 | 5.27 | 1.55 | 4058 | 1.0 |
| rag_think r1 | 7 | 0 | 24.36 | 38.17 | 22.58 | 4056 | 1.0 |
| graphrag_text r1 | 7 | 0 | 5.74 | 6.56 | 3.27 | 8464 | 1.0 |
| graphrag_notext r1 | 7 | 0 | 3.5 | 4.83 | 1.48 | 3878 | 1.0 |
| abl_facts r1 | 7 | 0 | 5.41 | 5.85 | 3.62 | 3593 | 2.0 |
| abl_graph r1 | 7 | 0 | 6.25 | 7.17 | 3.05 | 5383 | 2.429 |

## comparison

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 7 | 0 | 6.52 | 9.06 | 3.5 | 9133 | 2.571 |
| plain r1 | 7 | 0 | 1.56 | 1.67 | 0.08 | 98 | 1.0 |
| rag r1 | 7 | 0 | 4.94 | 5.47 | 1.58 | 4064 | 1.0 |
| rag_think r1 | 7 | 0 | 20.7 | 41.92 | 17.3 | 4062 | 1.0 |
| graphrag_text r1 | 7 | 0 | 6.18 | 6.35 | 3.03 | 8305 | 1.0 |
| graphrag_notext r1 | 7 | 0 | 4.33 | 4.98 | 1.43 | 3796 | 1.0 |
| abl_facts r1 | 7 | 0 | 5.52 | 6.05 | 3.4 | 3502 | 2.0 |
| abl_graph r1 | 7 | 0 | 6.56 | 7.41 | 3.53 | 6988 | 2.714 |

## list

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 4 | 0 | 6.22 | 10.48 | 3.17 | 5201.0 | 2.75 |
| plain r1 | 4 | 0 | 1.63 | 2.11 | 0.08 | 96.5 | 1.0 |
| rag r1 | 4 | 0 | 3.53 | 7.59 | 1.48 | 3978.0 | 1.0 |
| rag_think r1 | 4 | 0 | 18.78 | 66.44 | 16.49 | 3976.0 | 1.0 |
| graphrag_text r1 | 4 | 0 | 5.63 | 8.18 | 3.13 | 8336.5 | 1.0 |
| graphrag_notext r1 | 4 | 0 | 4.12 | 6.19 | 1.42 | 3888.5 | 1.0 |
| abl_facts r1 | 4 | 0 | 5.35 | 6.52 | 3.17 | 3533.5 | 2.0 |
| abl_graph r1 | 4 | 0 | 6.67 | 8.67 | 3.79 | 5354.0 | 2.75 |

## formula

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 5 | 0 | 5.24 | 8.09 | 3.56 | 5196 | 2.0 |
| ours r2 | 5 | 0 | 5.35 | 7.26 | 3.24 | 5196 | 2.0 |
| ours r3 | 5 | 0 | 5.4 | 7.24 | 3.29 | 5196 | 2.0 |
| plain r1 | 5 | 0 | 1.67 | 1.87 | 0.09 | 104 | 1.0 |
| rag r1 | 5 | 0 | 4.69 | 5.67 | 1.61 | 4089 | 1.0 |
| rag r2 | 5 | 0 | 4.36 | 5.09 | 1.46 | 4089 | 1.0 |
| rag r3 | 5 | 0 | 4.16 | 5.08 | 1.42 | 4089 | 1.0 |
| rag_think r1 | 5 | 0 | 27.85 | 60.65 | 24.57 | 4087 | 1.0 |
| rag_think r2 | 5 | 0 | 28.72 | 61.46 | 25.01 | 4087 | 1.0 |
| rag_think r3 | 5 | 0 | 28.46 | 60.8 | 25.09 | 4087 | 1.0 |
| graphrag_text r1 | 5 | 0 | 5.65 | 6.45 | 3.25 | 8405 | 1.0 |
| graphrag_notext r1 | 5 | 0 | 3.65 | 4.12 | 1.39 | 3624 | 1.0 |
| abl_facts r1 | 5 | 0 | 6.23 | 7.76 | 3.69 | 3649 | 2.0 |
| abl_graph r1 | 5 | 0 | 6.45 | 7.16 | 3.24 | 5211 | 2.2 |

## where

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 5 | 0 | 3.52 | 4.14 | 2.18 | 4646 | 2.0 |
| ours r2 | 5 | 0 | 3.12 | 4.2 | 2.08 | 4646 | 2.0 |
| ours r3 | 5 | 0 | 3.15 | 4.19 | 2.07 | 4646 | 2.0 |
| plain r1 | 5 | 0 | 0.85 | 1.29 | 0.08 | 97 | 1.0 |
| rag r1 | 5 | 0 | 3.11 | 4.87 | 1.35 | 3478 | 1.0 |
| rag r2 | 5 | 0 | 2.57 | 5.04 | 1.25 | 3478 | 1.0 |
| rag r3 | 5 | 0 | 2.64 | 5.15 | 1.27 | 3478 | 1.0 |
| rag_think r1 | 5 | 0 | 22.6 | 45.67 | 20.66 | 3476 | 1.0 |
| rag_think r2 | 5 | 0 | 22.67 | 46.49 | 20.66 | 3476 | 1.0 |
| rag_think r3 | 5 | 0 | 22.37 | 45.84 | 20.43 | 3476 | 1.0 |
| graphrag_text r1 | 5 | 0 | 3.96 | 5.21 | 3.0 | 8314 | 1.0 |
| graphrag_notext r1 | 5 | 0 | 3.14 | 4.52 | 1.33 | 3437 | 1.0 |
| abl_facts r1 | 5 | 0 | 4.9 | 6.41 | 2.94 | 3626 | 2.0 |
| abl_graph r1 | 5 | 0 | 3.53 | 4.56 | 2.27 | 4174 | 2.0 |

## prerequisite

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 4 | 0 | 5.81 | 7.21 | 2.03 | 4793.5 | 2.0 |
| ours r2 | 4 | 0 | 5.39 | 7.32 | 2.02 | 4793.5 | 2.0 |
| ours r3 | 4 | 0 | 5.33 | 7.21 | 2.01 | 4793.5 | 2.0 |
| plain r1 | 4 | 0 | 1.7 | 1.78 | 0.08 | 99.5 | 1.0 |
| rag r1 | 4 | 0 | 2.49 | 4.63 | 0.88 | 2356.0 | 1.0 |
| rag r2 | 4 | 0 | 2.73 | 5.76 | 0.82 | 2356.0 | 1.0 |
| rag r3 | 4 | 0 | 2.62 | 5.52 | 0.78 | 2356.0 | 1.0 |
| rag_think r1 | 4 | 0 | 42.16 | 77.72 | 40.5 | 2354.0 | 1.0 |
| rag_think r2 | 4 | 0 | 42.31 | 78.08 | 40.66 | 2354.0 | 1.0 |
| rag_think r3 | 4 | 0 | 42.46 | 77.84 | 40.82 | 2354.0 | 1.0 |
| graphrag_text r1 | 4 | 0 | 6.2 | 6.85 | 2.95 | 8184.0 | 1.0 |
| graphrag_notext r1 | 4 | 0 | 3.67 | 6.75 | 1.26 | 3247.5 | 1.0 |
| abl_facts r1 | 4 | 0 | 4.2 | 4.74 | 3.9 | 3595.0 | 2.0 |
| abl_graph r1 | 4 | 0 | 5.61 | 7.64 | 2.1 | 4321.5 | 2.0 |

## structure

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 5 | 0 | 5.51 | 6.35 | 2.72 | 4892 | 2.2 |
| ours r2 | 5 | 0 | 4.58 | 5.45 | 2.51 | 4601 | 2.2 |
| ours r3 | 5 | 0 | 4.41 | 5.47 | 2.57 | 4601 | 2.2 |
| plain r1 | 5 | 0 | 1.04 | 1.57 | 0.08 | 97 | 1.0 |
| rag r1 | 5 | 0 | 3.78 | 5.58 | 1.36 | 3505 | 1.0 |
| rag r2 | 5 | 0 | 4.22 | 5.75 | 1.3 | 3505 | 1.0 |
| rag r3 | 5 | 0 | 4.15 | 5.55 | 1.23 | 3505 | 1.0 |
| rag_think r1 | 5 | 0 | 39.39 | 58.34 | 36.37 | 3503 | 1.0 |
| rag_think r2 | 5 | 0 | 39.44 | 58.68 | 36.55 | 3503 | 1.0 |
| rag_think r3 | 5 | 0 | 39.28 | 58.66 | 36.35 | 3503 | 1.0 |
| graphrag_text r1 | 5 | 0 | 4.83 | 9.4 | 2.97 | 8091 | 1.0 |
| graphrag_notext r1 | 5 | 0 | 3.27 | 6.33 | 1.27 | 3296 | 1.0 |
| abl_facts r1 | 5 | 0 | 4.66 | 5.57 | 3.44 | 3601 | 2.0 |
| abl_graph r1 | 5 | 0 | 5.62 | 8.4 | 3.58 | 4420 | 2.2 |

## not_covered

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 9 | 0 | 3.89 | 4.56 | 2.35 | 4343 | 2.111 |
| ours r2 | 9 | 0 | 3.86 | 5.48 | 2.72 | 4327 | 2.0 |
| ours r3 | 9 | 0 | 3.93 | 5.63 | 2.74 | 4327 | 2.0 |
| plain r1 | 9 | 0 | 1.82 | 1.99 | 0.08 | 102 | 1.0 |
| rag r1 | 9 | 0 | 3.07 | 4.41 | 1.5 | 4009 | 1.0 |
| rag r2 | 9 | 0 | 3.29 | 4.51 | 1.42 | 4009 | 1.0 |
| rag r3 | 9 | 0 | 3.23 | 4.46 | 1.39 | 4009 | 1.0 |
| rag_think r1 | 9 | 0 | 21.54 | 28.31 | 19.58 | 4007 | 1.0 |
| rag_think r2 | 9 | 0 | 21.43 | 29.11 | 19.54 | 4007 | 1.0 |
| rag_think r3 | 9 | 0 | 21.35 | 28.21 | 19.45 | 4007 | 1.0 |
| graphrag_text r1 | 9 | 0 | 4.52 | 5.02 | 2.96 | 8215 | 1.0 |
| graphrag_notext r1 | 9 | 0 | 2.91 | 3.57 | 1.34 | 3484 | 1.0 |
| abl_facts r1 | 9 | 0 | 6.17 | 7.67 | 4.35 | 3671 | 2.556 |
| abl_graph r1 | 9 | 0 | 3.76 | 4.58 | 2.4 | 3855 | 2.0 |

## multihop

| run | answers | errors | latency_median_s | latency_p90_s | first_token_median_s | context_tokens_median | model_calls_mean |
|---|---|---|---|---|---|---|---|
| ours r1 | 12 | 0 | 8.0 | 10.13 | 4.82 | 8255.0 | 2.583 |
| ours r2 | 12 | 0 | 7.56 | 9.41 | 4.74 | 8321.5 | 2.833 |
| ours r3 | 12 | 0 | 7.26 | 8.66 | 4.46 | 8321.5 | 2.833 |
| plain r1 | 12 | 0 | 1.77 | 1.98 | 0.09 | 110.0 | 1.0 |
| rag r1 | 12 | 0 | 4.81 | 9.47 | 1.56 | 4046.5 | 1.0 |
| rag r2 | 12 | 0 | 4.54 | 5.65 | 1.4 | 4046.5 | 1.0 |
| rag r3 | 12 | 0 | 4.54 | 5.68 | 1.4 | 4046.5 | 1.0 |
| rag_think r1 | 12 | 0 | 28.94 | 37.79 | 26.25 | 4044.5 | 1.0 |
| rag_think r2 | 12 | 0 | 29.0 | 37.8 | 26.3 | 4044.5 | 1.0 |
| rag_think r3 | 12 | 0 | 28.98 | 37.79 | 26.3 | 4044.5 | 1.0 |
| graphrag_text r1 | 12 | 0 | 6.31 | 9.76 | 3.45 | 8579.5 | 1.0 |
| graphrag_notext r1 | 12 | 0 | 4.38 | 6.36 | 1.42 | 4044.0 | 1.0 |
| abl_facts r1 | 12 | 0 | 7.08 | 9.23 | 4.32 | 3589.5 | 2.083 |
| abl_graph r1 | 12 | 0 | 7.93 | 9.72 | 5.12 | 12740.5 | 3.917 |

## GraphRAG index

{"text_units_extracted": 476, "entities": 3515, "relationships": 3790, "communities": 332, "community_reports": 332}
