# VR course on the small setup: what it produced

Run `v2-20261103-0755/small`: Gemma 4 E4B writes, Gemma 4 12B verifies and judges, vLLM 0.32.0 on one RTX PRO 6000.
All 63 lectures built (exit 0). Compared with v1 (`lir/nptel-virtual-and-augmented-reality/`, Gemma E4B + gpt-6-luna
judge). Numbers from the LIR files, `decisions.jsonl`, `calls.jsonl` and `report.md`. Written 2026-11-03.

The large setup (Qwen 27B) was stopped by hand at 17% (key points 228/321 parts); its answer cache is intact, so
`bash run_v2.sh --resume v2-20261103-0755 --setups large --courses vr` continues it. Fix item 1 below first: the same
overflow would hit it.

## Verdict

The knowledge per part is as good as v1 or better, and the v1 registry problems are mostly gone. Two steps failed
silently on the second half of the course: **27 of 63 lectures have no links**, and **20 lectures have no open
questions**. The run took 2.7× the planned time, because the 12B judge did most of the work.

## Fix first

| # | Problem | Evidence | Fix |
|--:|---|---|---|
| 1 | **Links missing in 27 lectures** (L21, L27, L31, L37–L63 except L43, L46, L48) | Every `links.lecture` call for those lectures was cut at length (56 of 92 calls; 30 retries). The prompt grows with every earlier facet of every concept: up to 63.9k input tokens against a 65.5k context. Result: 57% of concepts have no link (v1: 48%) | Cap the earlier facets per concept (e.g. the latest 2), or split a lecture's concepts into groups (the open decision in `pipeline2/TASKS.md`). Rerun from the cache: only links and what follows are recomputed |
| 2 | **Open questions: 20 lectures with none, 25 with one** (plan: 2–6) | 70 questions dropped by the code check "each key point needs 2 keywords word for word in the reference answer" (59 of the 70). L16 (tracking) has none | Send the failed check back for one rewrite, as the judges do, instead of dropping; or pick the keywords in code from the reference answer |
| 3 | **Judges set the run time** | 2,711 judge + 1,035 rewrite calls: 58% of requests, 12.1 M of 18.0 M output tokens, 90%+ of it thinking, p50 latency 400 s. The 12B server made ~76% of all tokens with 0.56 of the GPU; 628 preemptions | Judge thinking cap 4k → 1.5–2k; give the 12B more memory (E4B 0.34 → ~0.2); fewer E4B slots (256 overfilled its KV cache) |
| 4 | **Registry: bad aliases and missed merges** | Aliases that are sentences ("A virtual reality system is an artificial environment which…"); "3D" as an abbreviation of *3D graphics pipeline*; "Actual visual speed" merged into *Perceived speed*; *Virtual reality* an alias of *Virtual reality system* while also its own concept; 11 exact-name duplicates (e.g. *XR system* ×2) | Code checks: an alias is a short name (no sentence), an abbreviation is not a common token; merge exact-name duplicates in code |

## Smaller issues

- **Text junk in key points**: 16.4% keep "(52, 53, 57)" (decided: no fix) and 5.3% end in ", " or ",," (for example *"…tracking moving real-world objects.,,"*). Both are one-regex cleanups in `strip_ids`.
- **Judge strictness is uneven**: it fails 42% of key terms (522 dropped after a rewrite) and 24% of facets, but passes 92% of links. Some links it kept are weak (*Expert kind_of User*, *Wave depends_on Frequency* flagged forward).
- **101 links flagged `forward`** (`depends_on` towards a later concept) and 20 two-way.
- **A quiz item that contradicts the lecture** passed the judge (L16: "'tracking' and 'sensing' refer to the same function" → False, while the lecture says they are used interchangeably).
- **Term → concept mismatches**: 210 of 2,278 terms map to a concept with a different name, some wrong (*Tracker* → *Tracking*).

## By the numbers

| | v1 | v2 small | |
|---|--:|--:|---|
| Parts | 388 | 405 | |
| Key points | 1,549 (3.99/part) | 1,508 (3.72/part) | 84 failed the judge, 79 repaired |
| Key term occurrences | 1,201 | 2,278 | 2,908 kept by step 3, 522 dropped by the judge |
| Concepts | 883 | 1,395 | 1,019 appear once: the registry is fragmented |
| Duplicate concept names | 52 | 11 | |
| "Extended reality" aliases | ER, Error rates, Empirical research, … | XR | v1's chain merges are gone |
| Links | 417 | 814 | in 36 lectures only |
| Prerequisite / `depends_on` links | 7 | 189 | |
| Concepts with no link | 48% | 57% | caused by problem 1 |
| Facets | – | 9,079 (4,980 taught) | 328 turned into mentions by the judge |
| Quiz items | | 808 (2.0/part) | MC 493, true/false 258, yes/no 57; 16 parts without a quiz |
| Recaps / review questions / recall | | 405 / 562 / 247 | |
| Open questions | | 62 | see problem 2 |
| Run time | 2 h 51 min | 5 h 39 min | plan 2.1 h |
| Requests / output tokens | 5,149 / – | 6,423 / 18.0 M | plan ~6.0k requests |

## What reads well

Side by side on L16 (tracking), v2's parts cover the same topics as v1's segments, and the key points are at least as precise and now
carry sentence addresses and concept IDs. Example: *"Tracking the surrounding environment is critical in AR for registering
digital content and essential in VR for safety warnings."* Quiz items are mostly on target, with an explanation for
every option. Recaps read naturally. The five course goals cover the course (concepts and history, human factors,
interaction design, hardware and graphics, evaluation).

## Next steps

1. Fix 1 and 2 (and 3 if speed matters), then rerun the small setup from its cache. Only links, open questions and
   what depends on them are recomputed.
2. Resume the large setup on the fixed code and compare.
